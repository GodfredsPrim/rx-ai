"""Demo regressions using isolated databases and mocked delivery services."""
from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
import auth
import main
import models


def headers(response):
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def admin_headers(client, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, admin_access_code="demo-code", admin_password=""))
    return headers(client.post("/api/auth/admin/access", json={"access_code": "demo-code"}))


@pytest.mark.parametrize("code,password", [("demo-code", ""), ("", "demo-password"), ("κωδικός", "")])
def test_admin_configuration_provisions_account(client, monkeypatch, code, password):
    monkeypatch.setattr(main, "settings", replace(main.settings, app_env="production",
                        admin_username="", admin_access_code=code, admin_password=password))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    token = headers(client.post("/api/auth/admin/access", json={"access_code": code or password}))
    assert client.get("/api/session", headers=token).json()["role"] == "admin"
    for route in ("dashboard", "stats", "users", "waitlist"):
        assert client.get("/api/admin/" + route, headers=token).status_code == 200


def test_admin_rejects_wrong_code_and_password_when_explicit_code_set(client, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, admin_access_code="code", admin_password="password"))
    for value in ("", "wrong", "password", "😀"):
        assert client.post("/api/auth/admin/access", json={"access_code": value}).status_code == 400


def test_admin_unconfigured(client):
    assert client.post("/api/auth/admin/access", json={"access_code": "wrong"}).status_code == 500


def test_staff_lifecycle_and_case_review(client, db, admin_headers, case, monkeypatch):
    monkeypatch.setattr(main, "_send_moolre_sms", Mock(return_value={"status": "sent"}))
    payload = dict(username="demo.pharm", email="pharm@example.com", password="demo-password",
                   full_name="Demo Pharmacist", license_number="PH-DEMO", phone="0241234567")
    result = client.post("/api/admin/pharmacists", headers=admin_headers, json=payload)
    assert result.status_code == 200, result.text
    pharmacist_id = result.json()["pharmacist"]["id"]
    assert client.post("/api/admin/pharmacists", headers=admin_headers, json=payload).status_code == 400
    for username in (payload["username"], payload["email"], "ph-demo"):
        staff = headers(client.post("/api/auth/pharmacist/login", data={"username": username, "password": payload["password"]}))
        assert client.get("/api/session", headers=staff).json()["role"] == "pharmacist"
    assert client.get("/api/admin/dashboard", headers=staff).status_code == 401
    assert client.patch("/api/pharmacist/availability", headers=staff, json={"accepting_cases": False}).status_code == 200
    case.status = "Pending"
    db.commit()
    assert client.post(f"/api/pharmacist/cases/{case.id}/accept", headers=staff).status_code == 200
    assert client.post(f"/api/pharmacist/cases/{case.id}/accept", headers=staff).status_code == 400
    assert client.delete(f"/api/admin/pharmacists/{pharmacist_id}", headers=admin_headers).status_code == 400
    response = client.post(f"/api/pharmacist/review/{case.id}", headers=staff,
                           json={"advice": "Demo review advice", "total_price": 10})
    assert response.status_code == 200, response.text
    assert response.json()["case"]["status"] == "Reviewed"
    assert client.get("/api/pharmacist/dashboard", headers=staff).json()["stats"]["completed_cases"] == 1
    reset = f"/api/admin/pharmacists/{pharmacist_id}/reset-password"
    assert client.post(reset, headers=admin_headers, json={"password": "new-password"}).status_code == 200
    assert client.post("/api/auth/pharmacist/login", data={"username": payload["username"], "password": payload["password"]}).status_code == 400
    headers(client.post("/api/auth/pharmacist/login", data={"username": payload["username"], "password": "new-password"}))


def test_otp_resend_limit_and_latest_code(client, db, monkeypatch):
    monkeypatch.setattr(main, "_send_moolre_sms", Mock(return_value={"status": "sent"}))
    codes = iter([123456, 234567, 345678])
    monkeypatch.setattr(main.secrets, "randbelow", lambda _: next(codes))
    for _ in range(3):
        assert client.post("/api/auth/otp/request", json={"phone": "0241234567"}).status_code == 200
    assert client.post("/api/auth/otp/request", json={"phone": "0241234567"}).status_code == 429
    assert client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "123456"}).status_code == 400
    token = headers(client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "345678"}))
    assert client.get("/api/session", headers=token).json()["role"] == "user"
    assert client.get("/api/profile", headers=token).status_code == 200
    assert client.get("/api/admin/dashboard", headers=token).status_code == 401
    assert client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "345678"}).status_code == 400


def test_otp_wrong_attempts_and_expiry(client, db):
    otp = models.OtpCode(phone="233241234567", code_hash=main._hash_otp("233241234567", "123456"),
                         expires_at=datetime.utcnow() + timedelta(minutes=5))
    db.add(otp)
    db.commit()
    for _ in range(5):
        assert client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "000000"}).status_code == 400
    assert client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "123456"}).status_code == 429
    otp.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "123456"}).status_code == 400


@pytest.mark.parametrize("password", ["incorrect", "x" * 100, "😀" * 30])
def test_long_login_password_does_not_crash(client, db, password):
    db.add(models.User(username="demo", email="demo@example.com", hashed_password=auth.get_password_hash("correct")))
    db.commit()
    assert client.post("/api/auth/login", data={"username": "demo", "password": password}).status_code == 400


def test_waitlist_updates_and_export(client, admin_headers):
    payload = {"full_name": "Demo Visitor", "email": "visitor@example.com", "phone": "0241234567"}
    assert client.post("/api/waitlist", json=payload).json()["status"] == "created"
    payload["full_name"] = "Updated Visitor"
    assert client.post("/api/waitlist", json=payload).json()["status"] == "updated"
    response = client.get("/api/admin/waitlist/export", headers=admin_headers)
    assert response.status_code == 200
    assert "Updated Visitor" in response.text
    assert client.get("/api/waitlist/qr").status_code == 200


def test_registration_login_and_profile(client):
    payload = dict(username="demo-patient", email="patient@example.com", password="demo-password",
                   first_name="Demo", last_name="Patient")
    token = headers(client.post("/api/auth/register", json=payload))
    assert client.get("/api/profile", headers=token).status_code == 200
    assert client.post("/api/auth/register", json=payload).status_code == 400
    for username in ("DEMO-PATIENT", "PATIENT@EXAMPLE.COM"):
        headers(client.post("/api/auth/login", data={"username": username, "password": payload["password"]}))
