"""Offline fixtures: never use a developer database, credentials, or network."""
import os
import httpx
from unittest.mock import patch

import pytest

# Set before app_config is imported, including by the existing smoke tests.
os.environ.update(APP_ENV="test", DATABASE_URL="sqlite://", SECRET_KEY="offline-test-only")
for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "ABENA_API_KEY",
             "MOOLRE_API_USER", "MOOLRE_API_KEY", "MOOLRE_API_PUBKEY", "MOOLRE_API_VASKEY",
             "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ADMIN_PASSWORD", "ADMIN_ACCESS_CODE",
             "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_SENDER"):
    os.environ[name] = ""
os.environ["DEEPSEEK_API_KEY"] = "offline-test-only"

# Both configuration modules load dotenv at import time; tests must ignore local .env.
with patch("dotenv.load_dotenv", return_value=False):
    import main

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import models


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    def override_db():
        yield db
    main.app.dependency_overrides[main.get_db] = override_db
    # No lifespan startup: schema is created above; production migrations/seeds must not run.
    test_client = TestClient(main.app)
    try:
        yield test_client
    finally:
        test_client.close()
        main.app.dependency_overrides.clear()


@pytest.fixture
def case(db):
    record = models.PrescriptionHistory(status="Reviewed", guest_phone="+233241234567",
                                        case_summary="Headache for two days", payment_amount=10)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
