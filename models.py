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
    phone2 = Column(String, default="")
    address = Column(String, default="")
    alert = Column(Text, default="")

    owner = relationship("User", back_populates="emergency")

class PrescriptionHistory(Base):
    __tablename__ = "prescription_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    drug_name = Column(String)
    details = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="prescriptions")
