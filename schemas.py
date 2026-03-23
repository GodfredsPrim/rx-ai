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
