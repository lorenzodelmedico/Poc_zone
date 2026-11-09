"""Cache temporaire dans le processus backend principal, sans Streamlit."""
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from weakref import WeakKeyDictionary

_guard = RLock()
_clients = WeakKeyDictionary()


@dataclass
class _Entry:
    lock: RLock = field(default_factory=RLock)
    expires: float = 0.0
    data: dict | None = None


def get_context(api, user_id, loader, *, ttl_s=300, max_users=128):
    """L'identité doit être celle déjà autorisée dans le backend.

    Retourne (copie du contexte, cache_hit). Les chargements d'utilisateurs
    différents ne partagent pas leur verrou. Les erreurs ne sont pas cachées.
    """
    if ttl_s <= 0 or max_users < 1:
        raise ValueError("Configuration du cache invalide.")
    with _guard:
        users = _clients.setdefault(api, {})
        now = monotonic()
        for key, value in list(users.items()):
            if value.data is not None and value.expires <= now:
                del users[key]
        if user_id not in users:
            if len(users) >= max_users:
                users.pop(next(iter(users)))
            users[user_id] = _Entry()
        entry = users[user_id]
    with entry.lock:
        hit = entry.data is not None and entry.expires > monotonic()
        if not hit:
            loaded = loader()
            if not isinstance(loaded, dict) or not isinstance(loaded.get("tables"), dict):
                raise ValueError("Contexte API indisponible ou incomplet.")
            if str(loaded.get("user_id")) != str(user_id):
                raise ValueError("Contexte API associé à une autre identité.")
            entry.data = deepcopy(loaded)
            entry.expires = monotonic() + ttl_s
        return deepcopy(entry.data), hit


def invalidate_context(api, user_id):
    """À appeler lors d'une déconnexion ou d'une invalidation de profil."""
    with _guard:
        _clients.get(api, {}).pop(user_id, None)
