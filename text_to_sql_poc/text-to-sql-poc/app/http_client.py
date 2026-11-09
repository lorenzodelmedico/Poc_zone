import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler

from app.errors import AppError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Les identifiants et en-têtes restent sur l'URL configurée.
        return None


def post_json(url, payload, *, headers=None, body_format="json", ca_bundle="", timeout=30):
    if urlparse(url).scheme not in {"http", "https"}:
        raise AppError("HTTP_CONFIG", "URL HTTP/HTTPS requise.")
    if body_format not in {"json", "form"}:
        raise AppError("HTTP_CONFIG", "Le format du corps doit valoir json ou form.")
    try:
        context = ssl.create_default_context(cafile=ca_bundle or None)
        body = (json.dumps(payload).encode("utf-8") if body_format == "json"
                else urlencode(payload).encode("utf-8"))
        request = Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json" if body_format == "json" else "application/x-www-form-urlencoded",
            "Accept": "application/json", **(headers or {}),
        })
        opener = build_opener(HTTPSHandler(context=context), NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise AppError("HTTP_RESPONSE_TOO_LARGE", "Réponse amont trop volumineuse.", 502)
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except HTTPError as exc:
        raise AppError("UPSTREAM_HTTP", f"Le service amont a retourné HTTP {exc.code}.", 502) from None
    except (URLError, TimeoutError, OSError):
        raise AppError("UPSTREAM_CONNECTION", "Connexion amont impossible ; vérifier réseau, délai et certificat.", 502) from None
    except (ValueError, UnicodeError):
        raise AppError("UPSTREAM_JSON", "Le service amont n'a pas retourné un objet JSON valide.", 502) from None
