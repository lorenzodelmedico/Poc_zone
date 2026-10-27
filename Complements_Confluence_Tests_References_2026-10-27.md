# Complément ciblé — Confluence, tests supprimables et lecture d’autres dépôts

## Lecture rapide

Les captures montrent finalement un résultat annoncé comme vérifié, avec un passage de version 12 à 13. Elles montrent aussi des appels de préparation mal remplis, une erreur de type sur les listes de critères et des détours par la configuration locale. Les arguments JSON complets ne sont pas visibles : on ne peut pas conclure qu’une autre personne modifiait réellement la page.

Dans le code livré, version vaut 0 si elle est omise. L’ancien test `version != page["version"]["number"]` signalait alors à tort « la version a changé ». Les espaces et les retours à la ligne du contenu ne participent pas à cette comparaison numérique. Le correctif rapide déjà livré détecte les arguments manquants ; le présent complément ajoute un message qui affiche les deux versions lorsqu’elles diffèrent vraiment.

| Besoin | Changement proposé maintenant | Nouveau fichier de production |
|---|---|---|
| Suppression précise dans Confluence | Action prepare_remove : le backend retire un bloc p/h1-h6 exact et unique, conserve le reste du XHTML et capture la version | Aucun |
| Choix d’une page parmi plusieurs | read(format="metadata") renvoie les titres/URL/versions sans contenu dans le prompt | Aucun |
| Éviter project_facts/config/.env avant Confluence | Description des outils et règle de routage explicites | Aucun |
| Tests fiables et supprimables | run_project_test : fichiers sous tests/agent/, Python du venv cible et load_dotenv | Aucun ; un exemple de test optionnel est fourni |
| Lire un dépôt voisin | read_reference et liste read_repositories dans le harness courant | Aucun |

Je comprends ici « repo test » comme un répertoire de tests dans le dépôt concerné. Cela conserve les deux dépôts existants ; aucun troisième dépôt Git n’est créé automatiquement.

Ce complément réutilise les modules selon leur rôle : parsing/API dans confluence.py, parcours et brouillons dans confluence_tools.py, lecture de fichiers dans workspace.py, exécution dans validation.py, déclarations MCP dans workflow_mcp.py. Pas de nouvelle couche d’orchestration, ni nouvelle dépendance pour le kit.

## Base et ordre d’application

1. Terminer **Correctif_Verification_Modifications_2026-10-26.md**.
2. Appliquer **Correctif_Rapide_Confluence_2026-10-27.md**, que tu as prévu de recopier.
3. Appliquer les blocs du présent document après ces deux correctifs.

Les ancres ci-dessous sont celles de cette succession de livraisons. Elles ne sont pas issues d’un checkout actuel de ton poste. Si une ancre ne correspond plus, conserver tes ajouts et comparer la fonction concernée ; ne pas remplacer un ancien fichier complet.

`<KIT>` = dépôt qui contient continue_kit. `<CIBLE>` = projet configuré par --project dans le MCP actif. Les deux peuvent être identiques.

## A — Suppression Confluence ciblée et versions

### A1 — Fonction de suppression, sans toucher à l’authentification

Fichier : `<KIT>/continue_kit/confluence.py`.
Ajouter la fonction suivante immédiatement avant la ligne de niveau fichier `class Confluence:`. Conserver cette classe et les réglages réseau qui fonctionnent sur ton poste.

