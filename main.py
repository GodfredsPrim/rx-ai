from pathlib import Path
from io import BytesIO, StringIO
import re
import csv
from typing import List

import os
from dotenv import load_dotenv
import pypdf
from authlib.integrations.starlette_client import OAuth
import json
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import auth
from auth import get_current_user, get_optional_user, get_current_pharmacist, get_current_admin
import models
import schemas
import chat_engine
import whatsapp_bot
from database import SessionLocal, engine, get_db

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env', override=True, verbose=True)
STATIC_DIR = BASE_DIR / "static"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", os.getenv("FRONTEND_URL", "http://127.0.0.1:8000")).split(",")
    if origin.strip()
]


def _ensure_legacy_schema_updates():
    inspector = inspect(engine)

    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" not in user_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))


# Create DB tables
models.Base.metadata.create_all(bind=engine)
_ensure_legacy_schema_updates()

app = FastAPI(title="RxAI Ghana API")
app.include_router(whatsapp_bot.router)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET") or "dev-secret-change-me",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", "dummy_key"))
configured_base_url = os.getenv("DEEPSEEK_BASE_URL", "").strip()
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

if configured_base_url:
    base_url = configured_base_url
else:
    # If DEEPSEEK_BASE_URL is not set, use OpenAI for sk- keys, otherwise DeepSeek default.
    if api_key.startswith("sk-"):
        base_url = "https://api.openai.com/v1"
    else:
        base_url = "https://api.deepseek.com"



openai_client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=LLM_MAX_RETRIES,
)

# Model name: default to deepseek-chat for DeepSeek keys, gpt-4o-mini for OpenAI keys
# Can always be overridden with MODEL_NAME env variable
_default_model = "gpt-4o-mini" if api_key.startswith("sk-") and not configured_base_url else "deepseek-chat"
MODEL_NAME = os.getenv("MODEL_NAME", _default_model)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# ─── WebSocket Connection Manager ─────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}  # user_id -> sockets
        self.case_connections: dict[int, list[WebSocket]] = {}    # case_id -> sockets (guests)
        self.pharmacist_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        conns = self.active_connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)

    async def connect_case(self, websocket: WebSocket, case_id: int):
        await websocket.accept()
        self.case_connections.setdefault(case_id, []).append(websocket)

    def disconnect_case(self, websocket: WebSocket, case_id: int):
        conns = self.case_connections.get(case_id, [])
        if websocket in conns:
            conns.remove(websocket)

    async def connect_pharmacist(self, websocket: WebSocket):
        await websocket.accept()
        self.pharmacist_connections.append(websocket)

    def disconnect_pharmacist(self, websocket: WebSocket):
        if websocket in self.pharmacist_connections:
            self.pharmacist_connections.remove(websocket)

    async def notify_user(self, user_id: int, data: dict):
        for ws in list(self.active_connections.get(user_id, [])):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                pass

    async def notify_case(self, case_id: int, data: dict):
        for ws in list(self.case_connections.get(case_id, [])):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                pass

    async def notify_pharmacists(self, data: dict):
        for ws in list(self.pharmacist_connections):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                pass


ws_manager = ConnectionManager()
# ──────────────────────────────────────────────────────────────────────────────


def _get_public_base_url(request: Request | None = None) -> str:
    frontend_url = os.getenv("FRONTEND_URL", "").strip()
    if frontend_url:
        return frontend_url.rstrip("/")
    if request:
        return str(request.base_url).rstrip("/")
    return "http://127.0.0.1:8000"


def _get_waitlist_public_info_payload(request: Request) -> schemas.WaitlistPublicInfo:
    base_url = _get_public_base_url(request)
    return schemas.WaitlistPublicInfo(
        waitlist_url=f"{base_url}/waitlist",
        qr_image_url=f"{base_url}/api/waitlist/qr",
        qr_page_url=f"{base_url}/waitlist/qr",
    )


def _serialize_waitlist_entry(entry: models.WaitlistEntry) -> dict:
    return {
        "id": entry.id,
        "full_name": entry.full_name,
        "email": entry.email,
        "phone": entry.phone,
        "location": entry.location,
        "notes": entry.notes,
        "source": entry.source,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }

def _find_guidelines_pdf() -> Path | None:
    configured = os.getenv("GUIDELINES_PDF_PATH")
    if configured:
        pdf_path = Path(configured)
        if pdf_path.exists():
            return pdf_path

    pdf_files = sorted(BASE_DIR.glob("*.pdf"))
    return pdf_files[0] if pdf_files else None


def _clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _chunk_text(text: str, chunk_size: int = 180, overlap: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _load_pdf_chunks() -> tuple[str, list[dict]]:
    pdf_path = _find_guidelines_pdf()
    if not pdf_path:
        return "", []

    full_text_parts: list[str] = []
    chunks: list[dict] = []

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        for page_index, page in enumerate(reader.pages, start=1):
            page_text = _clean_whitespace(page.extract_text() or "")
            if not page_text:
                continue

            full_text_parts.append(page_text)
            for chunk in _chunk_text(page_text):
                chunks.append(
                    {
                        "page": page_index,
                        "text": chunk,
                        "tokens": _tokenize(chunk),
                    }
                )
    except Exception as exc:
        print(f"Failed to load PDF context: {exc}")
        return "", []

    return "\n".join(full_text_parts), chunks


pdf_context, pdf_chunks = _load_pdf_chunks()


def _load_medicine_dataset() -> List[dict]:
    csv_path = BASE_DIR / "medicine_dataset.csv"
    if not csv_path.exists():
        return []
    
    medicines = []
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Pre-tokenize names for faster search
                row["_tokens"] = _tokenize(row.get("Name", "") + " " + row.get("Category", ""))
                medicines.append(row)
    except Exception as exc:
        print(f"Failed to load medicine dataset: {exc}")
    return medicines


medicine_dataset = _load_medicine_dataset()


def _load_twi_dataset() -> List[dict]:
    csv_path = BASE_DIR / "Public - Twi[Twi-En]_70.csv"
    if not csv_path.exists():
        csv_path = BASE_DIR / "Public%20-%20Twi%5BTwi-En%5D_70.csv"
    if not csv_path.exists():
        return []

    twi_entries = []
    try:
        with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                twi_text = (row.get("text") or "").strip()
                en_text = (row.get("label") or row.get("Comments") or "").strip()
                if twi_text and en_text:
                    twi_entries.append({"twi": twi_text, "en": en_text})
    except Exception as exc:
        print(f"Failed to load Twi dataset: {exc}")

    return twi_entries


twi_dataset = _load_twi_dataset()


def _load_final_dataset() -> List[dict]:
    csv_path = BASE_DIR / "final.csv"
    if not csv_path.exists():
        return []

    entries = []
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # final.csv has: ,disease,drug
                disease = row.get("disease", "").strip()
                drug = row.get("drug", "").strip()
                if disease and drug:
                    entries.append({
                        "disease": disease,
                        "drug": drug,
                        "_tokens": _tokenize(disease + " " + drug)
                    })
    except Exception as exc:
        print(f"Failed to load final dataset: {exc}")
    return entries


final_dataset = _load_final_dataset()


def _translate_twi_to_english(text: str) -> str | None:
    normalized = text.strip().lower()
    for pair in twi_dataset:
        if pair["twi"].strip().lower() == normalized:
            return pair["en"]
    return None


SYSTEM_PROMPT = f"""You are RxAI, a warm and capable clinical conversation assistant for pharmacy triage.

STYLE:
- Sound natural, calm, and caring.
- Use short, smooth replies, usually 2 to 4 sentences.
- Refer to what the user just said so the conversation feels continuous.
- Do not repeat the same empathy phrase every turn.
- Avoid sounding robotic, dramatic, or overly scripted.

CONVERSATION RULES:
1. Ask only one follow-up question per reply.
2. Wait for the user's answer before moving to the next question.
3. Start with a brief human acknowledgment, then continue naturally.
4. Gather this information before transitioning: duration, severity or progression, and other associated symptoms.
5. After enough information has been gathered, begin the reply with the exact marker [CONSULT_READY], then give a short summary and explain that the case will be sent to a licensed pharmacist for diagnosis and treatment decisions.
6. Do not prescribe and do not recommend specific drug names to the patient. The pharmacist makes the treatment decision.
7. Respond in the same language the user writes in.
8. If there are danger signs such as difficulty breathing, confusion, convulsions, jaundice, severe dehydration, or chest pain, clearly advise urgent hospital care.
9. Never dump a long checklist unless the user asks. Keep the exchange conversational.

BASE MEDICAL GUIDELINES CONTEXT:
{pdf_context[:4000]}"""


def _get_relevant_medicine_context(messages: list[dict], limit: int = 5) -> str:
    if not medicine_dataset:
        return ""

    query_text = " ".join(message["content"] for message in messages if message.get("role") == "user")
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return ""

    scored = []
    for med in medicine_dataset:
        overlap = query_tokens.intersection(med["_tokens"])
        if overlap:
            scored.append((len(overlap), med))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:limit]
    if not top:
        return ""

    context_parts = []
    for _, med in top:
        parts = [f"Drug: {med.get('Name')}"]
        if med.get("Category"): parts.append(f"Category: {med.get('Category')}")
        if med.get("Indication"): parts.append(f"Indication: {med.get('Indication')}")
        if med.get("Dosage Form"): parts.append(f"Form: {med.get('Dosage Form')}")
        if med.get("Strength"): parts.append(f"Strength: {med.get('Strength')}")
        context_parts.append(" | ".join(parts))

    return "\n".join(context_parts)


