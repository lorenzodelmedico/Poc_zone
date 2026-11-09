import json
import math
import threading
import time

from app.errors import AppError
from app.http_client import post_json


def dotted_get(data, path):
    for key in path.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


class TokenProvider:
    """Cache uniquement en mémoire ; aucune déduction de durée depuis un JWT."""

    def __init__(self, settings, transport=post_json, clock=time.monotonic):
        self.settings = settings
        self.transport = transport
        self.clock = clock
        self._token = ""
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def invalidate(self):
        with self._lock:
            self._token = ""
            self._expires_at = 0.0

    def get_token(self):
        with self._lock:
            if self._token and self.clock() < self._expires_at:
                return self._token
            s = self.settings
            try:
                extra = json.loads(s.auth_extra_json)
                if not isinstance(extra, dict):
                    raise ValueError
                if not s.auth_id_field or not s.auth_password_field or s.auth_id_field == s.auth_password_field:
                    raise ValueError
            except (TypeError, ValueError):
                raise AppError("AUTH_CONFIG", "Vérifier AUTH_EXTRA_JSON et les noms des champs d'identification.") from None
            payload = {**extra, s.auth_id_field: s.auth_id, s.auth_password_field: s.auth_password}
            result = self.transport(s.auth_url, payload, body_format=s.auth_body_format,
                                    ca_bundle=s.http_ca_bundle, timeout=30)
            token = dotted_get(result, s.auth_token_field)
            if not isinstance(token, str) or not token.strip():
                raise AppError("AUTH_TOKEN_MISSING", "Jeton absent ; vérifier AUTH_TOKEN_FIELD.", 502)
            ttl = dotted_get(result, s.auth_expires_field) if s.auth_expires_field else None
            try:
                ttl = float(ttl)
                ttl = ttl if math.isfinite(ttl) and ttl > 0 else 0
            except (ValueError, TypeError):
                ttl = 0
            self._token = token
            self._expires_at = self.clock() + max(0, ttl - min(30, ttl / 10))
            return token