```python
def remove_text_block(content, target_text):
    """Retirer un unique paragraphe/titre complet en conservant le reste du XHTML."""
    import unicodedata

    def normalize(text):
        return " ".join(unicodedata.normalize("NFC", text).split())

    if not isinstance(target_text, str) or not normalize(target_text):
        raise WorkflowError("target_text non vide requis pour prepare_remove.")
    checked_content(content)
    offsets, position = [0], 0
    for line in content.splitlines(keepends=True):
        position += len(line)
        offsets.append(position)

    class Blocks(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.matches = [], []

        def source_offset(self):
            line, column = self.getpos()
            return offsets[line - 1] + column

        def handle_starttag(self, tag, attrs):
            if tag in {"br", "hr", "img", "input", "meta", "link", "wbr"}:
                return
            protected = tag.startswith(("ac:", "ri:")) or tag in {"pre", "code", "script", "style"}
            if protected:
                for node in self.stack:
                    node["protected"] = True
            self.stack.append({"tag": tag, "start": self.source_offset(),
                "protected": protected or any(n["protected"] for n in self.stack)})

        def handle_startendtag(self, tag, attrs):
            if tag.startswith(("ac:", "ri:")):
                for node in self.stack:
                    node["protected"] = True

        def handle_endtag(self, tag):
            if not self.stack or self.stack[-1]["tag"] != tag:
                return
            node = self.stack.pop()
            if node["protected"] or tag not in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
                return
            end = content.find(">", self.source_offset()) + 1
            fragment = content[node["start"]:end]
            if normalize(PageText(fragment).text) == normalize(target_text):
                self.matches.append((node["start"], end, tag))

    parser = Blocks()
    parser.feed(content)
    parser.close()
    if len(parser.matches) != 1:
        raise WorkflowError("prepare_remove : " + str(len(parser.matches))
            + " bloc(s) correspondant(s). Un paragraphe ou titre complet unique est requis ; "
              "les macros et blocs de code ne sont pas modifiés.")
    start, end, tag = parser.matches[0]
    body = content[:start] + content[end:]
    return checked_content(body if body.strip() else "<p></p>"), tag
```

Cette fonction compare le texte du bloc après normalisation des espaces et Unicode NFC. Elle exige un paragraphe/titre COMPLET unique. Elle refuse les correspondances multiples, les portions de paragraphe et les contenus dans les macros/blocs de code. Retirer un titre ne retire pas automatiquement les paragraphes de sa section. Si le retrait vide toute la page, un paragraphe vide valide est conservé.

### A2 — Métadonnées des pages sans exposer les corps au modèle

Toujours dans confluence.py, méthode `Confluence.read_many`, remplacer :

```python
        if format not in {"text", "storage"}:
            raise WorkflowError("format doit valoir text ou storage.")
```

par :

```python
        if format not in {"text", "storage", "metadata"}:
            raise WorkflowError("format doit valoir text, storage ou metadata.")
```

Dans cette même méthode, repérer la ligne unique :

```python
                seen.add(str(page["id"]))
```

Ajouter immédiatement après, avant la lecture de `body` :

```python
                if format == "metadata":
                    results.append({**self.public(page), "format": "metadata"})
                    continue
```

### A3 — Import de la fonction de suppression

Fichier : `<KIT>/continue_kit/confluence_tools.py`.
Remplacer l’import :

```python
from .confluence import Confluence, PageText, checked_content
```

par :

```python
from .confluence import Confluence, PageText, checked_content, remove_text_block
```

### A4 — Exposer le changement précis à confirmer

Dans la méthode `ConfluenceTools.public`, repérer :

```python
        result["parent_url"] = draft.get("parent_url")
```

Ajouter juste après :

```python
        if draft.get("change"):
            result["change"] = draft["change"]
```

### A5 — Préparation ciblée et erreurs de version précises

Dans `ConfluenceTools`, remplacer entièrement la méthode `prepare_update`, de sa ligne `def` jusqu’avant la méthode suivante `resume`, par les **trois méthodes** ci-dessous. `_prepare_page` est un petit auxiliaire partagé, qui évite une deuxième lecture HTTP lors d’une suppression ciblée.

