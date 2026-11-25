import hashlib
import os
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from stat import S_ISREG
from tempfile import NamedTemporaryFile
from tokenize import detect_encoding


    def replace_document(self, relative, content):
        """Remplace intégralement un fichier texte UTF-8 existant."""
        if not isinstance(content, str) or not content.strip() or "\x00" in content:
            raise WorkflowError(
                "Un contenu texte complet, non vide et sans caractère NUL est requis."
            )

        try:
            raw = content.encode("utf-8")
        except UnicodeEncodeError:
            raise WorkflowError("Le contenu reçu ne peut pas être encodé en UTF-8.") from None

        if not relative or "\x00" in os.fspath(relative) or Path(relative).anchor:
            raise WorkflowError("Un chemin relatif valide est requis.")

        try:
            target = self.path(relative).resolve()
            if not target.is_relative_to(Path(self.root).resolve()):
                raise WorkflowError("Le fichier doit se trouver dans le projet courant.")

            original_mode = target.stat().st_mode
            if not S_ISREG(original_mode):
                raise WorkflowError("La cible doit être un fichier ordinaire.")

            with target.open(encoding="utf-8") as original:
                for chunk in iter(lambda: original.read(64 * 1024), ""):
                    if "\x00" in chunk:
                        raise WorkflowError("La cible doit être un fichier texte UTF-8.")
        except FileNotFoundError:
            raise WorkflowError("Le fichier à remplacer n'existe pas.") from None
        except UnicodeDecodeError:
            raise WorkflowError("La cible doit être un fichier texte UTF-8.") from None
        except OSError as exc:
            raise WorkflowError(f"Lecture de la cible impossible ({exc.strerror}).") from None

        if target.suffix.casefold() in {".py", ".pyi", ".pyw"}:
            try:
                encoding, _ = detect_encoding(BytesIO(raw).readline)
                decoded = raw.decode(encoding)
                if decoded != content.removeprefix("\ufeff"):
                    raise WorkflowError("La déclaration d'encodage Python changerait le texte reçu.")
                compile(raw, target.name, "exec", dont_inherit=True)
            except SyntaxError as exc:
                location = f" à la ligne {exc.lineno}, colonne {exc.offset}" if exc.lineno else ""
                raise WorkflowError(f"{type(exc).__name__}{location}. {exc.msg}") from None
            except (UnicodeError, LookupError):
                raise WorkflowError("Encodage Python incompatible avec le contenu UTF-8 reçu.") from None

        result = {
            "path": relative,
            "bytes": len(raw),
            "lines": len(content.splitlines()),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

        temporary = None
        try:
            with NamedTemporaryFile(
                mode="wb", dir=target.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = stream.name
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())

            if os.name == "posix":
                os.chmod(temporary, original_mode & 0o777)
            os.replace(temporary, target)
            temporary = None
        except PermissionError:
            raise WorkflowError(
                "Remplacement refusé. Le fichier peut être verrouillé, en lecture seule ou protégé."
            ) from None
        except OSError as exc:
            raise WorkflowError(f"Remplacement impossible ({exc.strerror}).") from None
        finally:
            if temporary is not None:
                with suppress(OSError):
                    os.unlink(temporary)

        return result






    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            openWorldHint=False,
        )
    )
    def replace_document(path: str, content: str) -> dict:
        """Réécrit intégralement un fichier texte UTF-8 existant du projet en mode APPLY.

        path indique le chemin relatif du fichier.
        content contient le texte final complet, indentation et fins de ligne incluses.
        Fournir le contenu brut du fichier, sans clôture Markdown ajoutée autour.
        Les sources Python sont compilées avant le remplacement.
        """
        return call(workflow.workspace.replace_document, path, content)


{"path":"exemple.py","content":"def exemple():\n    return 42\n"}