def _search_medicine_dataset(symptom_summary: str, limit: int = 5) -> list[dict]:
    """Search the medicine dataset for drugs matching symptoms. Returns at least 3 relevant results with dosage instructions."""
    if not medicine_dataset:
        return []

    query_tokens = _tokenize(symptom_summary)
    if not query_tokens:
        return []

    # Expanded map of symptoms to indications with dosage hints
    symptom_info = {
        "headache": {"indications": ["pain", "headache"], "dosage_hint": "Take 500mg-1g every 4-6 hours as needed, max 4g daily"},
        "fever": {"indications": ["fever", "pain"], "dosage_hint": "Take 500mg-1g every 4-6 hours as needed for fever"},
        "malaria": {"indications": ["fever", "infection", "malaria"], "dosage_hint": "Standard course: 1 tablet twice daily for 3 days with food"},
        "cough": {"indications": ["infection", "cough"], "dosage_hint": "Take 5-10ml every 4-6 hours as needed"},
        "cold": {"indications": ["infection", "virus", "cold"], "dosage_hint": "Take as directed, usually 1 tablet every 6-8 hours"},
        "flu": {"indications": ["virus", "infection", "flu"], "dosage_hint": "Take 1 tablet every 6-8 hours with food"},
        "diarrhea": {"indications": ["infection", "diarrhea"], "dosage_hint": "Take 2 tablets after each loose stool, max 8 tablets daily"},
        "stomach": {"indications": ["pain", "stomach"], "dosage_hint": "Take 1 tablet 30 minutes before meals"},
        "nausea": {"indications": ["nausea", "stomach"], "dosage_hint": "Take 25mg every 6-8 hours as needed"},
        "vomiting": {"indications": ["nausea", "vomiting"], "dosage_hint": "Take as directed, usually 10mg every 8 hours"},
        "wound": {"indications": ["wound", "infection"], "dosage_hint": "Apply topically 2-3 times daily or as directed"},
        "cut": {"indications": ["wound", "cut"], "dosage_hint": "Clean wound and apply 2-3 times daily"},
        "infection": {"indications": ["infection", "bacterial"], "dosage_hint": "Take 500mg every 6 hours or as prescribed"},
        "pain": {"indications": ["pain", "inflammation"], "dosage_hint": "Take 400-800mg every 6-8 hours as needed"},
        "inflammation": {"indications": ["pain", "inflammation"], "dosage_hint": "Take 200-400mg every 4-6 hours as needed"},
        "allergy": {"indications": ["allergy", "allergic"], "dosage_hint": "Take 10mg once daily for allergy relief"},
        "allergic": {"indications": ["allergy", "allergic"], "dosage_hint": "Take 10mg once daily"},
        "diabetes": {"indications": ["diabetes", "blood sugar"], "dosage_hint": "Take 500mg-1g twice daily with meals as prescribed"},
        "sugar": {"indications": ["diabetes", "blood sugar"], "dosage_hint": "Take as prescribed by your doctor"},
        "blood pressure": {"indications": ["hypertension", "blood pressure"], "dosage_hint": "Take 5-10mg once daily as prescribed"},
        "hypertension": {"indications": ["hypertension", "blood pressure"], "dosage_hint": "Take 5-10mg once daily"},
        "depression": {"indications": ["depression", "mental health"], "dosage_hint": "Take 20-50mg once daily as prescribed by doctor"},
        "anxiety": {"indications": ["anxiety", "mental health"], "dosage_hint": "Take as prescribed by your doctor"},
        "fungus": {"indications": ["fungus", "fungal"], "dosage_hint": "Apply to affected area once or twice daily"},
        "fungal": {"indications": ["fungus", "fungal"], "dosage_hint": "Apply to affected area once or twice daily"},
        "rash": {"indications": ["rash", "skin", "allergy"], "dosage_hint": "Apply thin layer to affected area 2-3 times daily"},
        "skin": {"indications": ["skin", "wound"], "dosage_hint": "Apply as directed to affected area"},
        "virus": {"indications": ["virus", "viral"], "dosage_hint": "Take as directed, complete full course"},
        "viral": {"indications": ["virus", "viral"], "dosage_hint": "Take as directed, rest and fluids important"},
        "sore throat": {"indications": ["infection", "sore throat"], "dosage_hint": "Dissolve 1 lozenge every 2-3 hours as needed"},
        "throat": {"indications": ["infection", "sore throat"], "dosage_hint": "Dissolve 1 lozenge every 2-3 hours"},
        "back pain": {"indications": ["pain", "back pain"], "dosage_hint": "Apply to affected area 3-4 times daily or take oral dose as needed"},
        "muscle": {"indications": ["pain", "muscle"], "dosage_hint": "Apply to affected muscles 3-4 times daily"},
    }

    # Build target indications from symptoms
    target_indications = set()
    matched_symptoms = set()
    for word in query_tokens:
        if word in symptom_info:
            matched_symptoms.add(word)
            for ind in symptom_info[word]["indications"]:
                target_indications.add(ind.lower())

    # Score each medication
    scored = []
    for med in medicine_dataset:
        score = 0
        med_indication = (med.get("Indication") or "").lower()
        med_category = (med.get("Category") or "").lower()
        med_name = (med.get("Name") or "").lower()

        # Higher score for matched symptoms
def _search_medicine_dataset(*args, **kwargs):
    return chat_engine.search_medicine_dataset(*args, **kwargs)


def _search_final_dataset(*args, **kwargs):
    return chat_engine.search_final_dataset(*args, **kwargs)


def _get_relevant_pdf_context(*args, **kwargs):
    return chat_engine.get_relevant_pdf_context(*args, **kwargs)


def _build_local_chat_fallback(
    translated_messages: list[dict],
    input_language: str,
    relevant_pdf_context: str,
) -> str:
    analysis = _analyze_conversation_state(translated_messages)
    user_messages = analysis["user_messages"]
    latest_message = analysis["latest_message"]
    lowered = analysis["lowered"]
    combined_text = analysis["combined_text"]

    urgent_keywords = {
        "difficulty breathing",
        "shortness of breath",
        "chest pain",
        "convulsion",
        "seizure",
        "confusion",
        "unconscious",
        "severe dehydration",
        "yellow eyes",
        "dark urine",
        "blood in stool",
        "coughing blood",
    }
    if any(keyword in lowered for keyword in urgent_keywords):
        if input_language == "twi":
            return (
                "Ayoo, sorry paa sÃƒâ€°Ã¢â‚¬Âº woretwa mu saa. Saa nsÃƒâ€°Ã¢â‚¬ÂºnkyerÃƒâ€°Ã¢â‚¬Âºnne yi betumi ayÃƒâ€°Ã¢â‚¬Âº asiane, enti kÃƒâ€°Ã¢â‚¬Â  ayaresabea anaa frÃƒâ€°Ã¢â‚¬Âº emergency ntÃƒâ€°Ã¢â‚¬Âºm. "
                "WobÃƒâ€°Ã¢â‚¬Âºtumi akÃƒâ€°Ã¢â‚¬Â  ayaresabea mprempren?"
            )
        return (
            "I am really sorry you are dealing with this. Those symptoms can be dangerous, so please go to the nearest hospital or seek emergency care now. "
            "Are you able to get urgent medical help right away?"
        )

    context_line = ""
    if relevant_pdf_context:
        context_line = " I can still guide you using the local clinical guideline notes I already have available."

    has_duration = analysis["has_duration"]
    has_severity = analysis["has_severity"]
    has_multiple_symptoms = analysis["has_multiple_symptoms"]

    if input_language == "twi":
        if not has_duration:
            return (
                "Ayoo, sorry paa sÃƒâ€°Ã¢â‚¬Âº woretÃƒâ€°Ã¢â‚¬Âº saa."
                f"{context_line} "
                "Mepa wo kyÃƒâ€°Ã¢â‚¬Âºw, bere bÃƒâ€°Ã¢â‚¬Âºn na yareÃƒâ€°Ã¢â‚¬Âº no fii ase?"
            )
        if not has_severity:
            return (
                "Meda wo ase sÃƒâ€°Ã¢â‚¬Âº woka kyerÃƒâ€°Ã¢â‚¬Âº me."
                f"{context_line} "
                "Seesei, Ãƒâ€°Ã¢â‚¬ÂºreyÃƒâ€°Ã¢â‚¬Âº den anaa Ãƒâ€°Ã¢â‚¬Âºretew?"
            )
        if not has_multiple_symptoms:
            return (
                "Me te ase."
                f"{context_line} "
                "YareÃƒâ€°Ã¢â‚¬Âº yi akyi no, nsÃƒâ€°Ã¢â‚¬ÂºnkyerÃƒâ€°Ã¢â‚¬Âºnne foforo bÃƒâ€°Ã¢â‚¬Âºn na woahu bio?"
            )
        return (
            "Mehu sÃƒâ€°Ã¢â‚¬Âº wei haw wo paa."
            f"{context_line} "
            "Mepa wo kyÃƒâ€°Ã¢â‚¬Âºw, saa bere yi mu no, dÃƒâ€°Ã¢â‚¬Âºn na Ãƒâ€°Ã¢â‚¬Âºhaw wo paa sen biara?"
        )

    if not has_duration:
        return (
            f"IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢m sorry youÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢re feeling this way.{context_line} "
            "To guide you safely, when exactly did these symptoms start?"
        )

    if not has_severity:
        return (
            f"Thanks for telling me that.{context_line} "
            "Has it been getting better, worse, or staying about the same?"
        )

    if not has_multiple_symptoms:
        return (
            f"I hear you.{context_line} "
            "Besides that main symptom, what other symptoms have you noticed?"
        )

    if latest_message:
        return (
            f"That sounds really uncomfortable.{context_line} "
            "What is bothering you the most right now?"
        )

    return (
        "IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢m sorry youÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢re feeling unwell."
        f"{context_line} "
        "Please tell me when the symptoms started so I can guide you step by step."
    )


def _analyze_conversation_state(translated_messages: list[dict]) -> dict:
    user_messages = [
        message["content"].strip()
        for message in translated_messages
        if message.get("role") == "user" and message.get("content", "").strip()
    ]
    latest_message = user_messages[-1] if user_messages else ""
    combined_text = " ".join(user_messages).lower()

    has_duration = bool(
        re.search(
            r"\b(\d+\s*(hour|hours|day|days|week|weeks|month|months)|today|yesterday|since|for\s+\d+|this morning|last night)\b",
            combined_text,
        )
    )
    has_severity = bool(
        re.search(
            r"\b(mild|moderate|severe|worse|worst|better|improving|same|constant|on and off|comes and goes)\b",
            combined_text,
        )
    )
    symptom_keywords = {
        "fever", "cough", "headache", "vomiting", "nausea", "diarrhea", "stomach", "pain",
        "rash", "sore throat", "weakness", "dizziness", "body pains", "runny nose",
    }
    observed_symptoms = {symptom for symptom in symptom_keywords if symptom in combined_text}
    return {
        "user_messages": user_messages,
        "latest_message": latest_message,
        "lowered": latest_message.lower(),
        "combined_text": combined_text,
        "has_duration": has_duration,
        "has_severity": has_severity,
        "has_multiple_symptoms": len(observed_symptoms) >= 2,
    }