```python
    def prepare_update(self, url, title, content, version, checks=None):
        if type(version) is not int or version <= 0:
            raise WorkflowError("prepare_update : version positive lue sur la page requise ; 0 n’est pas une version distante.")
        checks = make_checks(**(checks or {}))
        page = self.api().resolve(url)
        if version != page["version"]["number"]:
            raise WorkflowError(f"prepare_update : version reçue={version}, version distante={page['version']['number']}. "
                                "Relire puis préparer à nouveau ; ne pas modifier le contenu pour corriger un numéro de version.")
        return self._prepare_page(page, title, content, checks)

    def _prepare_page(self, page, title, content, checks, change=None):
        if not title.strip():
            raise WorkflowError("Titre non vide requis.")
        draft = {"draft_id": uuid4().hex, "kind": "page", "title": title.strip(),
                 "base": self.api().base,
                 "page_id": str(page["id"]), "url": self.api().public(page)["url"],
                 "version": page["version"]["number"], "space": page["space"]["key"], "revision": 1, "saved_revision": 0,
                 "pending": {"content": checked_content(content), "checks": checks}, "attempt": None,
                 "change": change}
        with self.workflow._connection() as conn:
            self.store(conn, draft)
        return self.public(draft)

    def prepare_remove(self, url, target_text):
        if not url:
            urls = self.api().urls("CONFLUENCE_PAGE_URLS")
            if len(urls) != 1:
                raise WorkflowError("prepare_remove : fournir url ; la configuration ne contient pas une page cible unique.")
            url = urls[0]
        page = self.api().resolve(url)
        body, tag = remove_text_block(page["body"]["storage"]["value"], target_text)
        checks = make_checks(must_not_contain=[target_text])
        if not check_content(body, checks, confluence=True)["verified"]:
            raise WorkflowError("Le texte reste présent ailleurs dans la page ; préciser la suppression avant de préparer.")
        result = self._prepare_page(page, page["title"], body, checks,
            change={"kind": "remove_block", "tag": tag, "target_text": target_text,
                    "preservation": "Le reste du XHTML est conservé exactement dans la proposition."})
        result["proposal"] = {"checks": checks, "content_chars": len(body)}
        result["next_action"] = "Présenter change et attendre une confirmation écrite ; puis save avec draft_id et revision."
        return result
```

### A6 — Déclaration MCP

Dans la fonction MCP `confluence_pages`, située dans `register_confluence_tools`, remplacer uniquement la ligne du paramètre action :

```python
        action: Literal["read", "guides", "prepare_create", "prepare_update", "save", "resume", "recover"],
```

par :

```python
        action: Literal["read", "guides", "prepare_create", "prepare_update", "prepare_remove", "save", "resume", "recover"],
```

Remplacer sa ligne du paramètre format :

```python
        offset: int = 0, limit: int = 12000, format: Literal["text", "storage"] = "text",
```

par :

```python
        offset: int = 0, limit: int = 12000, format: Literal["text", "storage", "metadata"] = "text",
```

Immédiatement après la ligne `        detail: bool = False,` de cette même signature, ajouter :

```python
        target_text: str = "",
```

Au début de la docstring de `confluence_pages`, après la première phrase `Lire/analyser des pages ou créer/modifier directement un document Confluence.`, ajouter ces lignes à 8 espaces d’indentation :

```python
        Pour supprimer un paragraphe/titre complet fourni par l’utilisateur, appeler directement
        prepare_remove(target_text=texte lisible exact, url=page cible si connue). Si une seule page
        est configurée, omettre url. Le serveur lit le XHTML, trouve un bloc unique, conserve le
        reste et capture sa version. Ne pas lire .env, config.yaml, harness ou project_facts pour cela.
        Ne pas renvoyer tout le document, ni fournir version/content/critères pour prepare_remove.
        Présenter change et attendre confirmation ; save reste inchangé et vérifie l’absence du texte.
        Cette action retire le seul bloc p/h1-h6 correspondant, pas toute la section sous un titre.
        S’il faut identifier une cible parmi plusieurs pages configurées, read(format="metadata")
        renvoie seulement leurs titres, URL et versions ; ne pas charger leur contenu pour cela.
```

