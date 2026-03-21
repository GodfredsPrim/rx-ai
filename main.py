from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session
from openai import OpenAI
import os
import re
from typing import List
from fastapi.staticfiles import StaticFiles
import pypdf

import models, schemas, auth
from database import engine, get_db

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

openai_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "dummy_key"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

pdf_context = ""
try:
    with open("📘 Section 1_ Preface & Purpose.pdf", "rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            pdf_context += page.extract_text() + "\n"
except Exception as e:
    print(f"Failed to load PDF context: {e}")

SYSTEM_PROMPT = f"""You are RxAI, a warm, calm, expert AI Pharmacist. You speak like a kind, reassuring doctor. Respond in the same language the patient writes in (English, Twi, Hausa, or French). Provide straightforward, friendly, and concise medical advice based on standard health guidelines without explicitly referencing them in your answers. ALWAYS flag red signs (convulsions, confusion, jaundice, severe dehydration, difficulty breathing) for immediate hospital referral. Be concise, warm, and end with a counseling tip.

ADDITIONAL CONTEXT FROM MEDICAL GUIDELINES:
{pdf_context}"""


def _ensure_user_auth_columns():
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "username" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR"))
        conn.execute(text("UPDATE users SET username = email WHERE username IS NULL OR TRIM(username) = ''"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))


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


_ensure_user_auth_columns()


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
        raise HTTPException(status_code=400, detail=f"Google OAuth failed: {e}")

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
        # Placeholder local password hash so account remains compatible with existing model.
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

    try:
        response = openai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content

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
                "reply": "(Demo fallback - Auth API Error) Yes, you should take Paracetamol. Dose: 500mg-1g every 4-6 hours (max 4g/day)."
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


# Serve static files as the very last route
import os as _os
if _os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)