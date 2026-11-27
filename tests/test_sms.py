"""SMS contracts and dual-channel notification regressions; no real SMS sent."""
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

import main
import models


@pytest.fixture
def admin_token(client, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, admin_access_code="test-admin"))
    response = client.post("/api/auth/admin/access", json={"access_code": "test-admin"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_sms_configuration_is_admin_only_and_does_not_expose_key(client, monkeypatch, admin_token):
    monkeypatch.setattr(main, "MOOLRE_API_VASKEY", "")
    monkeypatch.setattr(main, "MOOLRE_SMS_SENDER_ID", "")
    route = "/api/admin/integrations/sms"
    assert client.get(route).status_code == 401
    result = client.get(route, headers=admin_token).json()
    assert not result["configured"]
    assert set(result["missing_variables"]) == {"MOOLRE_API_VASKEY", "MOOLRE_SMS_SENDER_ID"}
    monkeypatch.setattr(main, "MOOLRE_API_VASKEY", "secret-never-disclosed")
    monkeypatch.setattr(main, "MOOLRE_SMS_SENDER_ID", "BisaRx")
    response = client.get(route, headers=admin_token)
    assert response.json()["configured"]
    assert "secret-never-disclosed" not in response.text


@pytest.mark.parametrize("status,body,expected", [
    (200, {"status": 1, "code": "SMS01"}, "sent"),
    (200, {"status": 0, "code": "ASMS07"}, "failed"),
    (401, {"status": 0, "code": "AIN01"}, "failed"),
])
def test_moolre_sms_contract(monkeypatch, status, body, expected):
    monkeypatch.setattr(main, "MOOLRE_API_VASKEY", "test-vas-key")
    monkeypatch.setattr(main, "MOOLRE_SMS_SENDER_ID", "BisaRx")
    gateway = Mock()
    gateway.post.return_value = httpx.Response(status, json=body)
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=gateway)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(main.httpx, "Client", factory)
    result = main._send_moolre_sms("024 123 4567", "Test message")
    assert result["status"] == expected
    args, kwargs = gateway.post.call_args
    assert args == ("https://api.moolre.com/open/sms/send",)
    assert kwargs["headers"]["X-API-VASKEY"] == "test-vas-key"
    assert kwargs["json"]["senderid"] == "BisaRx"
    assert kwargs["json"]["messages"][0]["recipient"] == "233241234567"


def test_production_otp_failure_never_returns_code(client, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, app_env="production"))
    monkeypatch.setattr(main, "_send_moolre_sms", Mock(return_value={"status": "skipped", "reason": "not_configured"}))
    response = client.post("/api/auth/otp/request", json={"phone": "0241234567"})
    assert response.status_code == 502
    assert "dev_code" not in response.text


def test_otp_patient_receives_review_in_portal_and_sms_even_when_online(client, db, monkeypatch, admin_token):
    sms = Mock(return_value={"status": "sent"})
    monkeypatch.setattr(main, "_send_moolre_sms", sms)
    monkeypatch.setattr(main.secrets, "randbelow", lambda _: 123456)
    assert client.post("/api/auth/otp/request", json={"phone": "0241234567"}).status_code == 200
    assert "123456" in sms.call_args.args[1]
    response = client.post("/api/auth/otp/verify", json={"phone": "0241234567", "code": "123456"})
    patient = {"Authorization": "Bearer " + response.json()["access_token"]}
    user_id = client.get("/api/session", headers=patient).json()["user_id"]
    created = client.post("/api/admin/pharmacists", headers=admin_token, json={
        "username": "sms-pharm", "email": "sms@example.com", "password": "test-password",
        "full_name": "Test Pharmacist", "license_number": "PH-SMS", "phone": "0201234567",
    })
    assert created.status_code == 200
    login = client.post("/api/auth/pharmacist/login", data={"username": "sms-pharm", "password": "test-password"})
    pharmacist = {"Authorization": "Bearer " + login.json()["access_token"]}
    case = models.PrescriptionHistory(user_id=user_id, status="Pending", case_summary="Test case")
    db.add(case)
    db.commit()
    notify_user = AsyncMock()
    monkeypatch.setattr(main.ws_manager, "notify_user", notify_user)
    monkeypatch.setitem(main.ws_manager.active_connections, user_id, [object()])
    sms.reset_mock()
    response = client.post(f"/api/pharmacist/review/{case.id}", headers=pharmacist,
                           json={"advice": "Test pharmacist feedback", "status": "Reviewed"})
    assert response.status_code == 200, response.text
    notify_user.assert_awaited_once()
    assert notify_user.call_args.args[1]["pharmacist_feedback"] == "Test pharmacist feedback"
    sms.assert_called_once()
    assert sms.call_args.args[0] == "233241234567"
    assert "Test pharmacist feedback" in sms.call_args.args[1]
    reports = client.get("/api/profile", headers=patient).json()["prescriptions"]
    assert any(report["pharmacist_feedback"] == "Test pharmacist feedback" for report in reports)


def test_new_case_sms_targets_verified_available_pharmacists(db, case, monkeypatch):
    import auth
    for index, (verified, available, phone) in enumerate([
        (True, True, "233201234567"), (False, True, "233201234568"),
        (True, False, "233201234569"), (True, True, ""),
    ]):
        db.add(models.Pharmacist(username=f"ph{index}", email=f"ph{index}@example.com",
            hashed_password=auth.get_password_hash("test-password"), license_number=f"PH{index}",
            is_verified=verified, accepting_cases=available, phone=phone))
    db.commit()
    monkeypatch.setattr(main, "_moolre_sms_enabled", lambda: True)
    monkeypatch.setattr(main, "SessionLocal", lambda: db)
    sms = Mock(return_value={"status": "sent"})
    monkeypatch.setattr(main, "_send_moolre_sms", sms)
    main._notify_pharmacists_of_new_case(case.id)
    sms.assert_called_once()
    assert sms.call_args.args[0] == "233201234567"
    assert f"case #{case.id}" in sms.call_args.args[1]
