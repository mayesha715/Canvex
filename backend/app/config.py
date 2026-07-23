import json
from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# asyncpg rejects these libpq query params; the app negotiates SSL itself.
_ASYNCPG_INCOMPATIBLE_QS = {"sslmode", "channel_binding"}


def _normalize_database_url(url: str) -> str:
    """Managed Postgres providers (Render, Railway, Heroku) hand out URLs like
    ``postgres://…`` or ``postgresql://…`` with libpq query params. The app's
    async engine needs the ``postgresql+asyncpg://`` driver and can't accept
    ``sslmode``. Rewrite both so the same code runs locally and in production."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url.split("://", 1)[0]:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    parts = urlsplit(url)
    if parts.query:
        kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in _ASYNCPG_INCOMPATIBLE_QS]
        url = urlunsplit(parts._replace(query=urlencode(kept)))
    return url


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://canvex:canvex@localhost:5432/canvex"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me-in-development"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    gemini_api_key: str = ""
    gemini_vision_model: str = "gemini-1.5-pro"
    gemini_embedding_model: str = "models/text-embedding-004"
    api_base_url: str = "http://localhost:8000"
    environment: str = "development"
    # Google OAuth client ID (the "Web application" OAuth 2.0 client from Google
    # Cloud Console). Blank → the "Sign in with Google" button stays hidden and
    # POST /auth/google returns 503. The client ID is public, so the backend is
    # the single source of truth and serves it to the frontend via /auth/config.
    google_client_id: str = ""
    # Allowlist for "Institutional Login". Comma-separated domain suffixes, e.g.
    # "mit.edu,edu.bd" or just "edu". Empty → any academic-looking address
    # (domain containing ".edu" or ".ac.") is accepted. See email_is_institutional.
    institutional_email_domains: Annotated[list[str], NoDecode] = []
    # None → auto: run migrations on boot in production only (plan 13.7).
    # Override with RUN_MIGRATIONS_ON_STARTUP=true/false.
    run_migrations_on_startup: bool | None = None
    # NoDecode: keep pydantic-settings from JSON-parsing the env value so the
    # validator below can accept a plain comma-separated string (a JSON string
    # env var still crashes without this).
    cors_allow_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _fix_database_url(cls, value: object) -> object:
        return _normalize_database_url(value) if isinstance(value, str) else value

    @field_validator("cors_allow_origins", "institutional_email_domains", mode="before")
    @classmethod
    def _split_list(cls, value: object) -> object:
        # Accept a comma-separated string (friendlier for dashboard env vars)
        # or a JSON array; a Python list passes through unchanged.
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @property
    def migrate_on_startup(self) -> bool:
        if self.run_migrations_on_startup is not None:
            return self.run_migrations_on_startup
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def email_is_institutional(email: str, allowed_domains: list[str] | None = None) -> bool:
    """Whether an email belongs to an institution.

    With an explicit allowlist, the domain must end with one of the entries
    (so "edu.bd" matches "univ.edu.bd" and "mit.edu" matches exactly). With an
    empty allowlist, fall back to a generic academic heuristic: the domain
    contains ".edu" or ".ac." (covers .edu, .edu.bd, .ac.uk, .ac.bd, …)."""
    domain = email.strip().lower().rsplit("@", maxsplit=1)[-1]
    if not domain or "." not in domain:
        return False
    domains = allowed_domains if allowed_domains is not None else settings.institutional_email_domains
    if domains:
        return any(domain == d.lower() or domain.endswith("." + d.lower().lstrip(".")) for d in domains)
    return ".edu" in domain or ".ac." in domain