Dans la fonction imbriquée `run` de **confluence_pages**, ajouter en première position, avant le contrôle de prepare_update :

```python
            if action == "prepare_remove":
                return tools.prepare_remove(url, target_text)
```

### A7 — Éviter l’inventaire du dépôt pour une opération Confluence

Fichier : `<KIT>/continue_kit/workflow_mcp.py`, docstring de `project_facts`.
Ajouter après sa première phrase `Inventorier les faits structurants et documentables du dépôt.` :

```python
        Pour une opération sur une page Confluence, appeler directement confluence_pages ;
        ne pas inventorier le dépôt ni lire .env/config.yaml/harness pour rechercher ses accès.
```

### Parcours obtenu

Sur une page connue, ou si CONFLUENCE_PAGE_URLS contient une seule page, le modèle appelle directement :

```json
{
  "action": "prepare_remove",
  "target_text": "Un paragraphe ou titre complet à retirer."
}
```

Ajouter url si plusieurs pages sont configurées et que la cible est connue. Le serveur fait un GET, prépare la suppression et fournit draft_id, revision, version et change. Il ne renvoie pas le document complet ni son aperçu à cette étape.

Le modèle présente le retrait ; tu confirmes ; il appelle save(draft_id, revision). La version est contrôlée avant l’écriture, puis le contenu relu est vérifié. Le backend utilise encore le corps complet avec le client REST actuel, mais il ne le fait plus recopier au modèle. Il faut donc normalement **deux appels MCP**, plus éventuellement un read(format="metadata") pour choisir une cible parmi plusieurs.

Un conflit réel à save reste bloquant : aucun écrasement forcé ni réessai aveugle. Il faut préparer à nouveau sur la version courante et faire confirmer la nouvelle proposition. prepare_remove n’est pas un moteur de remplacement général : pour une portion de paragraphe ou une modification complexe, utiliser le parcours prepare_update existant avec la version lue et un vrai tableau de critères, par exemple `must_not_contain=["texte"]`.

## B — Tests supprimables, venv du projet et dotenv

### B1 — Exécuteur des tests de diagnostic

Fichier : `<KIT>/continue_kit/validation.py`.
Dans `run_check`, remplacer :

```python
            argv = [str(interpreter.resolve()) if a == "{python}" else a for a in argv]
```

par :

```python
            argv = [str(interpreter.absolute()) if a == "{python}" else a for a in argv]
```

Cela conserve le chemin d’entrée du venv, y compris si son Python est un lien vers un exécutable système sur les plateformes qui utilisent ce mécanisme.

Ajouter ensuite la fonction complète suivante **à la fin du fichier**, au niveau fichier, après run_check :

```python
def run_project_test(workspace, path, timeout_seconds=60):
    """Exécuter un test jetable avec le venv et le .env du projet cible."""
    target = workspace.path(path)
    if not target.is_relative_to(workspace.root / "tests" / "agent") or target.suffix != ".py" or not target.is_file():
        raise WorkflowError("Test Python existant sous tests/agent/ requis.")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 300:
        raise WorkflowError("0 < timeout_seconds <= 300 requis.")
    profile = workspace.profile()
    configured = profile["python"] or (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    interpreter = Path(configured).expanduser()
    interpreter = interpreter if interpreter.is_absolute() else workspace.root / interpreter
    venv_root = interpreter.parent.parent
    if (not interpreter.is_file() or not (venv_root / "pyvenv.cfg").is_file()
            or not venv_root.resolve().is_relative_to(workspace.root)):
        raise WorkflowError("Configurer python dans harness.json vers le venv local du projet cible ; aucun Python global de secours.")
    bootstrap = (
        "import runpy, sys; from pathlib import Path; from dotenv import load_dotenv; "
        "root=Path(sys.argv[1]); test=Path(sys.argv[2]); "
        "load_dotenv(root / '.env', override=False, encoding='utf-8-sig'); "
        "sys.path.insert(0, str(root)); sys.argv=[str(test)]; "
        "runpy.run_path(str(test), run_name='__main__')"
    )
    result = run_check(workspace, "agent_test", {"argv": ["{python}", "-c", bootstrap,
        str(workspace.root), str(target)], "cwd": ".", "timeout_seconds": timeout_seconds}, str(interpreter))
    return {**result, "test_path": path, "environment": "project_venv", "dotenv": "project_root/.env"}
```

