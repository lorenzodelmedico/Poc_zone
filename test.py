                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            previous = self.read().get("instance")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        command = [sys.executable, "-m", "continue_kit", "--env-file", str(self.env_file)]
                                                                                       #!/usr/bin/env python3
"""Point d'entree Open WebUI pour le proxy existant de continue_kit.

Emplacement : racine du depot contenant continue_kit/, a cote du .env.
Git Bash / Windows, avec le Python du kit deja configure :
    ./.venv/Scripts/python.exe openwebui_relay.py --copy-key
Configuration privee ailleurs : ajouter --env-file "C:/chemin/config/.env".

Open WebUI installe avec pip sur le MEME poste :
    Parametres > Administration > Connexions > OpenAI > Ajouter
    URL        : http://127.0.0.1:5010/v1
    Auth       : Bearer
    Cle API    : coller la cle LOCALE copiee par --copy-key
    Model IDs  : laisser vide ; les alias viennent de /v1/models
    Connexion  : serveur/backend (connexion directe navigateur desactivee)
Le terminal reste ouvert ; Ctrl+C arrete ce relais. --port change son port.

Contrat reutilise : settings.load_config(env_file), proxy.create_app(config).
Le proxy gere deja les certificats, l'acquisition/cache/renouvellement du jeton,
le mapping des modeles, les erreurs et les reponses JSON/SSE. Aucun jeton amont
n'est manipule ici. La protection locale intervient AVANT les hooks du proxy.
La cle locale est conservee hors du depot : ~/.openwebui-relay/local.key.
Sans --copy-key, son contenu peut etre copie depuis ce fichier local.

Les hooks existants du proxy, dont un eventuel historique ConversationStore,
restent actifs : aucune isolation de cet historique n'est ajoutee. Les outils
MCP de Continue et l'orchestration Streamlit ne deviennent pas des outils Open
WebUI par ce lancement. Les champs tools/tool_choice restent transmis par le
proxy ; leur execution depend du client ou de l'agent effectivement branche.

Validation : protection et lancement verifies sur substituts WSGI et modules
synthetiques sous Linux ; aucun essai Windows, Open WebUI ou API interne.
Base projet : INSTALLATION_ET_FICHIERS_COMPLETS.md et lots Continue 1A/1B.
References publiques, ponderation editoriale indicative (hors base projet) :
40 % https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
20 % https://docs.pylonsproject.org/projects/waitress/en/stable/usage.html
15 % https://flask.palletsprojects.com/en/stable/patterns/streaming/
15 % https://docs.python.org/3.12/library/wsgiref.html
10 % https://docs.python.org/3.12/library/secrets.html
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess


def read_local_key(path):
    """Creer une cle locale une fois, sans toucher au .env ni aux acces API."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(secrets.token_urlsafe(32))
    key = path.read_text(encoding="ascii").strip()
    if len(key) < 32 or any(not 33 <= ord(c) <= 126 for c in key):
        raise ValueError("Cle locale invalide.")
    return key


class LocalBearer:
    """Authentifier sans consommer le corps ni l'iterateur de reponse SSE."""

    def __init__(self, application, key):
        self.application = application
        self.expected = ("Bearer " + key).encode("ascii")

    def __call__(self, environ, start_response):
        health = (environ.get("PATH_INFO") == "/health"
                  and environ.get("REQUEST_METHOD") == "GET")
        supplied = environ.get("HTTP_AUTHORIZATION", "").encode("utf-8")
        if not health and not secrets.compare_digest(supplied, self.expected):
            body = json.dumps({"error": {
                "type": "authentication_error", "code": "local_auth_required",
                "message": "Cle locale Open WebUI absente ou incorrecte."
            }}).encode("utf-8")
            start_response("401 Unauthorized", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("WWW-Authenticate", "Bearer"), ("Cache-Control", "no-store")
            ])
            return [body]
        forwarded = dict(environ)
        forwarded.pop("HTTP_AUTHORIZATION", None)
        return self.application(forwarded, start_response)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Relais Open WebUI via continue_kit.")
    parser.add_argument("--env-file", help="Le meme .env que le kit existant.")
    parser.add_argument("--port", type=int, default=5010)
    parser.add_argument("--copy-key", action="store_true",
                        help="Copier uniquement la cle locale dans le presse-papiers Windows.")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port doit etre compris entre 1024 et 65535.")
    try:
        from continue_kit.settings import KitError, load_config
        from continue_kit.proxy import create_app
        from waitress import serve
    except ImportError:
        raise SystemExit("Chargement impossible : fichier attendu a la racine du kit, "
                         "avec son Python et ses dependances deja installes.") from None
    try:
        config = load_config(args.env_file)
        key = read_local_key(Path.home() / ".openwebui-relay" / "local.key")
        application = LocalBearer(create_app(config), key)
        if args.copy_key:
            subprocess.run(["clip.exe"], input=key.encode("ascii"), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Cle LOCALE copiee : collage dans le champ Cle API d'Open WebUI.", flush=True)
        print(f"API Open WebUI : http://127.0.0.1:{args.port}/v1", flush=True)
        print("Ctrl+C arrete ce relais.", flush=True)
        serve(application, host="127.0.0.1", port=args.port, threads=config.threads,
              expose_tracebacks=False)
    except KitError as error:
        raise SystemExit(str(error)) from None
    except KeyboardInterrupt:
        pass
    except Exception as error:
        raise SystemExit(f"Echec du relais ({type(error).__name__}). "
                         "Verifier le port et le fichier de cle locale ; "
                         "sans clip.exe, relancer sans --copy-key.") from None


if __name__ == "__main__":
    main()                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 command += [item for p in args.project for item in ("--project", p)]
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        options = ({"creationflags": subprocess.DETACHED_PROCESS}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   if os.name == "nt" else {"start_new_session": True})
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     close_fds=True, **options)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 self.wait_ready(process, previous)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             return True
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     if not self.acquire():
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 self.wait_ready()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             return True
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     self.publish("starting")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             return False
