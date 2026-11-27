"""Email OTP, provider failures and international notifications; no live emails."""
from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock

import httpx
import pytest

import main
import models
import auth


@pytest.fixture
def email_delivery(monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings,
        resend_api_key="test-resend-key", email_from="BisaRx <test@example.com>"))
    sender = Mock(return_value={"status": "sent", "reference": "test-email"})
    monkeypatch.setattr(main, "_send_email", sender)
    monkeypatch.setattr(main.secrets, "randbelow", lambda _: 123456)
    return sender


def request(client, email="patient@example.com"):
    return client.post("/api/auth/email/otp/request", json={"email": email})


def verify(client, email="patient@example.com", code="123456"):
    return client.post("/api/auth/email/otp/verify", json={"email": email, "code": code})


def test_email_otp_creates_patient_and_cannot_be_reused(client, db, email_delivery):
    response = request(client, "Patient@example.com")
    assert response.status_code == 200
    assert response.json()["dev_code"] is None
    assert "123456" not in response.text
    assert email_delivery.call_args.args[0] == "patient@example.com"
    assert "123456" in email_delivery.call_args.args[2]
    response = verify(client)
    assert response.status_code == 200, response.text
    token = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert client.get("/api/session", headers=token).json()["role"] == "user"
    assert client.get("/api/profile", headers=token).json()["email"] == "patient@example.com"
    assert verify(client).status_code == 400
    assert db.query(models.User).filter(models.User.email == "patient@example.com").count() == 1
    assert request(client).status_code == 200
    assert verify(client).status_code == 200
    assert db.query(models.User).filter(models.User.email == "patient@example.com").count() == 1


def test_email_otp_rate_attempt_and_expiry_limits(client, db, email_delivery):
    assert request(client).status_code == 200
    for _ in range(5):
        assert verify(client, code="000000").status_code == 400
    assert verify(client).status_code == 429
    assert request(client).status_code == 200
    challenge = db.query(models.OtpCode).order_by(models.OtpCode.id.desc()).first()
    challenge.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert verify(client).status_code == 400
    assert request(client).status_code == 200
    assert request(client).status_code == 429


def test_email_resend_invalidates_old_code_and_sms_cannot_verify_it(client, monkeypatch, email_delivery):
    codes = iter([123456, 234567])
    monkeypatch.setattr(main.secrets, "randbelow", lambda _: next(codes))
    assert request(client).status_code == 200
    assert request(client).status_code == 200
    assert verify(client).status_code == 400
    assert client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "234567"}).status_code == 400
    assert verify(client, code="234567").status_code == 200


def test_email_delivery_failure_invalidates_code(client, email_delivery):
    email_delivery.return_value = {"status": "failed"}
    assert request(client).status_code == 502
    assert verify(client).status_code == 400


def test_unconfigured_email_and_invalid_addresses(client):
    assert request(client).status_code == 503
    assert request(client, "not-an-email").status_code == 422
    assert client.post("/api/auth/otp/request", json={"phone": "+447700900123"}).status_code == 400
    assert client.get("/api/admin/integrations/email").status_code == 401


def test_email_otp_cannot_sign_in_admin(client, db, email_delivery):
    db.add(models.User(username="admin", email="admin@example.com", is_admin=True,
                       hashed_password=auth.get_password_hash("admin-test")))
    db.commit()
    assert request(client, "admin@example.com").status_code == 200
    assert verify(client, "admin@example.com").status_code == 403


@pytest.mark.parametrize("status,body,expected", [
    (200, {"id": "email-123"}, "sent"),
    (403, {"message": "unverified domain"}, "failed"),
])
def test_resend_contract(monkeypatch, status, body, expected):
    monkeypatch.setattr(main, "settings", replace(main.settings,
        resend_api_key="test-key", email_from="BisaRx <test@example.com>"))
    factory = MagicMock()
    gateway = factory.return_value.__enter__.return_value
    gateway.post.return_value = httpx.Response(status, json=body)
    monkeypatch.setattr(main.httpx, "Client", factory)
    assert main._send_email("patient@example.com", "Test subject", "Test text")["status"] == expected
    args, kwargs = gateway.post.call_args
    assert args == ("https://api.resend.com/emails",)
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["to"] == ["patient@example.com"]
    assert kwargs["json"]["text"] == "Test text"


def test_international_patient_gets_feedback_by_email_and_portal(client, db, email_delivery, monkeypatch):
    request(client)
    token = {"Authorization": "Bearer " + verify(client).json()["access_token"]}
    user_id = client.get("/api/session", headers=token).json()["user_id"]
    pharmacist = models.Pharmacist(username="email-ph", email="ph@example.com", license_number="EMAIL-PH",
        hashed_password=auth.get_password_hash("test-password"), is_verified=True, accepting_cases=True)
    db.add(pharmacist)
    db.commit()
    case = models.PrescriptionHistory(user_id=user_id, status="Pending", case_summary="Test case")
    db.add(case)
    db.commit()
    staff = {"Authorization": "Bearer " + auth.create_access_token({"sub": pharmacist.email, "role": "pharmacist"})}
    notify = AsyncMock()
    monkeypatch.setattr(main.ws_manager, "notify_user", notify)
    sms = Mock()
    monkeypatch.setattr(main, "_send_moolre_sms", sms)
    email_delivery.reset_mock()
    response = client.post(f"/api/pharmacist/review/{case.id}", headers=staff,
                           json={"advice": "Test review", "status": "Reviewed"})
    assert response.status_code == 200, response.text
    email_delivery.assert_called_once()
    assert email_delivery.call_args.args[0] == "patient@example.com"
    assert "Test review" in email_delivery.call_args.args[2]
    sms.assert_not_called()
    notify.assert_awaited_once()
    reports = client.get("/api/profile", headers=token).json()["prescriptions"]
    assert reports[0]["pharmacist_feedback"] == "Test review"


def test_international_pharmacist_gets_case_email(db, case, email_delivery, monkeypatch):
    db.add(models.Pharmacist(username="intl-ph", email="ph@example.com", license_number="INTL-PH",
        hashed_password="test-hash", phone="+447700900123", is_verified=True, accepting_cases=True))
    db.commit()
    monkeypatch.setattr(main, "SessionLocal", lambda: db)
    sms = Mock()
    monkeypatch.setattr(main, "_send_moolre_sms", sms)
    main._notify_pharmacists_of_new_case(case.id)
    email_delivery.assert_called_once()
    assert email_delivery.call_args.args[0] == "ph@example.com"
    sms.assert_not_called()