Le .env chargé est celui de la racine du projet CIBLE, dans le processus du test ; les variables déjà définies sont conservées. Le Python doit appartenir à un venv situé dans ce projet ; pas de repli sur le Python global ni sur celui du kit lorsqu’il s’agit d’un autre projet. python-dotenv doit déjà être disponible dans ce venv ; aucune installation de paquet n’est déclenchée.

Dans `<CIBLE>/.continue/harness.json`, conserver les champs existants et vérifier la valeur de python. Sur ton poste Windows, le cas standard est :

```json
"python": ".venv/Scripts/python.exe"
```

C’est une propriété à fusionner avec l’objet JSON existant, pas un remplacement de tout le fichier. Aucun test individuel n’est ajouté aux conditions de démarrage ou aux contrôles obligatoires du projet.

### B2 — Outil MCP

Fichier : `<KIT>/continue_kit/workflow_mcp.py`, dans `build_server`.
Insérer le bloc suivant **après** la ligne existante `    register_confluence_tools(server, workflow, call, env_file)` et **avant** `    return server`. Ne pas dupliquer l’appel d’enregistrement existant.

```python
    @server.tool(annotations=execute)
    def run_project_test(path: str, timeout_seconds: int = 60) -> dict:
        """Exécuter un test autonome déjà créé sous tests/agent/ du projet courant.
        Utilise son venv local et load_dotenv sur son .env, sans Python global de secours.
        Importer l’application depuis le test, jamais l’inverse ; les tests restent supprimables.
        Ne pas créer de test pour exécuter une opération distante réelle non demandée.
        Le résultat donne execution, exit_code et output_path du journal local.
        """
        from continue_kit.validation import run_project_test as execute_test
        return call(execute_test, workflow.workspace, path, timeout_seconds)
```

### B3 — Exemple de fichier de test réellement supprimable

Nouveau fichier **optionnel** : `<KIT>/tests/agent/test_confluence_remove.py`. Créer les deux dossiers s’ils n’existent pas.

Justification : c’est le fichier de test demandé, séparé du code applicatif. Il teste la suppression avec des données synthétiques sans appel HTTP. L’application et les outils MCP ne l’importent pas ; le supprimer, ou supprimer tests/agent/, ne casse pas leur démarrage. Les tests importent l’application, jamais l’inverse.

Contenu complet :

```python
"""Tests supprimables : aucun code applicatif ne doit importer ce fichier."""
from pathlib import Path
import unittest

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False, encoding="utf-8-sig")

from continue_kit.confluence import remove_text_block
from continue_kit.workspace import WorkflowError


class RemoveBlockTests(unittest.TestCase):
    def test_removes_heading_and_preserves_rest_exactly(self):
        before = '<p data-id="keep">Texte conservé.</p>\n'
        after = '\n<p>Suite conservée.</p>'
        source = before + '<h3>Point <strong>temporaire</strong> : A &amp; B</h3>' + after
        result, tag = remove_text_block(source, "Point temporaire : A & B")
        self.assertEqual(tag, "h3")
        self.assertEqual(result, before + after)

    def test_refuses_ambiguous_target(self):
        with self.assertRaises(WorkflowError):
            remove_text_block('<p>Texte.</p><h3>Texte.</h3>', 'Texte.')

    def test_refuses_partial_paragraph(self):
        with self.assertRaises(WorkflowError):
            remove_text_block('<p>Préfixe : Texte.</p>', 'Texte.')

    def test_keeps_section_below_removed_heading(self):
        source = '<h3>Ancien titre</h3><p>Contenu à conserver.</p>'
        self.assertEqual(remove_text_block(source, 'Ancien titre')[0], '<p>Contenu à conserver.</p>')

    def test_refuses_content_inside_macro(self):
        source = ('<ac:structured-macro ac:name="info"><ac:rich-text-body>'
                  '<p>Texte.</p></ac:rich-text-body></ac:structured-macro>')
        with self.assertRaises(WorkflowError):
            remove_text_block(source, 'Texte.')


if __name__ == "__main__":
    unittest.main()
```

