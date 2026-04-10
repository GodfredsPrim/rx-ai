from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)
    
    profile = relationship("Profile", back_populates="owner", uselist=False)
    medical = relationship("Medical", back_populates="owner", uselist=False)
    emergency = relationship("Emergency", back_populates="owner", uselist=False)
    conditions = relationship("Condition", back_populates="owner")
    allergies = relationship("Allergy", back_populates="owner")
    medications = relationship("Medication", back_populates="owner")
    prescriptions = relationship("PrescriptionHistory", back_populates="owner")

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    dob = Column(String, default="")
    gender = Column(String, default="")
    phone = Column(String, default="")
    address = Column(String, default="")
    city = Column(String, default="")
    gh_card = Column(String, default="")
    blood_type = Column(String, default="")
    
    owner = relationship("User", back_populates="profile")

class Medical(Base):
    __tablename__ = "medicals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    smoking = Column(String, default="")
    alcohol = Column(String, default="")
    notes = Column(Text, default="")

    owner = relationship("User", back_populates="medical")

class Condition(Base):
    __tablename__ = "conditions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)

    owner = relationship("User", back_populates="conditions")

class Allergy(Base):
    __tablename__ = "allergies"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)

    owner = relationship("User", back_populates="allergies")

class Medication(Base):
    __tablename__ = "medications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    dose = Column(String)
    freq = Column(String)
    status = Column(String)
    doctor = Column(String, default="")

    owner = relationship("User", back_populates="medications")

class Emergency(Base):
    __tablename__ = "emergencies"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, default="")
    rel = Column(String, default="")
    phone = Column(String, default="")
    phone_alt = Column(String, default="")
    address = Column(String, default="")
    alert = Column(Text, default="")

    owner = relationship("User", back_populates="emergency")

class Pharmacist(Base):
    __tablename__ = "pharmacists"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, default="")
    license_number = Column(String, unique=True, index=True)
    location = Column(String, default="")
    is_verified = Column(Boolean, default=False)
    
    reviews = relationship("PrescriptionHistory", back_populates="reviewer")

class PrescriptionHistory(Base):
    __tablename__ = "prescription_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    pharmacist_id = Column(Integer, ForeignKey("pharmacists.id"), nullable=True)
    drug_name = Column(String)
    details = Column(String)
    patient_message = Column(Text, default="")
    case_summary = Column(Text, default="")
    ai_summary = Column(Text, default="")
    pharmacist_feedback = Column(Text, default="")
    referral_advice = Column(Text, default="")
    follow_up_instructions = Column(Text, default="")
    urgency_level = Column(String, default="routine")
    follow_up_status = Column(String, default="awaiting_review")
    symptom_area = Column(String, default="")
    symptom_type = Column(String, default="")
    status = Column(String) # Pending, In Review, Reviewed, Ordered, Delivered
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    owner = relationship("User", back_populates="prescriptions")
    reviewer = relationship("Pharmacist", back_populates="reviews")
    events = relationship("CaseEvent", back_populates="case", cascade="all, delete-orphan")


class CaseEvent(Base):
    __tablename__ = "case_events"
    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescription_history.id"))
    actor_role = Column(String, default="")
    actor_name = Column(String, default="")
    action = Column(String, default="")
    note = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    case = relationship("PrescriptionHistory", back_populates="events")

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, default="")
    location = Column(String, default="")
    notes = Column(Text, default="")
    source = Column(String, default="qr_waitlist")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
