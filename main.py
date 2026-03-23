from pathlib import Path
import re
import csv
from typing import List

import os
from dotenv import load_dotenv
import pypdf
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import auth
import models
import schemas
from database import engine, get_db

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env', override=True, verbose=True)
STATIC_DIR = BASE_DIR / "static"

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="RxAI Ghana API")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET") or "dev-secret-change-me",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", "dummy_key"))
configured_base_url = os.getenv("DEEPSEEK_BASE_URL", "").strip()

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


SYSTEM_PROMPT = f"""You are RxAI, a warm, deeply empathetic pharmacist who genuinely cares about each person you speak with. You're like a compassionate friend who happens to know a lot about medicine. You speak from the heart, with kindness and understanding.

CONVERSATION STYLE:
- Start with empathy: Acknowledge how the person feels. If they're suffering, let them know you genuinely care.
- Be conversational and warm, like chatting with a trusted friend over tea.
- Use emotionally supportive phrases: "Oh no, I'm so sorry you're going through this!" "That sounds really uncomfortable, let's figure this out together" "I completely understand how you feel" "Don't worry, we're going to get through this"
- Never sound robotic or clinical. Your warmth should come through in every message.

CONVERSATION RULES (follow strictly):
1. ASK ONE QUESTION AT A TIME: Like a doctor, you must only ask one caring follow-up question in each response. Never bundle multiple questions.
2. WAIT FOR ANSWER: Do not move to the next topic until the patient has answered your previous question.
3. EMPATHY FIRST: Every single response must begin with a reflection of the patient's feelings.
4. GATHER VITAL INFO: Before recommending anything, you MUST know:
   - Exactly how long they've had the symptoms.
   - The severity (is it getting better or worse?).
   - Any other symptoms they might have missed.
5. TRANSITION: After you have gathered enough information (at least 3-4 distinct exchanges), include the exact marker [CONSULT_READY] at the very start of your response, followed by a warm, empathetic summary and transition to medication.
6. NO SELF-PRESCRIBING: NEVER recommend specific drug names yourself. The drug lookup happens separately after [CONSULT_READY].
7. LANGUAGE: Respond in the same language the patient writes in (English, Twi, Hausa, or French).
8. RED FLAGS: ALWAYS flag danger signs (convulsions, confusion, jaundice, severe dehydration, difficulty breathing) with immediate hospital referral.

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
        for symptom in matched_symptoms:
            if symptom in med_indication or symptom in med_category:
                score += 5
            # Check if indication keywords match
            for ind in symptom_info[symptom]["indications"]:
                if ind in med_indication:
                    score += 3

        # Score by token overlap with name/category
        overlap = query_tokens.intersection(med["_tokens"])
        score += len(overlap)

        # Bonus for common OTC medications
        common_meds = ["paracetamol", "acetaminophen", "ibuprofen", "aspirin", "ORS", "vitamin", "zinc", "amoxicillin", "coartem"]
        for common in common_meds:
            if common in med_name:
                score += 1

        if score > 0:
            scored.append((score, med))

    # Update: Cross-reference with final_dataset for better precision
    for entry in final_dataset:
        score = 0
        disease = entry["disease"].lower()
        drug_name = entry["drug"].lower()

        # Check for symptom match in disease name
        for symptom in matched_symptoms:
            if symptom in disease:
                score += 10 # High priority for disease match

        # Token overlap
        overlap = query_tokens.intersection(entry["_tokens"])
        score += len(overlap)

        if score > 5:
            # We need to find or simulate the extra metadata (category, dose) since final.csv is simple
            # We'll try to find a match in the main medicine_dataset first
            med_info = next((m for m in medicine_dataset if m.get("Name", "").lower() == drug_name), None)
            
            scored.append((score, {
                "Name": drug_name.title(),
                "Category": med_info.get("Category", "Treatment") if med_info else "General medication",
                "Dosage Form": med_info.get("Dosage Form", "Tablet/Syrup") if med_info else "As directed",
                "Strength": med_info.get("Strength", "Standard") if med_info else "N/A",
                "Indication": disease.title(),
                "Classification": med_info.get("Classification", "OTC") if med_info else "General",
                "_tokens": entry["_tokens"]
            }))

    scored.sort(key=lambda item: item[0], reverse=True)

    # Deduplicate by drug name, keeping highest scored, ensure at least 3 results
    seen_names = set()
    results = []
    for _, med in scored:
        name = med.get("Name", "")
        if name not in seen_names:
            seen_names.add(name)
            
            # Determine dosage hint based on symptom match
            dosage_hint = "Take as directed by your pharmacist or doctor"
            for symptom in matched_symptoms:
                if symptom in symptom_info:
                    dosage_hint = symptom_info[symptom]["dosage_hint"]
                    break
            
            results.append({
                "name": name,
                "category": med.get("Category", ""),
                "dosage_form": med.get("Dosage Form", ""),
                "strength": med.get("Strength", ""),
                "indication": med.get("Indication", ""),
                "classification": med.get("Classification", ""),
                "dosage_instructions": dosage_hint,
            })
        if len(results) >= max(limit, 4):  # Increased limit for better results
            break

    return results


def _get_relevant_pdf_context(messages: list[dict], limit: int = 3) -> str:
    if not pdf_chunks:
        return ""

    query_text = " ".join(message["content"] for message in messages if message.get("role") == "user")
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return ""

    scored_chunks = []
    for chunk in pdf_chunks:
        overlap = query_tokens.intersection(chunk["tokens"])
        if overlap:
            scored_chunks.append((len(overlap), chunk["page"], chunk["text"]))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    top_chunks = scored_chunks[:limit]
    if not top_chunks:
        return ""

    return "\n\n".join(
        f"PDF page {page}: {text}" for _, page, text in top_chunks
    )


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
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


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


@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat(request: schemas.ChatRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Detect Twi using exact dataset mapping and translate to English for model prompt context
    input_language = "en"
    for m in messages:
        if m["role"] == "user" and _translate_twi_to_english(m["content"]):
            input_language = "twi"
            break

    translated_messages = []
    for m in messages:
        if m["role"] == "user" and input_language == "twi":
            translated = _translate_twi_to_english(m["content"])
            translated_messages.append({"role": "user", "content": translated or m["content"]})
        else:
            translated_messages.append(m)

    relevant_pdf_context = _get_relevant_pdf_context(translated_messages)

    prompt_parts = [SYSTEM_PROMPT]
    if relevant_pdf_context:
        prompt_parts.append(
            "Use the following PDF guideline excerpts when they are relevant to the user question. "
            "Prefer these excerpts over guessing.\n\n"
            f"{relevant_pdf_context}"
        )

    # Add explicit language instruction for the model if input is Twi
    if input_language == "twi":
        prompt_parts.append("Answer in Twi in a caring, clear way. If you need to translate medical terms, keep them understandable for non-English speakers. Still follow the conversation rules and use [CONSULT_READY] when ready.")

    try:
        response = openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "\n\n".join(prompt_parts)}] + translated_messages,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content

        # If input was Twi, translate the reply back to Twi for fluency
        if input_language == "twi":
            translation_response = openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "Translate the following English medical advice to fluent Twi. Keep it natural, caring, and concise. Use simple terms for medical concepts. If the text contains [CONSULT_READY], keep that marker exactly as is."},
                    {"role": "user", "content": reply}
                ],
                max_tokens=1000,
            )
            reply = translation_response.choices[0].message.content

        # Check if the AI is ready to consult (has gathered enough info)
        is_consulting = "[CONSULT_READY]" in reply
        matched_drugs = []

        if is_consulting:
            # Strip the marker from the reply
            reply = reply.replace("[CONSULT_READY]", "").strip()

            # Gather all user messages to build symptom context
            all_user_text = " ".join(
                m["content"] for m in translated_messages if m["role"] == "user"
            )

            # Also use the AI's summary (the reply after CONSULT_READY)
            search_text = all_user_text + " " + reply
            matched_drugs = _search_medicine_dataset(search_text, limit=4)

            # Save matched drugs to prescription history
            for drug in matched_drugs:
                rx = models.PrescriptionHistory(
                    user_id=current_user.id,
                    drug_name=drug["name"],
                    details=f"{drug['indication']} - {drug['category']}",
                    status="Pending",
                )
                db.add(rx)
            db.commit()

        return {
            "reply": reply,
            "drugs": matched_drugs if matched_drugs else None,
            "consulting": is_consulting,
            "error": None,
        }
    except Exception as e:
        if "dummy_key" in os.getenv("DEEPSEEK_API_KEY", "dummy_key"):
            return {
                "reply": "(Demo fallback) I can answer from the uploaded guideline PDF once your AI API key is configured.",
                "drugs": None,
                "consulting": False,
                "error": None,
            }
        raise HTTPException(status_code=500, detail=str(e))


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
            "Severe dehydration — sunken eyes, no urine",
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
                {"t": "Coartem®", "c": "g"},
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


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