Pour cet exemple, depuis la racine du KIT dans Git Bash :

```bash
".venv/Scripts/python.exe" -m unittest discover -s tests/agent -p "test_confluence_remove.py"
```

Ou, si le KIT est le projet cible du MCP actif :

```json
{
  "path": "tests/agent/test_confluence_remove.py",
  "timeout_seconds": 60
}
```

via run_project_test. Pour un autre projet, créer le test de ce projet sous son propre tests/agent/. Les journaux sont rangés dans le dossier d’état du projet ; le résultat distingue passed, failed, timeout et unavailable. Ce mécanisme organise et exécute les tests, il n’isole pas leurs effets comme le ferait une machine virtuelle : utiliser des fixtures et doubles pour les opérations distantes non demandées.

## C — Lire un autre dépôt depuis le projet courant

### C1 — Lecture dédiée dans Workspace

Fichier : `<KIT>/continue_kit/workspace.py`.
Dans la classe Workspace, ajouter cette méthode immédiatement avant `    def snapshot(self, exclude=()):`. Elle est au même niveau que files/path/snapshot. Ne pas élargir la méthode path existante.

```python
    def read_reference(self, repo="", path="", query="", start_line=1, limit=120):
        """Lire un dépôt explicitement référencé, sans élargir les chemins d’écriture."""
        if type(start_line) is not int or start_line < 1 or type(limit) is not int or not 1 <= limit <= 300:
            raise WorkflowError("start_line >= 1 et 1 <= limit <= 300 requis.")
        config_path = self.root / ".continue" / "harness.json"
        config = read_json(config_path) if config_path.exists() else {}
        roots = config.get("read_repositories", {}) if isinstance(config, dict) else None
        if not isinstance(roots, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v.strip()
                                              for k, v in roots.items()):
            raise WorkflowError("harness.json : read_repositories doit associer des noms à des chemins.")
        if not repo:
            return {"read_only": True, "repositories": roots}
        alias = repo if repo in roots else next((key for key, value in roots.items() if value == repo), None)
        if alias is None:
            raise WorkflowError("Dépôt non référencé : ajouter son chemin dans read_repositories du harness du projet courant.")
        root = Path(roots[alias]).expanduser()
        root = root if root.is_absolute() else self.root / root
        reference = Workspace(root)
        exclude = reference.profile()["exclude"]
        result = {"repo": alias, "read_only": True}

        def read_source(name):
            if reference.excluded(name, exclude):
                raise WorkflowError("Fichier exclu du dépôt de référence.")
            target = reference.path(name)
            if not target.is_file() or target.stat().st_size > 2_000_000:
                raise WorkflowError("Fichier texte régulier de 2 Mo maximum requis.")
            try:
                return target.read_text(encoding="utf-8-sig").splitlines()
            except UnicodeError:
                raise WorkflowError("Fichier non lisible en UTF-8.") from None

        if path:
            lines = read_source(path)
            end = min(len(lines), start_line - 1 + limit)
            result.update(path=path, total_lines=len(lines), start_line=start_line,
                          lines=[{"line": i + 1, "text": lines[i]} for i in range(start_line - 1, end)],
                          next_line=end + 1 if end < len(lines) else None)
            return result
        names = reference.files(exclude)
        if not query:
            end = min(len(names), start_line - 1 + limit)
            return {**result, "files": names[start_line - 1:end], "total_files": len(names),
                    "next_line": end + 1 if end < len(names) else None}
        matches, skipped = [], 0
        candidates = names[:1000]
        for name in candidates:
            try:
                lines = read_source(name)
            except (WorkflowError, OSError):
                skipped += 1
                continue
            for number, text in enumerate(lines, 1):
                if query.casefold() in text.casefold() or (number == 1 and query.casefold() in name.casefold()):
                    matches.append({"path": name, "line": number, "text": text[:600]})
                    if len(matches) >= limit:
                        return {**result, "matches": matches, "truncated": True,
                                "skipped_files": skipped, "next_action": "Affiner query ou lire un path précis."}
        return {**result, "matches": matches, "truncated": len(names) > len(candidates), "skipped_files": skipped}
```

