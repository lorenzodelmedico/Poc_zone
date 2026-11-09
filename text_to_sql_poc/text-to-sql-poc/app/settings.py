import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.errors import AppError

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    metadata_path: Path
    llm_chat_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout: int = 120
    llm_max_tokens: int = 1800
    auth_url: str = ""
    auth_id: str = ""
    auth_password: str = ""
    auth_id_field: str = "id"
    auth_password_field: str = "password"
    auth_body_format: str = "json"
    auth_token_field: str = "access_token"
    auth_expires_field: str = "expires_in"
    auth_extra_json: str = "{}"
    http_ca_bundle: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""
    db_user: str = ""
    db_token_mode: str = "password"
    db_sslmode: str = "verify-full"
    db_sslrootcert: str = ""
    db_connect_timeout: int = 10
    max_rows: int = 500
    statement_timeout_ms: int = 10000

    def check_live(self):
        required = {
            "LLM_CHAT_URL": self.llm_chat_url, "LLM_MODEL": self.llm_model,
            "AUTH_URL": self.auth_url, "AUTH_ID": self.auth_id,
            "AUTH_PASSWORD": self.auth_password, "PGHOST": self.db_host,
            "PGDATABASE": self.db_name, "PGUSER": self.db_user,
        }
        missing = [key for key, value in required.items()
                   if not value or re.search(r"<[A-Z][A-Z0-9_]*>", value)]
        if missing:
            raise AppError("CONFIG_INCOMPLETE", "Configuration à compléter : " + ", ".join(missing))
        if self.db_token_mode not in {"password", "custom"}:
            raise AppError("CONFIG_INVALID", "DB_TOKEN_MODE doit valoir password ou custom.")
        if self.db_sslmode not in {"verify-full", "verify-ca", "require"}:
            raise AppError("CONFIG_INVALID", "PGSSLMODE doit valoir verify-full, verify-ca ou require.")
        if not 1 <= self.max_rows <= 5000 or not 100 <= self.statement_timeout_ms <= 60000:
            raise AppError("CONFIG_INVALID", "MAX_ROWS : 1 à 5000 ; STATEMENT_TIMEOUT_MS : 100 à 60000.")


def load_settings() -> Settings:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    values = {}
    for field in Settings.__dataclass_fields__.values():
        if field.name == "metadata_path":
            continue
        env_name = {
            "db_host": "PGHOST", "db_port": "PGPORT", "db_name": "PGDATABASE",
            "db_user": "PGUSER", "db_sslmode": "PGSSLMODE",
            "db_sslrootcert": "PGSSLROOTCERT",
        }.get(field.name, field.name.upper())
        value = os.getenv(env_name)
        if value is not None:
            values[field.name] = int(value) if isinstance(field.default, int) else value
    path = Path(os.getenv("METADATA_PATH", "config/metadata.local.json"))
    return Settings(metadata_path=path if path.is_absolute() else ROOT / path, **values)
