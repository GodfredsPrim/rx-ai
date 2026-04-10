from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


class PharmacistCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    license_number: str
    location: str = ""


class AssignCaseRequest(BaseModel):
    pharmacist_id: int


class PharmacistReviewRequest(BaseModel):
    diagnosis: Optional[str] = None
    advice: str
    drug: Optional[str] = None
    referral_advice: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    status: str = "Reviewed"

class ProfileBase(BaseModel):
    first_name: str
    last_name: str
    dob: str
    gender: str
    phone: str
    address: str
    city: str
    gh_card: str
    blood_type: str

class ProfileUpdate(ProfileBase):
    pass

class Profile(ProfileBase):
    id: int
    user_id: int
    class Config:
        from_attributes = True

class MedicalBase(BaseModel):
    smoking: str
    alcohol: str
    notes: str

class MedicalUpdate(MedicalBase):
    conditions: List[str]
    allergies: List[str]

class MedicationBase(BaseModel):
    name: str
    dose: str
    freq: str
    status: str
    doctor: str

    class Config:
        from_attributes = True

class EmergencyBase(BaseModel):
    name: str
    rel: str
    phone: str
    phone_alt: str
    address: str
    alert: str

class EmergencyUpdate(EmergencyBase):
    pass

class PrescriptionBase(BaseModel):
    drug_name: str
    details: str
    status: str

class Prescription(PrescriptionBase):
    id: int
    created_at: datetime
    patient_message: Optional[str] = None
    case_summary: Optional[str] = None
    ai_summary: Optional[str] = None
    pharmacist_feedback: Optional[str] = None
    referral_advice: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    urgency_level: Optional[str] = None
    follow_up_status: Optional[str] = None
    symptom_area: Optional[str] = None
    symptom_type: Optional[str] = None
    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class DrugMatch(BaseModel):
    name: str
    category: str
    dosage_form: str
    strength: str
    indication: str
    classification: str

class ChatResponse(BaseModel):
    reply: str
    drugs: Optional[List[DrugMatch]] = None
    consulting: bool = False
    error: Optional[str] = None


class RedFlagItem(BaseModel):
    condition: str
    flags: List[str]


class ConditionItem(BaseModel):
    name: str
    drug: str
    category: Optional[str] = None
    indication: Optional[str] = None
    tags: Optional[List[dict]] = None
    q: Optional[str] = None


class ReferenceData(BaseModel):
    conditions: List[ConditionItem]
    red_flags: List[RedFlagItem]
    total_medicines: int
    total_conditions: int


class GuestCaseSubmit(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: Optional[EmailStr] = None
    message: str
    symptoms: Optional[str] = None


class GuestCaseResponse(BaseModel):
    case_id: int
    message: str
    case_summary: str

class WaitlistEntryCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    location: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = "qr_waitlist"


class WaitlistEntryResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str
    location: Optional[str] = None
    notes: Optional[str] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class WaitlistSubmitResponse(BaseModel):
    status: str
    message: str
    entry: WaitlistEntryResponse


class WaitlistPublicInfo(BaseModel):
    waitlist_url: str
    qr_image_url: str
    qr_page_url: str