def _build_fallback_consult_summary(translated_messages: list[dict], input_language: str) -> str:
    analysis = _analyze_conversation_state(translated_messages)
    summary_source = " ".join(analysis["user_messages"]).strip()
    short_summary = summary_source[:1000] if summary_source else "the reported symptoms"

    if input_language == "twi":
        return (
            "Meda wo ase. Makaboa nsÃƒâ€°Ã¢â‚¬Âºm a wode ama no nyinaa ano. "
            f"NsÃƒâ€°Ã¢â‚¬Âºm titiriw a mede rekÃƒâ€°Ã¢â‚¬Â ma oduruyÃƒâ€°Ã¢â‚¬Âºfo no ne: {short_summary}. "
            "Mede bÃƒâ€°Ã¢â‚¬ÂºkÃƒâ€°Ã¢â‚¬Â ma oduruyÃƒâ€°Ã¢â‚¬Âºfo a Ãƒâ€°Ã¢â‚¬Â wÃƒâ€°Ã¢â‚¬Â  tumi ahwÃƒâ€°Ã¢â‚¬Âº mu na Ãƒâ€°Ã¢â‚¬Â nyÃƒâ€°Ã¢â‚¬Âº ayaresa ho gyinae."
        )
    return (
        "Thank you. I have gathered the key clinical details. "
        f"The summary for the pharmacist is: {short_summary}. "
        "I will send this to a licensed pharmacist to review and decide the appropriate treatment."
    )


def _should_auto_handoff_to_pharmacist(translated_messages: list[dict], ai_reply: str = "") -> bool:
    analysis = _analyze_conversation_state(translated_messages)
    combined_text = f"{analysis['combined_text']} {ai_reply.lower()}".strip()
    explicit_handoff_request = any(
        phrase in combined_text
        for phrase in {
            "send to pharmacist",
            "talk to pharmacist",
            "pharmacist review",
            "review by pharmacist",
            "case review",
        }
    )
    enough_clinical_detail = (
        analysis["has_duration"] and
        analysis["has_multiple_symptoms"] and
        (analysis["has_severity"] or len(analysis["user_messages"]) >= 3)
    )
    return explicit_handoff_request or enough_clinical_detail


def _build_pharmacist_case_details(*args, **kwargs):
    return chat_engine.build_pharmacist_case_details(*args, **kwargs)


def _extract_ai_medication_suggestions(dataset_guidance: str) -> list[dict]:
    suggestions: list[dict] = []
    guidance = (dataset_guidance or "").strip()
    if not guidance or guidance == "No dataset guidance matched.":
        return suggestions

    for section in [part.strip() for part in guidance.split(" | ") if part.strip()]:
        if section.startswith("medicine_dataset.csv:"):
            payload = section.split(":", 1)[1].strip()
            for match in re.finditer(r"([^,(]+)\s*\(([^)]*)\)", payload):
                medication = match.group(1).strip()
                metadata = [part.strip() for part in match.group(2).split(";", 1)]
                category = metadata[0] if metadata else ""
                indication = metadata[1] if len(metadata) > 1 else ""
                direction = " - ".join([part for part in [category, indication] if part]) or "Matched from medicine dataset"
                suggestions.append(
                    {
                        "source": "medicine_dataset.csv",
                        "medication": medication,
                        "direction": direction,
                        "label": f"{medication}: {direction}",
                    }
                )
        elif section.startswith("final.csv:"):
            payload = section.split(":", 1)[1].strip()
            for item in [entry.strip() for entry in payload.split(",") if entry.strip()]:
                disease, arrow, medication = item.partition("->")
                if not arrow:
                    continue
                disease_name = disease.strip()
                medication_name = medication.strip()
                direction = f"Matched condition: {disease_name}" if disease_name else "Matched from final dataset"
                suggestions.append(
                    {
                        "source": "final.csv",
                        "medication": medication_name,
                        "direction": direction,
                        "label": f"{medication_name}: {direction}",
                    }
                )

    unique_suggestions: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for suggestion in suggestions:
        key = (
            suggestion.get("source", "").lower(),
            suggestion.get("medication", "").strip().lower(),
        )
        if not suggestion.get("medication") or key in seen:
            continue
        seen.add(key)
        unique_suggestions.append(suggestion)
    return unique_suggestions


def _get_default_ai_medication(rx: models.PrescriptionHistory) -> str:
    dataset_guidance = ""
    for chunk in (rx.details or "").split(" || "):
        section = chunk.strip()
        if section.lower().startswith("dataset guidance for pharmacist review only:"):
            dataset_guidance = section.split(":", 1)[1].strip()
            break
    suggestions = _extract_ai_medication_suggestions(dataset_guidance)
    return suggestions[0]["medication"] if suggestions else ""





def _log_case_event(*args, **kwargs):
    return chat_engine.log_case_event(*args, **kwargs)


def _create_case_record(*args, **kwargs):
    return chat_engine.create_case_record(*args, **kwargs)


def _ensure_db_migrations():
    inspector = inspect(engine)
    
    # Migrations for 'users' table
    if inspector.has_table("users"):
        columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "username" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR"))
            conn.execute(text("UPDATE users SET username = email WHERE username IS NULL OR TRIM(username) = ''"))
            # SQLite supports IF NOT EXISTS for indexes
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))

    # Migrations for 'emergencies' table
    if inspector.has_table("emergencies"):
        columns = {column["name"] for column in inspector.get_columns("emergencies")}
        if "phone_alt" not in columns and "phone2" in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE emergencies RENAME COLUMN phone2 TO phone_alt"))

    if inspector.has_table("pharmacists"):
        columns = {column["name"] for column in inspector.get_columns("pharmacists")}
        with engine.begin() as conn:
            if "full_name" not in columns:
                conn.execute(text("ALTER TABLE pharmacists ADD COLUMN full_name VARCHAR DEFAULT ''"))
            if "location" not in columns:
                conn.execute(text("ALTER TABLE pharmacists ADD COLUMN location VARCHAR DEFAULT ''"))
            if "is_verified" not in columns:
                conn.execute(text("ALTER TABLE pharmacists ADD COLUMN is_verified BOOLEAN DEFAULT 0"))

    if inspector.has_table("prescription_history"):
        columns = {column["name"] for column in inspector.get_columns("prescription_history")}
        with engine.begin() as conn:
            if "pharmacist_id" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN pharmacist_id INTEGER"))
            if "patient_message" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN patient_message TEXT DEFAULT ''"))
            if "case_summary" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN case_summary TEXT DEFAULT ''"))
            if "ai_summary" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN ai_summary TEXT DEFAULT ''"))
            if "pharmacist_feedback" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN pharmacist_feedback TEXT DEFAULT ''"))
            if "referral_advice" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN referral_advice TEXT DEFAULT ''"))
            if "follow_up_instructions" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN follow_up_instructions TEXT DEFAULT ''"))
            if "urgency_level" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN urgency_level VARCHAR DEFAULT 'routine'"))
            if "follow_up_status" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN follow_up_status VARCHAR DEFAULT 'awaiting_review'"))
            if "symptom_area" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN symptom_area VARCHAR DEFAULT ''"))
            if "symptom_type" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN symptom_type VARCHAR DEFAULT ''"))
            if "delivery_address" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN delivery_address VARCHAR DEFAULT ''"))
            if "delivery_phone" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN delivery_phone VARCHAR DEFAULT ''"))
            if "delivery_notes" not in columns:
                conn.execute(text("ALTER TABLE prescription_history ADD COLUMN delivery_notes TEXT DEFAULT ''"))



def _normalize_username(value: str) -> str:
    username = re.sub(r"[^a-z0-9_.-]", "", value.strip().lower())
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    return username


def _build_unique_username(db: Session, base_value: str, exclude_user_id: int | None = None) -> str:
    base_username = _normalize_username(base_value or "user")
    candidate = base_username
    suffix = 1

    while True:
        query = db.query(models.User).filter(models.User.username == candidate)
        if exclude_user_id is not None:
            query = query.filter(models.User.id != exclude_user_id)
        if not query.first():
            return candidate
        suffix += 1
        candidate = f"{base_username}{suffix}"


_ensure_db_migrations()


def _ensure_user_profile_records(db: Session, user_id: int, first_name: str = "", last_name: str = ""):
    if not db.query(models.Profile).filter(models.Profile.user_id == user_id).first():
        db.add(models.Profile(user_id=user_id, first_name=first_name, last_name=last_name))
    if not db.query(models.Medical).filter(models.Medical.user_id == user_id).first():
        db.add(models.Medical(user_id=user_id))
    if not db.query(models.Emergency).filter(models.Emergency.user_id == user_id).first():
        db.add(models.Emergency(user_id=user_id))
        db.commit()