### C2 — Enregistrer les dépôts de référence

Fichier : `<CIBLE>/.continue/harness.json`.
Ajouter cette propriété dans l’objet JSON existant en conservant python/checks/exclude et les autres champs :

```json
"read_repositories": {
  "ragdoc": "../ragdoc"
}
```

Penser à la virgule avec les propriétés voisines. Le chemin relatif est résolu depuis la racine du projet cible, indépendamment du terminal. Le nom ragdoc est un alias ; adapter le chemin à ton arborescence.

### C3 — Outil MCP

Dans `<KIT>/continue_kit/workflow_mcp.py`, à l’intérieur de build_server, insérer aussi le bloc suivant avant `    return server`, au même niveau que l’outil ajouté en B2 :

```python
    @server.tool(annotations=read)
    def read_reference(repo: str = "", path: str = "", query: str = "", start_line: int = 1, limit: int = 120) -> dict:
        """Lire/analyser un autre dépôt enregistré dans read_repositories du harness courant.
        repo est son alias ou son chemin enregistré (exemple ../ragdoc). Sans repo, lister les références.
        Sans path/query, lister les fichiers ; query recherche du texte ou un nom de fonction.
        path et start_line lisent un extrait ; suivre next_line si nécessaire. Aucune écriture ni
        exécution de code du dépôt source. Faire les adaptations et le compte rendu dans le projet courant.
        """
        return call(workflow.workspace.read_reference, repo, path, query, start_line, limit)
```

### Utilisation

En mode Agent, tu peux demander :

> Analyse la logique du dépôt ../ragdoc, puis adapte-la dans ce projet. Utilise read_reference pour lire le dépôt source.

Le modèle peut appeler :

```text
read_reference(repo="ragdoc")
read_reference(repo="ragdoc", query="class Confluence")
read_reference(repo="ragdoc", path="app/sources.py", start_line=1, limit=150)
```

Sans repo, l’outil liste les références déclarées. Les résultats de lecture sont bornés et donnent next_line si l’extrait doit être poursuivi. La recherche textuelle est limitée aux 1 000 premiers fichiers admissibles, avec signalement d’une recherche tronquée et des fichiers illisibles. L’outil respecte les filtres, refuse les secrets et la traversée de liens hors des sources. Il ne crée pas de dossier d’état dans le dépôt lu, n’importe pas son code et ne propose aucune écriture distante.

Les outils de modification du kit restent attachés au projet courant. Cela ne transforme pas tous les outils natifs de Continue en un sandbox universel ; cette autorisation de lecture appartient à read_reference. Adapter la logique dans les fichiers du projet courant plutôt que créer implicitement une dépendance d’exécution au dépôt voisin.

## D — Règle active et modèle permanent

Ajouter le bloc suivant à la fin du corps Markdown de **chacun** de ces fichiers :

- `<CIBLE>/.continue/rules/01-coding.md` : copie active maintenant.
- `<KIT>/continue_kit/templates/01-coding.md` : modèle pour les futures installations.

