# workspace.py — imports et constante au niveau du module
import re
from threading import Lock

_DOCUMENT_WRITE_LOCK = Lock()

    def replace_block(self, relative, old_text, new_text):
        if not old_text:
            raise WorkflowError("Le bloc à rechercher est vide.")

        target = self.path(relative).resolve()
        if not target.is_relative_to(Path(self.root).resolve()) or not target.is_file():
            raise WorkflowError("Un fichier existant du projet est requis.")

        try:
            original = target.read_bytes()
            text = original.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            raise WorkflowError("Impossible de lire le fichier en UTF-8.") from None

        # Accepte un bloc envoyé en LF même si le fichier utilise CRLF.
        eol = re.compile(r"\r\n|(?<!\r)\n")
        pattern = re.compile(
            r"(?:\r\n|(?<!\r)\n)".join(re.escape(line) for line in eol.split(old_text))
        )
        match = pattern.search(text)
        if match is None:
            raise WorkflowError("Bloc introuvable. Relire les lignes exactes.")
        if pattern.search(text, match.start() + 1):
            raise WorkflowError("Bloc ambigu. Ajouter des lignes de contexte.")

        ending = eol.search(match.group()) or eol.search(text)
        replacement = eol.sub(ending.group() if ending else "\n", new_text)
        updated = text[:match.start()] + replacement + text[match.end():]
        return self.replace_document(relative, updated, expected_original=(target, original))


    def replace_document(self, relative, content, *, expected_original=None):

            with _DOCUMENT_WRITE_LOCK:
                if expected_original is not None:
                    if (target, target.read_bytes()) != expected_original:
                        raise WorkflowError("Le fichier a changé. Relire le bloc.")
                os.replace(temporary, target)








    # workflow_mcp.py — à la place du décorateur et de la fonction replace_document
    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            openWorldHint=False,
        )
    )
    def replace_block(path: str, old_text: str, new_text: str) -> dict:
        """Outil par défaut en phase APPLY pour modifier quelques lignes.

        old_text reprend le bloc exact, indentation comprise, avec assez de contexte
        pour identifier une seule occurrence. new_text contient son remplacement.
        Si le bloc est absent ou ambigu, relire les lignes et préciser old_text.
        """
        return call(workflow.workspace.replace_block, path, old_text, new_text)

    @server.tool(annotations=document_write)
    def replace_document(path: str, content: str) -> dict:
        """En phase APPLY, réservé à une réécriture intégrale explicitement prévue.

        path désigne le fichier texte existant, relatif au projet.
        content contient le texte brut du fichier final entier.
        Toute modification localisée relève de replace_block.
        """
        return call(workflow.workspace.replace_document, path, content)


- Pour une modification localisée, lire les lignes concernées avec `read_reference`, puis appeler `replace_block`.
- Si le bloc est absent, ambigu ou obsolète, relire les lignes et ajouter du contexte dans `old_text` pour obtenir une seule correspondance.
- Réserver `replace_document` aux réécritures intégrales prévues par la demande ou le plan validé.
