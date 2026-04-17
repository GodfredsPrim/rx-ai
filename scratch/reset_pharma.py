
import models
import auth
from database import SessionLocal

db = SessionLocal()
try:
    ph = db.query(models.Pharmacist).filter(models.Pharmacist.username == 'drmello').first()
    if ph:
        ph.hashed_password = auth.get_password_hash("pharmacist1")
        db.commit()
        print(f"Reset password for pharmacist '{ph.username}' to 'pharmacist1'")
    else:
        print("Pharmacist 'drmello' not found.")
finally:
    db.close()