Conserver l’éventuel en-tête YAML et les règles déjà présentes. Ce bloc complète le correctif rapide ; il précise le cas de la suppression ciblée.

```markdown
## Suppressions Confluence, tests et dépôts de référence

- Pour supprimer un paragraphe/titre complet cité par l’utilisateur dans Confluence,
  utiliser directement confluence_pages(action="prepare_remove", target_text=texte).
  Fournir url si la cible est connue ; si une seule page est configurée, l’omettre.
  Pour choisir parmi plusieurs pages, read(format="metadata") suffit à les identifier.
  Ne pas appeler project_facts ou lire config.yaml/.env/harness pour chercher les accès.
- prepare_remove gère le XHTML, la version et les critères ; ne pas les reconstruire
  ni recopier la page. Présenter change, attendre confirmation, puis appeler save.
  En cas d’ambiguïté ou de conflit réel, rapporter l’erreur ; ne pas forcer la sauvegarde.
- Un critère de vérification vérifie uniquement ce qu’il exprime. Ne pas présenter une
  absence de texte comme un test d’exécution ou une validation globale du document.
- Pour un test de diagnostic, créer de préférence un fichier autonome sous tests/agent/
  du projet concerné. Fixtures et doubles pour les effets distants non demandés.
  Le code productif ne doit jamais importer ces fichiers ni en dépendre au démarrage.
  Leur suppression ne doit changer que la disponibilité des tests, pas l’application.
- Exécuter ces tests avec run_project_test. Utiliser le venv du projet cible et charger
  son .env avec load_dotenv ; aucun essai successif avec des Python globaux ou d’autres
  projets. Si l’outil est indisponible, employer explicitement ce venv et load_dotenv
  dans le script. Signaler une dépendance absente plutôt que l’installer à l’aveugle.
- Pour lire un autre dépôt, utiliser read_reference sur les références du harness
  courant. Chercher les fichiers/fonctions utiles puis lire leurs extraits, sans
  importer ou exécuter le dépôt source. Faire les changements et le CR ici.
  Ne pas ajouter implicitement le dépôt source à sys.path ou aux dépendances d’exécution.
```

## Chargement et contrôles

1. Enregistrer les fichiers. Si tu appliques toutes les sections, les fichiers Python modifiés sont confluence.py, confluence_tools.py, workspace.py, validation.py et workflow_mcp.py dans continue_kit.
2. Depuis Git Bash à la racine du KIT :

```bash
".venv/Scripts/python.exe" -m py_compile continue_kit/confluence.py continue_kit/confluence_tools.py continue_kit/workspace.py continue_kit/validation.py continue_kit/workflow_mcp.py
```

3. Recharger VS Code : Ctrl+Shift+P → Developer: Reload Window.
4. Ouvrir une nouvelle conversation **Agent**, avec le profil MCP et le projet cible corrects. Les deux nouveaux outils sont read_reference et run_project_test ; prepare_remove est une action supplémentaire du même outil confluence_pages.
5. Tester d’abord sur une page et un dépôt de test. Vérifier le contenu réel avant de généraliser à des documents utiles.

## Validation de la livraison

81 tests automatisés réussis. Les cinq cas du fichier de test fourni sont aussi exécutés par un de ces contrôles. Couverture : suppression unique, conservation exacte du reste proposé, ambiguïtés, macros, métadonnées seules, version absente/conflit réel, lecture de références et refus des sorties de périmètre, venv réel, priorité dotenv et suppression des tests sans dépendance applicative. Tests sur HTTP/SQLite locaux, vrais sous-processus dans un venv temporaire et schémas Pydantic. Enregistrement FastMCP simulé et python-dotenv doublé dans le venv de test ; ce double vérifie l’appel et la priorité des variables, pas le parseur officiel. Le fichier B3 a aussi été exécuté dans les contrôles locaux. Ce n’est pas une validation sur ton poste Windows ni sur ton instance interne.
