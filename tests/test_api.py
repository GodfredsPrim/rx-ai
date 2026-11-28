"""HTTP contracts with real validation and persistence, mocked external services."""
from datetime import datetime
from unittest.mock import Mock

import pytest
import main


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    datetime.fromisoformat(response.json()["timestamp"])


@pytest.mark.parametrize("route", ["/", "/pharmacist", "/admin", "/waitlist", "/waitlist/qr"])
def test_portals(client, route):
    response = client.get(route)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_chat_validation_and_auth(client):
    assert client.post("/api/chat", json={"messages": [{}]}).status_code == 401
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/missing").status_code == 404


def test_chat_route_passes_authenticated_intake_to_engine(client, db, monkeypatch):
    import models, auth
    user = models.User(username="patient", email="patient@example.com", hashed_password="unused")
    db.add(user)
    db.commit()
    token = auth.create_access_token({"sub": user.email})
    engine = Mock(return_value={"reply": "When did it start?", "drugs": [],
                                "consulting": False, "error": None})
    monkeypatch.setattr(main.chat_engine, "process_chat", engine)
    messages = [{"role": "user", "content": "My head hurts"}]
    response = client.post("/api/chat", json={"messages": messages}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["reply"] == "When did it start?"
    assert engine.call_args.kwargs["messages"] == messages
    assert engine.call_args.kwargs["user_id"] == user.id
    assert engine.call_args.kwargs["skip_summary"] is True


def test_guest_contact_persists_and_sends_mock_sms(client, db, case, monkeypatch):
    sms = Mock(return_value={"status": "sent"})
    monkeypatch.setattr(main, "_send_moolre_sms", sms)
    response = client.post(f"/api/cases/{case.id}/guest-contact",
                           json={"phone": "+233 24 123 4567", "full_name": "Test Patient"})
    assert response.status_code == 200
    db.refresh(case)
    assert case.guest_phone == "+233241234567"
    assert case.case_summary.startswith("Test Patient - ")
    assert sms.call_args.args[0] == "+233241234567"


def test_guest_contact_errors(client, case):
    assert client.post("/api/cases/99999/guest-contact", json={"phone": "0241234567"}).status_code == 404
    assert client.post(f"/api/cases/{case.id}/guest-contact", json={"phone": "letters"}).status_code == 400
    assert client.post(f"/api/cases/{case.id}/guest-contact", json={}).status_code == 422


@pytest.mark.parametrize("payment,expected", [
    ({"status": "initialized", "reference": "test-reference", "payment_url": "https://example.invalid/pay"}, "pending"),
    ({"status": "skipped"}, "not_configured"),
    ({"status": "error"}, "failed"),
])
def test_guest_order_payment_outcomes(client, db, case, monkeypatch, payment, expected):
    gateway = Mock(return_value=payment)
    monkeypatch.setattr(main, "_init_moolre_payment", gateway)
    response = client.post(f"/api/cases/{case.id}/guest-order", json={
        "delivery_address": "Test address", "phone_number": "+233 24 123 4567"})
    assert response.status_code == 200
    db.refresh(case)
    assert case.status == "Ordered"
    assert case.payment_status == expected
    gateway.assert_called_once()


def test_guest_order_rejects_wrong_phone_and_unreviewed_case(client, db, case, monkeypatch):
    gateway = Mock()
    monkeypatch.setattr(main, "_init_moolre_payment", gateway)
    route = f"/api/cases/{case.id}/guest-order"
    order = {"delivery_address": "Test address", "phone_number": "0000"}
    assert client.post(route, json=order).status_code == 403
    case.status = "Pending"
    db.commit()
    order["phone_number"] = case.guest_phone
    assert client.post(route, json=order).status_code == 400
    gateway.assert_not_called()


@pytest.mark.parametrize("route", ["/api/chat", "/api/chat/stream", "/api/cases/guest"])
def test_intake_requires_login(client, route):
    assert client.post(route, json={}).status_code == 401


def test_saved_reply_in_portal(client, db, case):
    import models, auth
    user = models.User(username="replypatient", email="reply@example.com", hashed_password="unused")
    db.add(user)
    db.flush()
    case.user_id = user.id
    case.drug_name = "Review completed"
    case.details = "Patient guidance"
    case.pharmacist_feedback = "Your pharmacist guidance"
    db.commit()
    token = auth.create_access_token({"sub": user.email})
    result = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200
    assert result.json()["prescriptions"][0]["pharmacist_feedback"] == "Your pharmacist guidance"
