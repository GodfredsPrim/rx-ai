
import models
import auth
from database import SessionLocal
from sqlalchemy import or_

db = SessionLocal()
try:
    admin = db.query(models.User).filter(
        or_(models.User.username == 'admin', models.User.email == 'admin@bisarx.local')
    ).first()
    
    if admin:
        print(f"Found admin user: {admin.username}")
        new_pass = "admin1"
        admin.hashed_password = auth.get_password_hash(new_pass)
        admin.is_admin = True
        db.commit()
        print(f"Successfully reset password for '{admin.username}' to '{new_pass}'")
    else:
        print("Admin user not found. creating it...")
        admin = models.User(
            username='admin',
            email='admin@bisarx.local',
            hashed_password=auth.get_password_hash("admin1"),
            is_admin=True
        )
        db.add(admin)
        db.commit()
        print("Created admin user with password 'admin1'")
finally:
    db.close()
