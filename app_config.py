"""Single source of truth for BisaRx process configuration."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
logger = logging.getLogger("bisarx.config")


def _as_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        logger.warning("Invalid value for %s; using %s", name, default)
        return default


def _as_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        logger.warning("Invalid value for %s; using %s", name, default)
        return default


def _origins() -> tuple[str, ...]:
    configured = os.getenv("CORS_ORIGINS", os.getenv("FRONTEND_URL", "http://127.0.0.1:8000"))
    permanent = (
        "https://rx-ai-six.vercel.app",
        "https://openpharmacy.online",
        "https://www.openpharmacy.online",
    )
    return tuple(dict.fromkeys(origin.strip() for origin in (*configured.split(","), *permanent) if origin.strip()))


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    static_dir: Path = BASE_DIR / "static"
    app_env: str = os.getenv("APP_ENV", "production").strip().lower()
    database_url: str = (
        os.getenv("LOCAL_DATABASE_URL", "sqlite:///./rxai.db")
        if os.getenv("APP_ENV", "production").strip().lower() == "development"
        else os.getenv("DATABASE_URL", "sqlite:///./rxai.db")
    )
    secret_key: str = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET") or "dev-secret-change-me"
    jwt_algorithm: str = os.getenv("ALGORITHM", "HS256").strip()
    access_token_expire_minutes: int = _as_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)
    cors_origins: tuple[str, ...] = _origins()
    cors_origin_regex: str = os.getenv(
        "CORS_ALLOW_ORIGIN_REGEX",
        r"https?://(www\.)?openpharmacy\.online|https://rx-ai-[a-z0-9-]*\.vercel\.app",
    )
    llm_api_key: str = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", "dummy_key"))
    llm_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "").strip()
    llm_timeout_seconds: float = _as_float("LLM_TIMEOUT_SECONDS", 45.0)
    llm_max_retries: int = _as_int("LLM_MAX_RETRIES", 2)
    model_name: str = os.getenv("MODEL_NAME", "").strip()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_vision_model: str = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash").strip()
    gemini_vision_timeout_seconds: float = _as_float("GEMINI_VISION_TIMEOUT_SECONDS", 30.0)
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/google/callback"
    ).strip()
    admin_username: str = os.getenv("ADMIN_USERNAME", "").strip()
    admin_password: str = os.getenv("ADMIN_PASSWORD", "").strip()
    admin_access_code: str = os.getenv("ADMIN_ACCESS_CODE", "").strip()
    app_host: str = os.getenv("APP_HOST", "0.0.0.0").strip()
    app_port: int = _as_int("APP_PORT", _as_int("PORT", 8000))
    moolre_base_url: str = os.getenv("MOOLRE_BASE_URL", "https://api.moolre.com").strip().rstrip("/")
    moolre_api_user: str = os.getenv("MOOLRE_API_USER", "").strip()
    moolre_api_key: str = os.getenv("MOOLRE_API_KEY", "").strip()
    moolre_api_pubkey: str = os.getenv("MOOLRE_API_PUBKEY", "").strip()
    moolre_api_vaskey: str = os.getenv("MOOLRE_API_VASKEY", "").strip()
    moolre_account_number: str = os.getenv("MOOLRE_ACCOUNT_NUMBER", "").strip()
    moolre_sms_sender_id: str = os.getenv("MOOLRE_SMS_SENDER_ID", "").strip()
    moolre_business_email: str = os.getenv("MOOLRE_BUSINESS_EMAIL", "").strip()
    moolre_sms_path: str = os.getenv("MOOLRE_SMS_PATH", "/open/sms/send").strip()
    moolre_payment_path: str = os.getenv("MOOLRE_PAYMENT_PATH", "/embed/link").strip()
    moolre_payment_callback_url: str = os.getenv("MOOLRE_PAYMENT_CALLBACK_URL", "").strip()
    moolre_payment_redirect_url: str = os.getenv("MOOLRE_PAYMENT_REDIRECT_URL", "").strip()
    moolre_timeout_seconds: float = _as_float("MOOLRE_TIMEOUT_SECONDS", 20.0)

    @property
    def production_safe(self) -> bool:
        return self.secret_key != "dev-secret-change-me"


settings = Settings()
