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

print(f"DEBUG: Loaded API key starting with: {api_key[:10]}..., base_url={base_url}")

openai_client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

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


def _translate_twi_to_english(text: str) -> str | None:
    normalized = text.strip().lower()
    for pair in twi_dataset:
        if pair["twi"].strip().lower() == normalized:
            return pair["en"]
    return None


SYSTEM_PROMPT = f"""You are RxAI, a warm, calm, expert AI Pharmacist. You speak like a kind, reassuring doctor. Respond in the same language the patient writes in (English, Twi, Hausa, or French). Provide straightforward, friendly, and concise medical advice based on standard health guidelines and the provided medicine dataset without explicitly referencing them in your answers. ALWAYS flag red signs (convulsions, confusion, jaundice, severe dehydration, difficulty breathing) for immediate hospital referral. Be concise, warm, and end with a counseling tip. Do not use asterisks, bold, italics, or any markdown formatting in your responses. Give straight, direct answers based on the data provided. Recommend specific medications from the medicine dataset when relevant, including name, dosage form, strength, and indication. Do not ask questions; provide direct recommendations.

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
    relevant_med_context = _get_relevant_medicine_context(translated_messages)

    prompt_parts = [SYSTEM_PROMPT]
    if relevant_pdf_context:
        prompt_parts.append(
            "Use the following PDF guideline excerpts when they are relevant to the user question. "
            "Prefer these excerpts over guessing.\n\n"
            f"{relevant_pdf_context}"
        )
    
    if relevant_med_context:
        prompt_parts.append(
            "Use the following medicine dataset information for drug details. "
            "If a drug is mentioned or the symptom matches an indication, recommend specific medications directly from this data.\n\n"
            f"{relevant_med_context}"
        )

    # Add explicit language instruction for the model if input is Twi
    if input_language == "twi":
        prompt_parts.append("Answer in Twi in a caring, clear way. If you need to translate medical terms, keep them understandable for non-English speakers.")

    try:
        response = openai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "\n\n".join(prompt_parts)}] + translated_messages,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content

        # If input was Twi, translate the reply back to Twi for fluency
        if input_language == "twi":
            translation_response = openai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Translate the following English medical advice to fluent Twi. Keep it natural, caring, and concise. Use simple terms for medical concepts."},
                    {"role": "user", "content": reply}
                ],
                max_tokens=1000,
            )
            reply = translation_response.choices[0].message.content

        lower_reply = reply.lower()
        drugs_to_check = {
            "coartem": "Artemether + Lumefantrine (Coartem) - Malaria",
            "paracetamol": "Paracetamol - Pain/Fever/Headache",
            "ibuprofen": "Ibuprofen - Pain/Fever",
            "amlodipine": "Amlodipine 5mg - Hypertension",
            "metformin": "Metformin - Diabetes",
            "zinc": "ORS + Zinc 10-20mg - Diarrhea",
        }
        for drug_key, details in drugs_to_check.items():
            if drug_key in lower_reply:
                rx = models.PrescriptionHistory(
                    user_id=current_user.id,
                    drug_name=details.split(" - ")[0],
                    details=details.split(" - ")[1],
                    status="Pending",
                )
                db.add(rx)
        db.commit()

        return {"reply": reply}
    except Exception as e:
        if "dummy_key" in os.getenv("DEEPSEEK_API_KEY", "dummy_key"):
            return {
                "reply": "(Demo fallback) I can answer from the uploaded guideline PDF once your AI API key is configured."
            }
        raise HTTPException(status_code=500, detail=str(e))


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