def _serialize_case(rx: models.PrescriptionHistory) -> dict:
    patient = rx.owner
    patient_profile = patient.profile if patient else None
    pharmacist = rx.reviewer
    support_sections = {
        "ai_intake_summary": (rx.ai_summary or "").strip(),
        "recent_patient_statements": "",
        "dataset_guidance": "",
        "pdf_guidance": "",
        "clinical_profile": "",
        "fast_delivery_note": "",
    }
    if "### AI CLINICAL INTAKE SUMMARY" in (rx.details or ""):
        # Handling the new detailed Markdown format
        details_text = rx.details or ""
        support_sections["ai_intake_summary"] = (rx.ai_summary or "").strip()
        
        # Simple regex or split for the newer format
        if "**Recent patient statements:**" in details_text:
            support_sections["recent_patient_statements"] = details_text.split("**Recent patient statements:**")[1].split("\n")[0].strip()
        elif "**Full patient conversation history:**" in details_text:
            support_sections["recent_patient_statements"] = details_text.split("**Full patient conversation history:**")[1].split("\n")[0].strip()

        if "**Dataset guidance for review:**" in details_text:
            support_sections["dataset_guidance"] = details_text.split("**Dataset guidance for review:**")[1].split("\n")[0].strip()
        if "**PDF guidance for review:**" in details_text:
            support_sections["pdf_guidance"] = details_text.split("**PDF guidance for review:**")[1].split("\n")[0].strip()
        if "Patient clinical profile for pharmacist review:" in details_text:
            support_sections["clinical_profile"] = details_text.split("Patient clinical profile for pharmacist review:")[1].strip()
    else:
        # Legacy parsing
        for chunk in (rx.details or "").split(" || "):
            section = chunk.strip()
            lowered = section.lower()
            if lowered.startswith("ai intake summary:"):
                support_sections["ai_intake_summary"] = section.split(":", 1)[1].strip()
            elif lowered.startswith("recent patient statements:"):
                support_sections["recent_patient_statements"] = section.split(":", 1)[1].strip()
            elif lowered.startswith("dataset guidance for pharmacist review only:"):
                support_sections["dataset_guidance"] = section.split(":", 1)[1].strip()
            elif lowered.startswith("pdf guidance for pharmacist review only:"):
                support_sections["pdf_guidance"] = section.split(":", 1)[1].strip()
            elif lowered.startswith("patient clinical profile for pharmacist review:"):
                support_sections["clinical_profile"] = section.split(":", 1)[1].strip()

    urgency_hint = {
        "urgent": "Prioritize immediate pharmacist action and rapid delivery or referral review.",
        "priority": "Expedite pharmacist review and prepare delivery if treatment is appropriate.",
        "routine": "Use the AI intake and dataset guidance to speed up standard pharmacist review.",
    }
    support_sections["fast_delivery_note"] = urgency_hint.get(rx.urgency_level or "routine", urgency_hint["routine"])
    ai_medication_suggestions = _extract_ai_medication_suggestions(support_sections["dataset_guidance"])
    current_drug_name = rx.drug_name if rx.drug_name != "Pharmacist review required" else None

    return {
        "id": rx.id,
        "drug_name": current_drug_name,
        "details": rx.details,
        "patient_message": rx.patient_message,
        "case_summary": rx.case_summary,
        "ai_summary": rx.ai_summary,
        "pharmacist_feedback": rx.pharmacist_feedback,
        "referral_advice": rx.referral_advice,
        "follow_up_instructions": rx.follow_up_instructions,
        "urgency_level": rx.urgency_level,
        "follow_up_status": rx.follow_up_status,
        "symptom_area": rx.symptom_area,
        "symptom_type": rx.symptom_type,
        "status": rx.status,
        "delivery_address": rx.delivery_address,
        "delivery_phone": rx.delivery_phone,
        "delivery_notes": rx.delivery_notes,
        "created_at": rx.created_at.isoformat() if rx.created_at else None,
        "pharmacist_support": support_sections,
        "ai_medication_suggestions": ai_medication_suggestions,
        "patient": {
            "id": patient.id if patient else None,
            "username": patient.username if patient else "",
            "email": patient.email if patient else "",
            "full_name": (
                f"{patient_profile.first_name} {patient_profile.last_name}".strip()
                if patient_profile else ""
            ),
            "phone": patient_profile.phone if patient_profile else "",
            "city": patient_profile.city if patient_profile else "",
        },
        "pharmacist": {
            "id": pharmacist.id,
            "name": pharmacist.full_name or pharmacist.username,
            "email": pharmacist.email,
            "location": pharmacist.location,
        } if pharmacist else None,
        "events": [
            {
                "id": event.id,
                "actor_role": event.actor_role,
                "actor_name": event.actor_name,
                "action": event.action,
                "note": event.note,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in sorted(rx.events, key=lambda item: item.created_at or item.id)
        ],
    }


def _serialize_pharmacist(pharmacist: models.Pharmacist) -> dict:
    return {
        "id": pharmacist.id,
        "username": pharmacist.username,
        "email": pharmacist.email,
        "full_name": pharmacist.full_name,
        "license_number": pharmacist.license_number,
        "location": pharmacist.location,
        "is_verified": pharmacist.is_verified,
    }


def _get_admin_seed_config(db: Session) -> tuple[str, str, str] | None:
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    raw_admin_username = os.getenv("ADMIN_USERNAME", "").strip()
    admin_username = _normalize_username(raw_admin_username) if raw_admin_username else ""
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

    if admin_password:
        if not admin_email and admin_username:
            admin_email = f"{admin_username}@bisarx.local"
        if not admin_username and admin_email:
            admin_username = _build_unique_username(db, admin_email.split("@")[0] or "admin")
        if admin_email and admin_username:
            return admin_email, admin_username, admin_password

    # Local fallback so the app always has a predictable admin login in development.
    env_name = os.getenv("ENV", os.getenv("APP_ENV", "development")).strip().lower()
    is_production = env_name in {"prod", "production"}
    if is_production:
        return None

    return ("admin@bisarx.local", "admin", "admin12345")


def _ensure_admin_account(db: Session):
    seed_config = _get_admin_seed_config(db)
    if not seed_config:
        return
    admin_email, admin_username, admin_password = seed_config

    admin = db.query(models.User).filter(models.User.email == admin_email).first()
    if not admin:
        admin = models.User(
            username=_build_unique_username(db, admin_username or admin_email.split("@")[0] or "admin"),
            email=admin_email,
            hashed_password=auth.get_password_hash(admin_password),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        _ensure_user_profile_records(db, admin.id, "System", "Admin")
        return

    updated = False
    if not admin.username:
        admin.username = _build_unique_username(db, admin_username or "admin", exclude_user_id=admin.id)
        updated = True
    if not admin.is_admin:
        admin.is_admin = True
        updated = True
    if not auth.verify_password(admin_password, admin.hashed_password):
        admin.hashed_password = auth.get_password_hash(admin_password)
        updated = True
    if updated:
        db.commit()


bootstrap_db = SessionLocal()
try:
    _ensure_admin_account(bootstrap_db)
finally:
    bootstrap_db.close()


@app.get("/api/auth/google/login")
async def google_login(request: Request):
    if not os.getenv("GOOGLE_CLIENT_ID") or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/google/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        env_exists = (BASE_DIR / ".env").exists()
        google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        key_prefix = google_client_id[:4] if google_client_id else "N/A"
        detail = f"Google OAuth failed: {str(e)} | KeyPrefix: {key_prefix} | EnvExists: {env_exists} | BaseDir: {BASE_DIR}"
        raise HTTPException(status_code=500, detail=detail)

    user_info = token.get("userinfo")
    if not user_info:
        try:
            user_info = await oauth.google.parse_id_token(request, token)
        except Exception:
            user_info = None

    if not user_info:
        raise HTTPException(status_code=400, detail="Unable to fetch Google user info")

    email = user_info.get("email")
    first_name = user_info.get("given_name", "")
    last_name = user_info.get("family_name", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        placeholder_hash = auth.get_password_hash(os.urandom(16).hex())
        user = models.User(
            username=_build_unique_username(db, email.split("@")[0]),
            email=email,
            hashed_password=placeholder_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.username:
        user.username = _build_unique_username(db, email.split("@")[0], exclude_user_id=user.id)
        db.commit()
        db.refresh(user)

    _ensure_user_profile_records(db, user.id, first_name, last_name)

    access_token = auth.create_access_token(data={"sub": user.email})
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000")
    separator = "&" if "?" in frontend_url else "?"
    return RedirectResponse(url=f"{frontend_url}{separator}token={access_token}")


@app.post("/api/auth/register", response_model=schemas.Token)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    username = _normalize_username(user_in.username)

    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already registered")

    if db.query(models.User).filter(models.User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = auth.get_password_hash(user_in.password)
    user = models.User(username=username, email=user_in.email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)

    _ensure_user_profile_records(db, user.id, user_in.first_name, user_in.last_name)

    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    login_value = form_data.username.strip().lower()
    user = db.query(models.User).filter(
        or_(models.User.username == login_value, models.User.email == login_value)
    ).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token_payload = {"sub": user.email}
    if user.is_admin:
        token_payload["role"] = "admin"
    access_token = auth.create_access_token(data=token_payload)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/pharmacist/login", response_model=schemas.Token)
def pharmacist_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        login_value = form_data.username.strip().lower()
        pharmacist = db.query(models.Pharmacist).filter(
            or_(
                models.Pharmacist.username == login_value,
                models.Pharmacist.email == login_value,
                models.Pharmacist.license_number == login_value.upper()
            )
        ).first()

        
        if not pharmacist:
            print(f"LOGIN FAIL: Pharmacist not found for '{login_value}'")
            raise HTTPException(status_code=400, detail="Incorrect pharmacist username or password")
            
        if not auth.verify_password(form_data.password, pharmacist.hashed_password):
            print(f"LOGIN FAIL: Password mismatch for pharmacist '{login_value}'")
            raise HTTPException(status_code=400, detail="Incorrect pharmacist username or password")
            
        access_token = auth.create_access_token(data={"sub": pharmacist.email, "role": "pharmacist"})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        if not isinstance(e, HTTPException):
            print(f"ERROR in pharmacist_login: {str(e)}")
            import traceback
            traceback.print_exc()
        raise e



@app.post("/api/auth/pharmacist/register", response_model=schemas.Token)
def pharmacist_register(pharmacist_in: schemas.PharmacistCreate, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=403,
        detail="Pharmacist accounts can only be created by an admin.",
    )


@app.get("/api/session")
def get_session(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return {"role": "guest", "display_name": ""}

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return {"role": "guest", "display_name": ""}

    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    except auth.JWTError:
        return {"role": "guest", "display_name": ""}

    email = payload.get("sub")
    role = payload.get("role") or "user"
    if not email:
        return {"role": "guest", "display_name": ""}

    if role == "pharmacist":
        pharmacist = db.query(models.Pharmacist).filter(models.Pharmacist.email == email).first()
        if not pharmacist:
            return {"role": "guest", "display_name": ""}
        return {
            "role": "pharmacist",
            "display_name": pharmacist.full_name or pharmacist.username or pharmacist.email,
            "pharmacist_id": pharmacist.id,
        }

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"role": "guest", "display_name": ""}

    resolved_role = "admin" if user.is_admin or role == "admin" else "user"
    display_name = user.username or user.email
    if user.profile:
        full_name = f"{user.profile.first_name} {user.profile.last_name}".strip()
        if full_name:
            display_name = full_name

    return {"role": resolved_role, "display_name": display_name, "user_id": user.id}


@app.get("/api/profile")
def get_profile(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "profile": current_user.profile,
        "medical": current_user.medical,
        "conditions": [c.name for c in current_user.conditions],
        "allergies": [a.name for a in current_user.allergies],
        "medications": current_user.medications,
        "emergency": current_user.emergency,
        "prescriptions": current_user.prescriptions,
    }


@app.get("/api/profile/reports", response_model=List[schemas.Prescription])
def get_profile_reports(current_user: models.User = Depends(auth.get_current_user)):
    return current_user.prescriptions

def _background_generate_summary(case_id: int, translated_messages: list[dict]):

    """Background task to generate and update a detailed AI clinical summary."""
    db = SessionLocal()
    try:
        case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
        if not case:
            return

        # Generate the detailed report (this can take 5-15 seconds)
        detailed_report = chat_engine.generate_detailed_summary(translated_messages)
        
        # Update the case record
        case.ai_summary = detailed_report[:2000]
        
        # ALSO update the details field which is what the pharmacist primarily sees
        # We rebuild the full clinical details block so it shows the AI analysis + history
        patient_msgs = [m["content"] for m in translated_messages if m["role"] == "user"]
        symptom_history = " | ".join(patient_msgs)
        
        case.details = (
            f"### AI CLINICAL INTAKE SUMMARY\n{detailed_report}\n\n"
            f"--- \n"
            f"**Full patient conversation history:** {symptom_history or 'Not captured'} \n"
            f"**Dataset guidance for review:** (Available in Intake) \n"
            f"**PDF guidance for review:** (Available in Intake) \n"
            f" || Patient clinical profile for pharmacist review: {chat_engine.build_patient_clinical_profile_snapshot(db, case.user_id)}"

        )

        # Update the queue summary to be more professional
        # Try to find the "SUMMARY:" line we instructed the AI to provide
        lines = detailed_report.split("\n")
        new_case_summary = ""
        for line in lines:
            if line.upper().startswith("SUMMARY:"):
                new_case_summary = line.split(":", 1)[1].strip()
                break
        
        if not new_case_summary:
            # Fallback to the patient msg summary if AI didn't provide the SUMMARY line
            new_case_summary = "Professional review of " + ", ".join(patient_msgs[-2:])
            
        case.case_summary = new_case_summary[:500]

        
        # Update urgency based on full details
        case.urgency_level = chat_engine.infer_urgency_level(f"{new_case_summary} {detailed_report}")

        
        db.commit()
    except Exception as e:
        print(f"Background summary generation failed for case {case_id}: {e}")
    finally:
        db.close()


@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat(


    request: schemas.ChatRequest, 
    background_tasks: BackgroundTasks, 
    current_user: models.User = Depends(get_optional_user), 
    db: Session = Depends(get_db)
):
    # If user is not logged in, they can still use chat (guest mode)
    user_id = current_user.id if current_user else None
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Use skip_summary=True to prevent freezing the request while the detailed clinical report is generated
    result = chat_engine.process_chat(
        messages=messages, 
        db=db, 
        user_id=user_id, 
        image_data=request.image_data,
        case_id=request.case_id,
        skip_summary=True 
    )

    if result.get("case_id"):
        case_id = result.get("case_id")
        # Run detailed summary generation in the background to prevent UI freeze
        background_tasks.add_task(_background_generate_summary, case_id, messages)
        
        # Notify pharmacists of new case
        background_tasks.add_task(
            ws_manager.notify_pharmacists, 
            {"type": "case_created", "case_id": case_id}
        )


    return {
        "reply": result["reply"],
        "drugs": result["drugs"],
        "consulting": result["consulting"],
        "error": result["error"],
        "case_id": result.get("case_id"),
    }


@app.post("/api/chat/stream")
async def chat_stream(
    request: schemas.ChatRequest,
    current_user: models.User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Streaming SSE chat endpoint – delivers AI tokens progressively, then creates a case if needed."""
    from fastapi.responses import StreamingResponse as _SR
    user_id = current_user.id if current_user else None
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    async def event_generator():
        try:
            stream = openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=chat_engine.build_system_messages(messages, image_data=request.image_data),
                stream=True,
                max_tokens=900,
                temperature=0.4,
            )
            full_reply = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_reply += delta
                    yield f"data: {json.dumps({'token': delta})}\n\n"

            # --- Post-stream: detect handoff and create case ---
            is_consulting = "[CONSULT_READY]" in full_reply
            if not is_consulting:
                is_consulting = chat_engine.should_auto_handoff_to_pharmacist(
                    [{"role": m.role, "content": m.content} for m in request.messages],
                    full_reply
                )

            case_id = None
            if is_consulting:
                # Strip the marker from the reply sent to patient
                clean_reply = full_reply.replace("[CONSULT_READY]", "").strip()
                if not clean_reply:
                    clean_reply = chat_engine.build_fallback_consult_summary(
                        [{"role": m.role, "content": m.content} for m in request.messages],
                        "en",
                    )
                # Build search context for drug matching
                all_user_text = " ".join(
                    m.content for m in request.messages if m.role == "user"
                ) + " " + clean_reply
                matched_drugs = chat_engine.search_medicine_dataset(all_user_text, limit=4)
                final_matches = chat_engine.search_final_dataset(all_user_text, limit=4)
                relevant_pdf = chat_engine.get_relevant_pdf_context(
                    [{"role": m.role, "content": m.content} for m in request.messages]
                )
                case = chat_engine.create_case_record(
                    db=db,
                    user_id=user_id,
                    translated_messages=[{"role": m.role, "content": m.content} for m in request.messages],
                    ai_summary=clean_reply,
                    matched_drugs=matched_drugs,
                    final_matches=final_matches,
                    relevant_pdf_context=relevant_pdf,
                    actor_note="Case created from streaming triage handoff.",
                )
                case_id = case.id
                full_reply = clean_reply + (
                    "\n\nI have prepared your case summary and sent it to a licensed pharmacist for review. "
                    "The pharmacist will assess and decide the right treatment."
                )
                # Notify patient if logged in
                if user_id:
                    try:
                        await ws_manager.notify_user(user_id, {
                            "type": "case_created",
                            "case_id": case_id,
                            "message": "Your case has been sent to a pharmacist.",
                        })
                    except Exception:
                        pass
                
                # Notify pharmacists of new case
                try:
                    await ws_manager.notify_pharmacists({
                        "type": "case_created",
                        "case_id": case_id
                    })
                except Exception:
                    pass

            yield f"data: {json.dumps({'done': True, 'full': full_reply, 'consulting': is_consulting, 'case_id': case_id})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return _SR(event_generator(), media_type="text/event-stream")


@app.websocket("/ws/patient/{user_id}")
async def patient_websocket(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time patient notifications."""
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)


@app.websocket("/ws/case/{case_id}")
async def case_websocket(websocket: WebSocket, case_id: int):
    """WebSocket endpoint for real-time case updates (guests and logged-in users)."""
    await ws_manager.connect_case(websocket, case_id)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect_case(websocket, case_id)


@app.websocket("/ws/pharmacist")
async def pharmacist_websocket(websocket: WebSocket):
    """WebSocket endpoint for pharmacist dashboard real-time updates."""
    await ws_manager.connect_pharmacist(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect_pharmacist(websocket)


@app.get("/api/cases/public")
def get_public_pending_cases(db: Session = Depends(get_db)):
    """Public endpoint to view pending cases for display on pharmacist dashboard without login."""
    pending_cases = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.status == "Pending",
        models.PrescriptionHistory.pharmacist_id.is_(None),
    ).order_by(
        models.PrescriptionHistory.urgency_level.desc(),
        models.PrescriptionHistory.created_at.desc()
    ).limit(100).all()
    
    return {
        "cases": [_serialize_case(case) for case in pending_cases],
        "total": len(pending_cases),
    }


@app.get("/api/cases/guest/{case_id}")
def get_guest_case_status(case_id: int, db: Session = Depends(get_db)):
    """Check status of a guest-submitted case."""
    case = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.id == case_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {
        "case_id": case.id,
        "status": case.status,
        "follow_up_status": case.follow_up_status,
        "pharmacist_feedback": case.pharmacist_feedback,
        "drug_name": case.drug_name if case.drug_name != "Pharmacist review required" else None,
        "referral_advice": case.referral_advice,
        "follow_up_instructions": case.follow_up_instructions,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


@app.get("/api/pharmacist/dashboard")
def pharmacist_dashboard(
    current_pharmacist: models.Pharmacist = Depends(get_current_pharmacist),
    db: Session = Depends(get_db),
):
    pending_cases = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.status == "Pending",
        models.PrescriptionHistory.pharmacist_id.is_(None),
    ).order_by(models.PrescriptionHistory.created_at.desc()).all()

    assigned_cases = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.pharmacist_id == current_pharmacist.id,
    ).order_by(models.PrescriptionHistory.created_at.desc()).all()

    completed_case_ids = {
        c.id
        for c in assigned_cases
        if c.follow_up_status == "feedback_sent" or c.status in {"Reviewed", "Ordered", "Delivered", "Completed"}
    }
    in_review_cases = [c for c in assigned_cases if c.id not in completed_case_ids]
    completed_cases = [c for c in assigned_cases if c.id in completed_case_ids]

    return {
        "pharmacist": _serialize_pharmacist(current_pharmacist),
        "stats": {
            "assigned_cases": len(in_review_cases),
            "in_review_cases": len(in_review_cases),
            "completed_cases": len(completed_cases),
            "pending_cases": len(pending_cases),
        },
        "pending_cases": [_serialize_case(case) for case in pending_cases],
        "assigned_cases": [_serialize_case(case) for case in in_review_cases],
        "in_review_cases": [_serialize_case(case) for case in in_review_cases],
        "completed_cases": [_serialize_case(case) for case in completed_cases],
    }


@app.get("/api/pharmacists/available")
@app.get("/api/clinicians/available")
def available_pharmacists(db: Session = Depends(get_db)):
    pharmacists = db.query(models.Pharmacist).filter(models.Pharmacist.is_verified == True).order_by(
        models.Pharmacist.full_name.asc(), models.Pharmacist.username.asc()
    ).all()
    return {"pharmacists": [_serialize_pharmacist(pharmacist) for pharmacist in pharmacists]}


@app.post("/api/pharmacist/cases/{case_id}/accept")
def pharmacist_accept_case(
    case_id: int,
    current_pharmacist: models.Pharmacist = Depends(get_current_pharmacist),
    db: Session = Depends(get_db),
):
    case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != "Pending":
        raise HTTPException(status_code=400, detail="Case is no longer available to accept")
    if case.pharmacist_id and case.pharmacist_id != current_pharmacist.id:
        raise HTTPException(status_code=409, detail="Another pharmacist has already accepted this case")

    case.pharmacist_id = current_pharmacist.id
    case.status = "In Review"
    case.follow_up_status = "under_review"
    _log_case_event(
        case,
        "pharmacist",
        current_pharmacist.full_name or current_pharmacist.username,
        "case_accepted",
        "Pharmacist accepted the shared case queue item.",
    )
    db.commit()
    db.refresh(case)
    return {"status": "success", "case": _serialize_case(case)}


@app.post("/api/pharmacist/review/{case_id}")
def pharmacist_review_case(
    case_id: int,
    review: schemas.PharmacistReviewRequest,
    background_tasks: BackgroundTasks,
    current_pharmacist: models.Pharmacist = Depends(get_current_pharmacist),
    db: Session = Depends(get_db),
):
    case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status == "Pending" and case.pharmacist_id is None:
        case.pharmacist_id = current_pharmacist.id
        case.status = "In Review"
        case.follow_up_status = "under_review"
        _log_case_event(
            case,
            "pharmacist",
            current_pharmacist.full_name or current_pharmacist.username,
            "case_accepted",
            "Pharmacist accepted the case while submitting a review.",
        )

    if case.pharmacist_id != current_pharmacist.id:
        raise HTTPException(status_code=403, detail="This case is not assigned to you")

    # Multi-drug handling
    if review.drugs_list and len(review.drugs_list) > 0:
        drugs = [d.get("name", "").strip() for d in review.drugs_list if d.get("name")]
        points = [f"{d.get('name')}: {d.get('point')}" for d in review.drugs_list if d.get("name")]
        case.drug_name = ", ".join(drugs)
        case.pharmacist_feedback = "\n".join(points)
    else:
        case.drug_name = (review.drug or "Pharmacist review completed").strip()
        case.pharmacist_feedback = review.advice.strip()

    case.referral_advice = (review.referral_advice or "").strip()
    case.follow_up_instructions = (review.follow_up_instructions or "").strip()
    case.follow_up_status = "feedback_sent"
    case.details = (
        f"{case.details}\n\n"
        f"Prescription: {case.drug_name}\n"
        f"Dosage: {case.pharmacist_feedback}\n"
        f"Interaction: {case.referral_advice or 'None'}"
    )
    case.status = review.status
    _log_case_event(
        case,
        "pharmacist",
        current_pharmacist.full_name or current_pharmacist.username,
        "review_submitted",
        case.pharmacist_feedback,
    )
    db.commit()
    db.refresh(case)
    serialized = _serialize_case(case)
    # Notify patient via WebSocket (non-blocking background task)
    notification = {
        "type": "case_updated",
        "case_id": case.id,
        "drug_name": case.drug_name,
        "pharmacist_feedback": case.pharmacist_feedback,
        "referral_advice": case.referral_advice,
        "follow_up_instructions": case.follow_up_instructions,
        "status": case.status,
    }
    # Notify logged-in user if applicable
    if case.user_id:
        background_tasks.add_task(ws_manager.notify_user, case.user_id, notification)
    # Always notify by case_id (covers guests)
    background_tasks.add_task(ws_manager.notify_case, case.id, notification)

    return {"status": "success", "case": serialized}


@app.post("/api/cases/{case_id}/ai-suggest")
def case_ai_suggest(
    case_id: int,
    current_pharmacist: models.Pharmacist = Depends(get_current_pharmacist),
    db: Session = Depends(get_db),
):
    """AI suggestion to help pharmacist fill in review form fields."""
    case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    context = (
        f"Case summary: {case.case_summary or 'Not provided'}\n"
        f"Patient message: {case.patient_message or 'Not provided'}\n"
        f"AI intake summary: {case.ai_summary or 'Not provided'}\n"
        f"Symptom area: {case.symptom_area or 'General'}\n"
        f"Urgency: {case.urgency_level or 'routine'}\n"
    )

    prompt = (
        "You are a clinical pharmacist AI assistant. Based on the case context below, "
        "suggest the most appropriate pharmacist response. Output ONLY valid JSON with these keys: "
        "drug_name, pharmacist_feedback (2-3 detailed points for the patient including dosage and usage instructions), "
        "referral_advice (or empty string), follow_up_instructions (or empty string), dosage.\n\nCase:\n" + context
    )

    try:
        response = openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        suggestion = json.loads(raw)
    except Exception as exc:
        suggestion = {
            "drug_name": _get_default_ai_medication(case) or "",
            "pharmacist_feedback": "Please review the case carefully and provide appropriate clinical advice.",
            "referral_advice": "",
            "follow_up_instructions": "Monitor and return if symptoms worsen.",
            "dosage": "As directed",
        }

    return {"suggestion": suggestion}


@app.get("/api/admin/dashboard")
def admin_dashboard(
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    pharmacists = db.query(models.Pharmacist).order_by(models.Pharmacist.full_name.asc(), models.Pharmacist.username.asc()).all()
    all_cases_raw = db.query(models.PrescriptionHistory).all()
    urgency_rank = {"urgent": 0, "priority": 1, "routine": 2}
    status_rank = {"Pending": 0, "In Review": 1, "Reviewed": 2, "Ordered": 3, "Delivered": 4, "Completed": 5}
    cases = sorted(all_cases_raw, key=lambda c: (
        urgency_rank.get(c.urgency_level or "routine", 2),
        status_rank.get(c.status or "Pending", 0),
        -(c.created_at.timestamp() if c.created_at else 0)
    ))
    all_users = db.query(models.User).order_by(models.User.id.desc()).all()

    total_cases = len(all_cases_raw)
    pending_cases = sum(1 for c in all_cases_raw if c.status == "Pending")
    in_review_cases = sum(1 for c in all_cases_raw if c.status == "In Review")
    reviewed_cases = sum(1 for c in all_cases_raw if c.status in {"Reviewed", "Ordered", "Delivered"})
    users_with_profiles = db.query(models.User).join(models.Profile).count()

    return {
        "stats": {
            "total_users": len(all_users),
            "total_pharmacists": len(pharmacists),
            "pending_cases": pending_cases,
            "in_review_cases": in_review_cases,
            "reviewed_cases": reviewed_cases,
            "total_cases": total_cases,
            "verified_pharmacists": len([p for p in pharmacists if p.is_verified]),
            "users_with_profiles": users_with_profiles,
            "waitlist_entries": db.query(models.WaitlistEntry).count(),
        },
        "pharmacists": [_serialize_pharmacist(pharmacist) for pharmacist in pharmacists],
        "cases": [_serialize_case(case) for case in cases],
        "recent_users": [_serialize_user(u) for u in all_users[:20]],
        "all_users": [_serialize_user(u) for u in all_users],
    }



@app.get("/api/admin/insights")
def admin_insights(
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """AI-generated system insights for admin overview."""
    all_cases = db.query(models.PrescriptionHistory).all()
    total_cases = len(all_cases)
    pending = sum(1 for c in all_cases if c.status == "Pending")
    urgent = sum(1 for c in all_cases if (c.urgency_level or "") == "urgent")
    reviewed = sum(1 for c in all_cases if c.status in {"Reviewed", "Ordered", "Delivered"})
    total_users = db.query(models.User).count()
    pharmacists = db.query(models.Pharmacist).filter(models.Pharmacist.is_verified == True).count()
    resolution_rate = round((reviewed / total_cases * 100) if total_cases else 0, 1)

    prompt = (
        f"You are a clinical operations AI advisor for BisaRx, a Ghanaian community pharmacy platform. "
        f"Current stats: {total_cases} total cases, {pending} pending, {urgent} urgent, {reviewed} reviewed, "
        f"{total_users} patients, {pharmacists} active pharmacists, {resolution_rate}% resolution rate. "
        f"In 3 concise bullet points, give the admin specific, actionable recommendations to improve system performance."
    )
    try:
        response = openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.5,
        )
        insights_text = response.choices[0].message.content.strip()
    except Exception:
        insights_text = (
            f"\u2022 {pending} cases pending. Assign pharmacists promptly.\n"
            f"\u2022 Resolution rate is {resolution_rate}%. Target 90%+ for optimal care.\n"
            f"\u2022 {urgent} urgent cases need immediate attention."
        )
    return {
        "stats": {
            "total_cases": total_cases, "pending": pending, "urgent": urgent,
            "reviewed": reviewed, "resolution_rate": resolution_rate,
            "total_users": total_users, "active_pharmacists": pharmacists,
        },
        "insights": insights_text,
    }



def _serialize_user(user: models.User) -> dict:
    profile = user.profile or {}
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "first_name": profile.first_name if profile else "",
        "last_name": profile.last_name if profile else "",
        "phone": profile.phone if profile else "",
        "city": profile.city if profile else "",
    }


@app.get("/api/admin/users")
def admin_list_users(
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = db.query(models.User).order_by(models.User.id.desc()).all()
    return {"users": [_serialize_user(u) for u in users]}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete related records
    db.query(models.Profile).filter(models.Profile.user_id == user_id).delete()
    db.query(models.Medical).filter(models.Medical.user_id == user_id).delete()
    db.query(models.Emergency).filter(models.Emergency.user_id == user_id).delete()
    db.query(models.Condition).filter(models.Condition.user_id == user_id).delete()
    db.query(models.Allergy).filter(models.Allergy.user_id == user_id).delete()
    db.query(models.Medication).filter(models.Medication.user_id == user_id).delete()
    db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.user_id == user_id).delete()
    
    db.delete(user)
    db.commit()
    return {"status": "success"}


@app.get("/api/admin/stats")
def admin_system_stats(
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get detailed system statistics"""
    total_users = db.query(models.User).count()
    total_pharmacists = db.query(models.Pharmacist).count()
    verified_pharmacists = db.query(models.Pharmacist).filter(models.Pharmacist.is_verified == True).count()
    
    # Case stats
    total_cases = db.query(models.PrescriptionHistory).count()
    pending_cases = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.status == "Pending").count()
    in_review_cases = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.status == "In Review").count()
    completed_cases = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.status.in_(["Reviewed", "Ordered", "Delivered"])
    ).count()
    
    # Cases per pharmacist
    cases_per_pharmacist = []
    pharmacists = db.query(models.Pharmacist).all()
    for p in pharmacists:
        assigned = db.query(models.PrescriptionHistory).filter(
            models.PrescriptionHistory.pharmacist_id == p.id
        ).count()
        completed = db.query(models.PrescriptionHistory).filter(
            models.PrescriptionHistory.pharmacist_id == p.id,
            models.PrescriptionHistory.status.in_(["Reviewed", "Ordered", "Delivered"])
        ).count()
        cases_per_pharmacist.append({
            "id": p.id,
            "name": p.full_name or p.username,
            "assigned": assigned,
            "completed": completed,
        })
    
    return {
        "users": {
            "total": total_users,
            "admins": db.query(models.User).filter(models.User.is_admin == True).count(),
        },
        "pharmacists": {
            "total": total_pharmacists,
            "verified": verified_pharmacists,
            "pending": total_pharmacists - verified_pharmacists,
        },
        "cases": {
            "total": total_cases,
            "pending": pending_cases,
            "in_review": in_review_cases,
            "completed": completed_cases,
        },
        "cases_per_pharmacist": cases_per_pharmacist,
    }


@app.post("/api/admin/pharmacists")
def admin_create_pharmacist(
    pharmacist_in: schemas.PharmacistCreate,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    username = _normalize_username(pharmacist_in.username)
    email = pharmacist_in.email.lower()
    license_number = pharmacist_in.license_number.strip()

    if db.query(models.Pharmacist).filter(models.Pharmacist.username == username).first():
        raise HTTPException(status_code=400, detail="Pharmacist username already exists")
    if db.query(models.Pharmacist).filter(models.Pharmacist.email == email).first():
        raise HTTPException(status_code=400, detail="Pharmacist email already exists")
    if db.query(models.Pharmacist).filter(models.Pharmacist.license_number == license_number).first():
        raise HTTPException(status_code=400, detail="License number already exists")

    pharmacist = models.Pharmacist(
        username=username,
        email=email,
        hashed_password=auth.get_password_hash(pharmacist_in.password),
        full_name=pharmacist_in.full_name.strip(),
        license_number=license_number,
        location=pharmacist_in.location.strip(),
        is_verified=True,
    )
    db.add(pharmacist)
    db.commit()
    db.refresh(pharmacist)
    return {"status": "success", "pharmacist": _serialize_pharmacist(pharmacist)}



@app.post("/api/admin/pharmacists/{pharmacist_id}/verify")
def admin_verify_pharmacist(
    pharmacist_id: int,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    pharmacist = db.query(models.Pharmacist).filter(models.Pharmacist.id == pharmacist_id).first()
    if not pharmacist:
        raise HTTPException(status_code=404, detail="Pharmacist not found")
    pharmacist.is_verified = True
    db.commit()
    return {"status": "success", "pharmacist": _serialize_pharmacist(pharmacist)}


@app.delete("/api/admin/pharmacists/{pharmacist_id}")
def admin_delete_pharmacist(
    pharmacist_id: int,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    pharmacist = db.query(models.Pharmacist).filter(models.Pharmacist.id == pharmacist_id).first()
    if not pharmacist:
        raise HTTPException(status_code=404, detail="Pharmacist not found")
    
    open_cases = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.pharmacist_id == pharmacist_id,
        models.PrescriptionHistory.status.in_(["In Review", "Pending"]),
    ).count()
    if open_cases:
        raise HTTPException(status_code=400, detail="Reassign or close active cases before deleting this pharmacist")
    
    db.delete(pharmacist)
    db.commit()
    return {"status": "success", "detail": "Pharmacist deleted"}

@app.post("/api/admin/pharmacists/{pharmacist_id}/reset-password")
def admin_reset_pharmacist_password(
    pharmacist_id: int,
    data: dict, # Expecting {"password": "newpassword"}
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    pharmacist = db.query(models.Pharmacist).filter(models.Pharmacist.id == pharmacist_id).first()
    if not pharmacist:
        raise HTTPException(status_code=404, detail="Pharmacist not found")
    
    new_password = data.get("password")
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
        
    pharmacist.hashed_password = auth.get_password_hash(new_password)
    db.commit()
    return {"status": "success", "detail": "Password reset successfully"}



@app.post("/api/admin/cases/{case_id}/assign")
def admin_assign_case(
    case_id: int,
    assignment: schemas.AssignCaseRequest,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pharmacist = db.query(models.Pharmacist).filter(models.Pharmacist.id == assignment.pharmacist_id).first()
    if not pharmacist:
        raise HTTPException(status_code=404, detail="Pharmacist not found")
    if not pharmacist.is_verified:
        raise HTTPException(status_code=400, detail="Pharmacist must be verified before assignment")

    case.pharmacist_id = pharmacist.id
    if case.status not in {"Reviewed", "Ordered", "Delivered"}:
        case.status = "Pending"
    case.follow_up_status = "assigned"
    _log_case_event(
        case,
        "admin",
        current_admin.username or current_admin.email,
        "case_assigned",
        f"Assigned to {pharmacist.full_name or pharmacist.username}",
    )
    db.commit()
    db.refresh(case)
    return {"status": "success", "case": _serialize_case(case)}


@app.post("/api/cases/{case_id}/order")
def order_prescription(
    case_id: int,
    order: schemas.OrderRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(models.PrescriptionHistory).filter(
        models.PrescriptionHistory.id == case_id,
        models.PrescriptionHistory.user_id == current_user.id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found or not owned by you")
    
    if case.status != "Reviewed":
        raise HTTPException(status_code=400, detail="Only reviewed cases can be ordered")
    
    case.status = "Ordered"
    case.delivery_address = order.delivery_address
    case.delivery_phone = order.phone_number
    case.delivery_notes = order.delivery_notes
    
    _log_case_event(
        case,
        "patient",
        current_user.username,
        "order_placed",
        f"Order placed for delivery to {order.delivery_address}",
    )
    db.commit()
    db.refresh(case)
    return {"status": "success", "case": _serialize_case(case)}


@app.post("/api/admin/cases/{case_id}/dispatch")
def admin_dispatch_case(
    case_id: int,
    update: schemas.DeliveryUpdate,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case.status = "Dispatched"
    _log_case_event(
        case,
        "admin",
        current_admin.username,
        "case_dispatched",
        f"Dispatched via {update.rider_name or 'Rider'}. Info: {update.tracking_info or 'N/A'}",
    )
    db.commit()
    db.refresh(case)
    return {"status": "success", "case": _serialize_case(case)}


@app.post("/api/admin/cases/{case_id}/deliver")
def admin_deliver_case(
    case_id: int,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    case = db.query(models.PrescriptionHistory).filter(models.PrescriptionHistory.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case.status = "Delivered"
    _log_case_event(
        case,
        "admin",
        current_admin.username,
        "case_delivered",
        "Medication successfully delivered to patient.",
    )
    db.commit()
    db.refresh(case)
    return {"status": "success", "case": _serialize_case(case)}


@app.delete("/api/admin/cases")
def admin_clear_cases(
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    deleted_events = db.query(models.CaseEvent).delete()
    deleted_cases = db.query(models.PrescriptionHistory).delete()
    db.commit()
    return {
        "status": "success",
        "deleted_cases": deleted_cases,
        "deleted_events": deleted_events,
        "message": "All case records have been cleared.",
    }


# Red flag symptoms derived from medical guidelines
RED_FLAGS = [
    {
        "condition": "Malaria / Severe Fever",
        "flags": [
            "Cannot keep oral medication down",
            "Confusion, convulsions, or severe weakness",
            "Yellowing of eyes or dark urine",
            "Fever lasting more than 3 days despite treatment",
            "Pregnant or infant under 6 months",
        ],
    },
    {
        "condition": "Head / Neurological",
        "flags": [
            "Sudden severe thunderclap headache",
            "Neck stiffness with fever",
            "Vision changes or slurred speech",
            "Headache after head injury",
        ],
    },
    {
        "condition": "Breathing / Chest",
        "flags": [
            "Difficulty breathing at rest",
            "Coughing blood",
            "Rapid breathing in children",
            "Productive cough with fever over 3 days",
        ],
    },
    {
        "condition": "Stomach / Abdomen",
        "flags": [
            "Severe dehydration ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â sunken eyes, no urine",
            "Blood or mucus in stool",
            "Rigid board-like abdomen",
            "Multiple household members ill",
        ],
    },
    {
        "condition": "General Danger Signs",
        "flags": [
            "Altered consciousness or unconsciousness",
            "Uncontrolled bleeding",
            "Pregnancy with acute serious illness",
            "Patient cannot stand or self-care",
        ],
    },
]


@app.get("/api/waitlist/public", response_model=schemas.WaitlistPublicInfo)
def get_waitlist_public_info(request: Request):
    return _get_waitlist_public_info_payload(request)


@app.post("/api/waitlist", response_model=schemas.WaitlistSubmitResponse)
def submit_waitlist_entry(
    waitlist_entry: schemas.WaitlistEntryCreate,
    db: Session = Depends(get_db),
):
    full_name = waitlist_entry.full_name.strip()
    email = waitlist_entry.email.lower().strip()
    phone = waitlist_entry.phone.strip()
    location = (waitlist_entry.location or "").strip()
    notes = (waitlist_entry.notes or "").strip()
    source = (waitlist_entry.source or "qr_waitlist").strip() or "qr_waitlist"

    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    existing_entry = db.query(models.WaitlistEntry).filter(models.WaitlistEntry.email == email).first()
    if existing_entry:
        existing_entry.full_name = full_name
        existing_entry.phone = phone
        existing_entry.location = location
        existing_entry.notes = notes
        existing_entry.source = source
        db.commit()
        db.refresh(existing_entry)
        return schemas.WaitlistSubmitResponse(
            status="updated",
            message="You're already on the waitlist, so we refreshed your details.",
            entry=schemas.WaitlistEntryResponse.model_validate(existing_entry),
        )

    new_entry = models.WaitlistEntry(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        notes=notes,
        source=source,
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return schemas.WaitlistSubmitResponse(
        status="created",
        message="You're on the waitlist. We'll reach out with next steps.",
        entry=schemas.WaitlistEntryResponse.model_validate(new_entry),
    )


@app.get("/api/waitlist/qr")
def get_waitlist_qr(request: Request):
    try:
        import qrcode
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="QR generation is unavailable until the qrcode dependency is installed.",
        ) from exc

    waitlist_info = _get_waitlist_public_info_payload(request)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(waitlist_info.waitlist_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="#0f766e", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/api/admin/waitlist")
def admin_list_waitlist(
    request: Request,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entries = db.query(models.WaitlistEntry).order_by(models.WaitlistEntry.created_at.desc()).all()
    return {
        "count": len(entries),
        "entries": [_serialize_waitlist_entry(entry) for entry in entries],
        "public": _get_waitlist_public_info_payload(request).model_dump(),
    }


@app.get("/api/admin/waitlist/export")
def admin_export_waitlist(
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entries = db.query(models.WaitlistEntry).order_by(models.WaitlistEntry.created_at.desc()).all()
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["id", "full_name", "email", "phone", "location", "notes", "source", "created_at"])
    for entry in entries:
        writer.writerow([
            entry.id,
            entry.full_name,
            entry.email,
            entry.phone,
            entry.location,
            entry.notes,
            entry.source,
            entry.created_at.isoformat() if entry.created_at else "",
        ])

    return StreamingResponse(
        iter([csv_buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist_entries.csv"'},
    )

@app.get("/api/reference", response_model=schemas.ReferenceData)
def get_reference_data():
    """Return conditions and red flags from the dataset for reference panel."""
    # Extract unique categories and indications from medicine dataset
    conditions_map = {}
    for med in medicine_dataset:
        category = med.get("Category", "").strip()
        indication = med.get("Indication", "").strip()
        name = med.get("Name", "").strip()
        
        if category and indication:
            key = f"{category}|{indication}"
            if key not in conditions_map:
                conditions_map[key] = {
                    "name": f"{category} - {indication}",
                    "drug": name,
                    "category": category,
                    "indication": indication,
                    "tags": [
                        {"t": "From Dataset", "c": "g"},
                        {"t": category[:15], "c": "b"},
                    ],
                }
    
    # Get common conditions with their treatments
    conditions_list = list(conditions_map.values())[:20]  # Limit to 20 conditions
    
    # Add hardcoded common conditions with proper tags if dataset is small
    common_conditions = [
        {
            "name": "Malaria / Fever",
            "drug": "Artemether + Lumefantrine (Coartem)",
            "category": "Antimalarial",
            "indication": "Malaria",
            "tags": [
                {"t": "CoartemÃƒâ€šÃ‚Â®", "c": "g"},
                {"t": "6 doses/3 days", "c": "b"},
                {"t": "With food", "c": "a"},
            ],
            "q": "Tell me about malaria symptoms and Coartem treatment.",
        },
        {
            "name": "Headache",
            "drug": "Paracetamol / Ibuprofen",
            "category": "Analgesic",
            "indication": "Pain",
            "tags": [
                {"t": "Tension", "c": "b"},
                {"t": "Migraine", "c": "b"},
                {"t": "Refer if severe", "c": "r"},
            ],
            "q": "Headache assessment and first-line treatment?",
        },
        {
            "name": "Diarrhea",
            "drug": "ORS + Zinc 10-20mg",
            "category": "Rehydration",
            "indication": "Diarrhea",
            "tags": [
                {"t": "Rehydration", "c": "g"},
                {"t": "Zinc", "c": "b"},
                {"t": "Metronidazole if amoebic", "c": "a"},
            ],
            "q": "Diarrhea management advice.",
        },
        {
            "name": "Cough / URTI",
            "drug": "Steam / Guaifenesin",
            "category": "Respiratory",
            "indication": "Cough",
            "tags": [
                {"t": "Fluids", "c": "g"},
                {"t": "Antibiotic if bacterial", "c": "a"},
                {"t": "Refer if SOB", "c": "r"},
            ],
            "q": "Cough and cold management?",
        },
        {
            "name": "Abdominal Pain",
            "drug": "Antacid / Omeprazole",
            "category": "Gastrointestinal",
            "indication": "Stomach Pain",
            "tags": [
                {"t": "Gastritis", "c": "b"},
                {"t": "NSAID for cramps", "c": "g"},
                {"t": "Refer if severe", "c": "r"},
            ],
            "q": "Abdominal pain assessment?",
        },
        {
            "name": "Skin Rash",
            "drug": "Hydrocortisone / Clotrimazole",
            "category": "Dermatological",
            "indication": "Skin",
            "tags": [
                {"t": "Allergic", "c": "a"},
                {"t": "Fungal", "c": "b"},
                {"t": "Antihistamine", "c": "g"},
            ],
            "q": "Skin rash first-line treatment?",
        },
        {
            "name": "Urinary Complaints",
            "drug": "Nitrofurantoin / Ciprofloxacin",
            "category": "Antibiotic",
            "indication": "UTI",
            "tags": [
                {"t": "UTI", "c": "b"},
                {"t": "Refer if pregnant", "c": "r"},
                {"t": "Fluids", "c": "g"},
            ],
            "q": "Urinary tract complaint management?",
        },
        {
            "name": "Hypertension",
            "drug": "Amlodipine 5mg OD",
            "category": "Cardiovascular",
            "indication": "Blood Pressure",
            "tags": [
                {"t": "BP monitoring", "c": "b"},
                {"t": "Adherence", "c": "g"},
                {"t": "Refer if uncontrolled", "c": "r"},
            ],
            "q": "Hypertension counseling guidelines?",
        },
        {
            "name": "Diabetes",
            "drug": "Metformin (first-line)",
            "category": "Antidiabetic",
            "indication": "Diabetes",
            "tags": [
                {"t": "Type 2 DM", "c": "b"},
                {"t": "Monitor glucose", "c": "g"},
                {"t": "Refer if uncontrolled", "c": "a"},
            ],
            "q": "Diabetes medication counseling?",
        },
        {
            "name": "Pain / Inflammation",
            "drug": "Paracetamol / Diclofenac gel",
            "category": "Analgesic",
            "indication": "Pain",
            "tags": [
                {"t": "NSAID", "c": "b"},
                {"t": "Topical option", "c": "g"},
                {"t": "Avoid overuse", "c": "a"},
            ],
            "q": "Pain and inflammation management?",
        },
    ]
    
    # Merge dataset conditions with common conditions, removing duplicates
    seen_names = set()
    final_conditions = []
    for c in common_conditions:
        if c["name"] not in seen_names:
            seen_names.add(c["name"])
            final_conditions.append(c)
    
    # Add dataset conditions that aren't duplicates
    for c in conditions_list:
        if c["name"] not in seen_names:
            seen_names.add(c["name"])
            final_conditions.append({
                "name": c["name"],
                "drug": c["drug"],
                "category": c["category"],
                "indication": c["indication"],
                "tags": c["tags"],
                "q": f"Tell me about {c['category']} medications for {c['indication']}.",
            })
    
    return {
        "conditions": final_conditions[:25],  # Max 25 conditions
        "red_flags": RED_FLAGS,
        "total_medicines": len(medicine_dataset),
        "total_conditions": len(final_conditions),
    }


@app.put("/api/profile/personal")
def update_personal(profile: schemas.ProfileUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_profile = current_user.profile
    for key, value in profile.dict().items():
        setattr(db_profile, key, value)
    db.commit()
    return {"status": "success"}


@app.put("/api/profile/medical")
def update_medical(medical: schemas.MedicalUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    current_user.medical.smoking = medical.smoking
    current_user.medical.alcohol = medical.alcohol
    current_user.medical.notes = medical.notes

    db.query(models.Condition).filter(models.Condition.user_id == current_user.id).delete()
    db.query(models.Allergy).filter(models.Allergy.user_id == current_user.id).delete()

    for c in medical.conditions:
        db.add(models.Condition(user_id=current_user.id, name=c))
    for a in medical.allergies:
        db.add(models.Allergy(user_id=current_user.id, name=a))
    db.commit()
    return {"status": "success"}


@app.post("/api/profile/medications")
def add_medication(med: schemas.MedicationBase, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    new_med = models.Medication(**med.dict(), user_id=current_user.id)
    db.add(new_med)
    db.commit()
    return {"status": "success"}


@app.delete("/api/profile/medications/{med_id}")
def del_medication(med_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db.query(models.Medication).filter(models.Medication.id == med_id, models.Medication.user_id == current_user.id).delete()
    db.commit()
    return {"status": "success"}


@app.put("/api/profile/emergency")
def update_emergency(emergency: schemas.EmergencyUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_emergency = current_user.emergency
    for key, value in emergency.dict().items():
        setattr(db_emergency, key, value)
    db.commit()
    return {"status": "success"}


@app.post("/api/cases/guest", response_model=schemas.GuestCaseResponse)
def submit_guest_case(
    case_data: schemas.GuestCaseSubmit,
    db: Session = Depends(get_db),
):
    """Allow non-logged-in users to submit cases directly to pharmacist queue."""
    user_id = None
    
    translated_messages = [{"role": "user", "content": case_data.message}]
    if case_data.symptoms:
        translated_messages.append({"role": "user", "content": case_data.symptoms})
    
    ai_summary = (
        f"Guest case from {case_data.first_name} {case_data.last_name}. "
        f"Phone: {case_data.phone}. "
        f"Message: {case_data.message}"
    )
    if case_data.symptoms:
        ai_summary += f" Additional symptoms: {case_data.symptoms}"

    search_text = " ".join(message["content"] for message in translated_messages if message.get("content"))
    matched_drugs = _search_medicine_dataset(search_text, limit=4)
    final_matches = _search_final_dataset(search_text, limit=4)
    relevant_pdf_context = _get_relevant_pdf_context(translated_messages)
    
    case = _create_case_record(
        db=db,
        user_id=user_id,
        translated_messages=translated_messages,
        ai_summary=ai_summary,
        matched_drugs=matched_drugs,
        final_matches=final_matches,
        relevant_pdf_context=relevant_pdf_context,
        actor_note="Guest case submitted without login.",
    )
    
    case.patient_message = case_data.message
    case.case_summary = f"{case_data.first_name} {case_data.last_name} - {case_data.message}"

    if case_data.symptoms:
        case.case_summary += f" | Symptoms: {case_data.symptoms}"
    case.follow_up_status = "awaiting_review"
    db.commit()
    db.refresh(case)
    
    return schemas.GuestCaseResponse(
        case_id=case.id,
        message="Your case has been submitted to the pharmacy. A licensed pharmacist will review it shortly.",
        case_summary=case.case_summary,
    )


@app.get("/waitlist", include_in_schema=False)
def waitlist_portal():
    return FileResponse(STATIC_DIR / "waitlist.html")


@app.get("/waitlist/qr", include_in_schema=False)
def waitlist_qr_portal():
    return FileResponse(STATIC_DIR / "waitlist_qr.html")


@app.get("/", include_in_schema=False)
def patient_portal():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/pharmacist", include_in_schema=False)
def pharmacist_portal():
    return FileResponse(STATIC_DIR / "pharmacist.html")


@app.get("/admin", include_in_schema=False)
def admin_portal():
    return FileResponse(STATIC_DIR / "admin.html")


# -- WhatsApp webhook --
from whatsapp_bot import router as wa_router
app.include_router(wa_router)


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", os.getenv("PORT", "8000")))
    uvicorn.run(app, host=host, port=port)
