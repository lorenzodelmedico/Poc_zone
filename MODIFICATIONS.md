# MODIFICATIONS — intégration détaillée du kit consolidé

## 0. Périmètre et lecture des blocs

Ce guide remplace le `MODIFICATIONS.md` de la livraison annoncée par :

> Le kit est mis à jour à partir des photos, avec un découpage réduit et le raccordement concret à Synchronizer.once().

Il concerne ce kit consolidé, avec deux modules Python autonomes et 27 tests synthétiques. Il ne nécessite pas le ZIP complet publié ensuite. Le complément `DIFF_SHAREPOINT_DEPUIS_KIT_CONSOLIDE.patch` et son guide `INTEGRATION_DIFF_SHAREPOINT.md` restent séparés et s'appliquent après cette base.

Cette réécriture précise les emplacements d'intégration ; elle ne modifie aucun fichier Python ni aucune archive. Les noms de fonctions et les bornes des blocs priment sur les numéros de ligne, qui se décalent après chaque insertion.

### Convention de remplacement

- **Remplacer une fonction entière** : commencer à son `def` ou `async def`, inclure tout son corps, et arrêter avant la fonction, la classe ou l'affectation suivante située au même niveau. Si elle possède un décorateur, inclure aussi ce décorateur dans la sélection.
- **Ajouter au niveau du module** : `def` et affectations commencent en colonne 0, hors de toute classe et de toute fonction.
- **Ajouter une méthode** : `def` commence avec quatre espaces dans la classe ; le corps commence avec huit espaces.
- Les blocs étiquetés **À REPÉRER** sont les sélections exactes à remplacer. Les blocs **REMPLACEMENT** contiennent leur nouveau contenu. Le code adjacent non sélectionné reste en place.
- Les fichiers `patches/*.py` contiennent des blocs à intégrer. Ils ne remplacent jamais les modules complets de l'application et ne sont pas importés sous le nom `patches`.
- Si un symbole du kit a déjà été intégré, le remplacer à son emplacement existant plutôt que d'en créer une deuxième définition.

Les exemples indentés de `sync.py` suivent les quatre espaces utilisés dans les photos. Les fragments volontairement limités à une ligne d'en-tête ne constituent pas des fonctions complètes à exécuter seules.

## 1. Ordre d'intégration et fichiers autonomes

| Ordre | Source du kit | Destination | Opération |
|---:|---|---|---|
| 1 | `requirements-routing.txt` | Environnement Python de l'application | Installer la dépendance déclarée via le registre autorisé |
| 2 | `app/routing.py` | `app/routing.py` | Copier/remplacer ce fichier entier |
| 2 | `app/context_cache.py` | `app/context_cache.py` | Copier/remplacer ce fichier entier |
| 2 | `app/routes.json` | `app/routes.json` | Copier/remplacer ce fichier entier |
| 2 | `app/routing_examples.json` | `app/routing_examples.json` | Copier/remplacer ce fichier entier |
| 3 | `patches/tracking_trace.py` | `app/tracking.py` | Opérations de la section 2 |
| 4 | `patches/clients_embed.py` | `app/clients.py` | Section 3, puis migration de chaque consommateur |
| 5 | `patches/sources_additions.py` | `app/sources.py` | Sections 4 et 5 |
| 6 | `patches/store_observed.py` | `app/store.py` | Section 6 |
| 7 | `patches/sync_additions.py`, `patches/sync_chat_method.py` | `app/sync.py` | Sections 7 et 8 |
| 8 | `patches/verification_functions.py` | `app/verification.py` | Section 9 |
| 9 | `patches/agent_functions.py` | `app/agent.py` | Section 10 |
| 10 | `patches/retrieval_additions.py` | `app/retrieval.py` et gestionnaire MCP | Section 11 |
| 11 | `patches/ui_show_review.py` | `app/ui.py` | Section 12 |

Les quatre fichiers de l'ordre 2 restent dans le même dossier `app/` : `routing.py` lit les deux fichiers JSON à côté de lui. `routing_examples.json` est utilisé par le code livré, y compris pour la construction/calibration du routeur ; il ne doit pas être omis comme un fichier facultatif de tests.

Depuis la racine de l'application, avec le Python du `.venv` actif :

```bash
python -m pip install -r /chemin/du/kit/requirements-routing.txt
python -m pip check
```

Le chemin `/chemin/du/kit/` désigne le dossier extrait, à adapter au chemin local. Aucun modèle supplémentaire n'est ajouté ; le routeur réutilise l'API d'embedding configurée.

## 2. app/tracking.py — remplacer le tracing et ajouter l'observation

### T1. Imports et variable d'observation

**Emplacement :** bloc des imports en tête de `app/tracking.py`, avant `_lock`, `log` et les fonctions.

Ajouter les imports de `patches/tracking_trace.py` s'ils sont absents :

```python
from contextlib import contextmanager
from contextvars import ContextVar
import uuid
```

**Emplacement de l'affectation :** au niveau du module, après les imports, avec les autres variables globales. Ajouter une seule fois :

```python
_embedding_observer_current = ContextVar('embedding_observer', default=None)
```

Conserver les imports déjà nécessaires à `timed_step`, `safe_error`, `export_run`, ainsi que `datetime` utilisé par `_trace`. Si `datetime` n'est plus importé, l'import attendu pour l'expression `datetime.fromisoformat(...)` est `from datetime import datetime`.

### T2. Fonctions à ajouter et fonction à remplacer

| Symbole dans `patches/tracking_trace.py` | Opération dans `app/tracking.py` | Bornes dans la destination |
|---|---|---|
| `observe_embeddings` | Ajouter la fonction entière **avec `@contextmanager`** | Au niveau du module, avant `_trace` ou en fin de fichier hors des autres fonctions |
| `record_embedding_batch` | Ajouter la fonction entière | Même niveau que `observe_embeddings` |
| `_trace` | Remplacer la fonction entière | Du `def _trace(...)` existant à la dernière instruction de son corps ; arrêter avant le prochain `def` de niveau 0 |
| `source_job_trace` | Ajouter la fonction entière | Au niveau du module, après `_trace`, ou remplacer son éventuelle version déjà intégrée |

Il ne faut pas coller tout le fichier fourni à la suite de l'ancien `_trace`, ce qui conserverait deux définitions. La fonction `_trace` du kit remplace le petit snippet de tracing antérieur. `timed_step`, `safe_error`, `_verification_trace` et `export_run` restent présents ; leurs corps ne sont pas remplacés par ce bloc.

Le code d'observation utilise une variable de contexte d'exécution. Sa déclaration reste dans `tracking.py`, pas dans `ui.py`, ni dans la fonction appelée à chaque rendu.

## 3. app/clients.py — remplacer API.embed et migrer ses appels

### E1. Remplacement de la méthode

**À REPÉRER :** dans `class API`, la méthode `def embed(self, texts...)`, située avant la méthode suivante, notamment `def rerank(...)` dans les photos.

**Opération :** remplacer du `def embed` à la fin de son corps par **toute la fonction `embed`** contenue dans `patches/clients_embed.py`, en ajoutant quatre espaces à chaque ligne du bloc fourni. Le `def` reste ainsi dans `class API`. Ne pas remplacer `rerank`, `llm`, `call`, le constructeur ni la fermeture du client.

**Imports, en tête du module :** `time`, `math`, `os` et le helper `endpoint` doivent être disponibles. `time` est le seul import standard nouvellement nécessaire dans les captures ; ne pas supprimer les autres.

### E2. Migration des consommateurs : règle exacte

La méthode renvoie désormais un dictionnaire. Seule la lecture du résultat change lorsqu'un appel consommait une liste de vecteurs.

| Expression à repérer | Remplacement |
|---|---|
| `vectors = api.embed(texts)` | `embedding = api.embed(texts)` puis `vectors = embedding['vectors']` |
| `vector = api.embed([query])[0]` | `vector = api.embed([query])['vectors'][0]` |
| `reply = api.embed(texts, return_metadata=True)` | `reply = api.embed(texts)` ; conserver `reply['vectors']` s'il existe déjà |
| `reply = api.embed(texts, return_metadata=False)` | `reply = api.embed(texts)` ; extraire ensuite `reply['vectors']` pour obtenir la liste |

Dans ce tableau, `api`, `texts` et `query` sont des noms illustratifs : conserver les noms réels et tous les autres arguments de l'appel trouvé. Supprimer `return_metadata` uniquement sur `embed`, jamais sur `llm`.

**Inventaire obligatoire des occurrences :**

```bash
rg -n -C 3 '\.embed\(' app
```

Chaque occurrence consommant directement une liste, un index `[0]`, un `len(...)` ou une itération de vecteurs doit lire `['vectors']` avant cette opération. Les appels déjà migrés de `routing.py` ne doivent pas recevoir un deuxième `['vectors']`. L'occurrence connue de `Synchronizer.once` est modifiée exactement en S5.

Les autres consommateurs ne figurant pas dans les photos ne peuvent pas être désignés par une ligne inventée ; le résultat de cette recherche donne leur emplacement réel.

## 4. app/sources.py — ajouter les fonctions du skill

### A1. Imports

Dans les imports de niveau 0 de `app/sources.py`, ajouter ceux de `patches/sources_additions.py` qui sont absents :

```python
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic
import uuid
```

### A2. Bloc à insérer et niveau exact

**Emplacement :** fin de `app/sources.py`, **après la fin de la fonction `collect_source`**. Dans les photos, la dernière instruction de cette fonction est :

```python
    raise ValueError('Connecteur non implémenté.')
```

Après cette instruction, sortir de la fonction : les nouveaux symboles commencent en colonne 0. Coller le contenu de `patches/sources_additions.py` à partir de `_skills_lock = RLock()` jusqu'au dernier `return sources` de `manual_sharepoint_sources`, inclus. Les imports de ce bloc ont déjà été déplacés en A1.

Le bloc contient ces affectations, toutes à conserver une seule fois : `_skills_lock`, `_skills_states`, `_skills_TTL`, `_skills_LIMIT`.

Il contient ces fonctions : `_skills_key`, `_skills_state`, `get_skill_state`, `set_document_search`, `select_source`, `queue_source`, `update_source`, `document_scope`, `clear_skills`, `manual_sharepoint_sources`.

Les nouvelles fonctions ne sont ni des méthodes de `Confluence`, ni des fonctions internes de `collect_source`. En cas d'intégration antérieure, remplacer les symboles homonymes plutôt que coller une seconde copie. La fonction métier `collect_source` existante reste dans ce fichier ; sa seule modification à cette étape est détaillée en section 5.

## 5. app/sources.py — collecte SharePoint complète ou exception

Cette section concerne la branche fichier du kit de base. Le parcours récursif site/bibliothèque relève du complément SharePoint séparé.

**Fonction :** `collect_source(source, api)`.

**Branche :** `if kind == 'sharepoint':`.

**À REPÉRER :** après la construction de `resolver`, sélectionner le bloc commençant par `docs = []` et finissant par `return docs`, juste avant `if kind == 'confluence_export':`. Cette sélection contient la boucle `for url in urls:`, le `client.close()` existant et les deux traitements d'exception imbriqués. Elle n'inclut ni les imports de la branche, ni la construction du client/résolveur.

**REMPLACEMENT — bloc complet, avec huit espaces au début de `docs = []` :**

```python
        docs = []
        try:
            for url in urls:
                try:
                    content = client.get_file_content(url)
                    title = url.split('/')[-1]
                    try:
                        allowed_user_codes, user_roles = resolver.resolve_permissions(url)
                    except Exception as e:
                        log.warning(f'Could not resolve permissions for SharePoint file {url}: {e}')
                        allowed_user_codes = []
                        user_roles = {}
                    metadata = {}
                    doc = sharepoint_document(sid, url, content, title, metadata)
                    doc.allowed_user_codes = allowed_user_codes
                    doc.user_roles = user_roles
                    docs.append(doc)
                except Exception as e:
                    log.warning(f'Échec de collecte SharePoint pour {url}: {e}')
                    raise RuntimeError('Collecte SharePoint incomplète.') from e
        finally:
            client.close()
        return docs
```

**Vérification visuelle :** le `finally` est aligné avec le nouveau `try` qui précède `for url`; `return docs` est aligné avec `docs = []`. L'ancien `client.close()` placé après la boucle est supprimé puisqu'il est maintenant dans `finally`.

Le `continue` supprimé est celui du **`except` extérieur à chaque URL**, anciennement après le message « Échec de collecte SharePoint ». Il ne faut pas supprimer les `continue` des autres connecteurs. Le `except` interne à la résolution des permissions reste avec une liste de droits vide ; aucun droit de lecture n'est ajouté en cas d'échec.

## 6. app/store.py — remplacer deux méthodes, pas la classe

**Classe :** `Store`.

**Source :** `patches/store_observed.py`.

| Méthode à repérer dans `Store` | Étendue à remplacer | Contenu fourni |
|---|---|---|
| `def observed(self, doc_id, doc=None):` | Ce `def` et tout son corps ; arrêter avant `def generations(...)` dans les photos | Fonction `observed` entière du bloc |
| `def disable_other_sources(self, source_ids):` | Ce `def` et tout son corps ; arrêter avant `def observed(...)` dans les photos | Fonction `disable_other_sources` entière du bloc |

Les fonctions du bloc fourni sont écrites avec `def` en colonne 0. Ajouter quatre espaces à chaque ligne avant insertion dans `class Store`. Le corps d'une méthode commence alors avec huit espaces.

Conserver les helpers `js`, `utcnow` et `placeholders` présents dans le module. Aucune nouvelle table ni modification de `SCHEMA` n'est demandée par ces deux méthodes.

Le résultat attendu est le rafraîchissement des deux champs de permissions dans `observed` et l'exclusion de `source_id LIKE 'chat:%'` de la désactivation globale. Ni `publish`, ni `active_docs_for_user`, ni les méthodes d'écriture des messages ne sont remplacées.

## 7. app/sync.py — ajouts hors classe et méthode dans la classe

### B1. Ajouter le suivi des travaux au niveau du module

Ajouter les imports de `patches/sync_additions.py` aux imports de `app/sync.py`. Conserver ceux déjà présents, notamment `logging`, `time`, `Chunker`, `collect_source`, `pipeline_signature` et `error_text`.

Le bloc fourni ajoute ces imports :

```python
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
import posixpath
from urllib.parse import unquote, urlsplit, urlunsplit, parse_qs, urljoin
import uuid
from app.sources import queue_source, update_source
from app.tracking import observe_embeddings
```

`import time` est aussi dans le bloc fourni, mais il est déjà présent dans les photos ; une occurrence suffit.

**Emplacement du reste du bloc :** fin de `app/sync.py`, **après la fin de la classe `Synchronizer`**, donc après tout le corps de sa méthode `watch`. Coller de `_source_jobs_pool = ThreadPoolExecutor(...)` à la fin de `enqueue_source_sync`, inclus, avec les affectations et les `def` en colonne 0.

Les fonctions ajoutées sont `_source_jobs_parts`, `validate_source_url`, `get_source_job`, `_source_jobs_public`, `_source_jobs_run`, `enqueue_source_sync`. Les affectations `_source_jobs_pool`, `_source_jobs_lock`, `_source_jobs_jobs`, `_source_jobs_MAX_PENDING` doivent aussi être copiées une seule fois.

Ces fonctions ne doivent pas être indentées comme des méthodes de `Synchronizer`. La méthode `index_from_chat`, ci-dessous, est le seul ajout de ce groupe à insérer dans la classe.

### B2. Ajouter index_from_chat dans Synchronizer

**À REPÉRER :** dans `class Synchronizer`, la ligne `def watch(self):`.

**Opération :** insérer la fonction entière `index_from_chat` de `patches/sync_chat_method.py` **juste avant `def watch(self):`**, avec quatre espaces supplémentaires sur toutes les lignes du bloc fourni.

Le code inséré est exactement :

```python
    def index_from_chat(self, user_id, url, report):
        from app.sources import manual_sharepoint_sources
        self.store.user(user_id)
        report('Synchronisation de la source sélectionnée')
        outcome = self.once(selected_urls=[url], request_user_id=user_id)
        if outcome['failures']:
            raise RuntimeError('La synchronisation ciblée a échoué.')
        source_ids = {source['id'] for source in manual_sharepoint_sources([url])}
        documents = self.store.active_docs_for_user(user_id)
        return {'document_ids': [doc['doc_id'] for doc in documents
                                if doc['source_id'] in source_ids], 'complete': True}
```

Après le dernier `return` ci-dessus, `def watch(self):` reprend avec quatre espaces. Son corps existant reste intact. Si `index_from_chat` existe déjà, remplacer cette méthode entière au lieu de l'ajouter une seconde fois.

## 8. app/sync.py — changements obligatoires dans Synchronizer.once

Toutes les modifications S1 à S6 concernent **la même méthode `once`**, dans `class Synchronizer`. Elles ne concernent ni `watch`, ni `_source_jobs_run`.

### S1. Remplacer uniquement la signature

**À REPÉRER :**

```python
    def once(self, force=False, selected_urls=None, extra_user_ids=None):
```

**REMPLACEMENT :**

```python
    def once(self, force=False, selected_urls=None, extra_user_ids=None, request_user_id=None):
```

Conserver les lignes suivantes `chunker = ...`, `signature = ...`, `report = ...` et le `with self.store.sync_lock():`. Le kit de base ne demande pas les arguments `source_report` et `progress` ajoutés ensuite dans le complément SharePoint.

### S2. Remplacer le choix des sources juste après start_sync

**Emplacement :** à l'intérieur de `with self.store.sync_lock():`, après `rid = self.store.start_sync()` et avant `for source in sources:`.

**À REPÉRER — bloc entier :**

```python
            if selected_urls:
                sources = [{'id': 'sharepoint_manual', 'kind': 'sharepoint', 'urls': selected_urls}]
            else:
                sources = self.s.sources()
```

**REMPLACEMENT :**

```python
            manual = selected_urls is not None
            if manual:
                if not selected_urls:
                    raise ValueError('Une URL au moins est requise.')
                from app.sources import manual_sharepoint_sources
                sources = manual_sharepoint_sources(selected_urls)
            else:
                sources = self.s.sources()
```

`manual` commence avec douze espaces, comme `rid`. La boucle `for source in sources:` reste juste après, également à douze espaces. Les anciens commentaires annonçant le remplacement des sources peuvent rester ; l'ancien bloc `if selected_urls` ne doit pas rester en double.

### S3a. Remplacer uniquement le calcul de gone

**Emplacement :** dans `for source in sources:`, dans son premier `try`, immédiatement après `seen = {d.id for d in docs}`.

**À REPÉRER :**

```python
                    gone = known - seen
```

**REMPLACEMENT :**

```python
                    gone = known - seen if not manual else set()
```

Les lignes suivantes `self.store.disable(list(gone))`, la suppression des générations et la mise à jour du rapport restent en place. C'est `gone` qui devient vide lors d'une collecte manuelle, pas tout le bloc qui est supprimé.

### S3b. Protéger la désactivation dans le premier except

**Emplacement précis :** le `except Exception as exc:` associé à la collecte de la source. Ce `except` contient `detail = error_text(exc)` puis `self.store.disable(list(known))`. Il se trouve **avant `for doc in docs:`**.

**À REPÉRER — uniquement cette ligne :**

```python
                    self.store.disable(list(known))
```

**REMPLACEMENT :**

```python
                    if not manual:
                        self.store.disable(list(known))
```

Le `if` commence avec vingt espaces ; son appel `disable` avec vingt-quatre. Les lignes `report['failures'].append(...)`, `log.exception(...)` et `continue` du même `except` restent alignées comme avant, avec vingt espaces. Elles ne doivent pas être déplacées dans le `if`.

Ne pas appliquer ce changement au second `except` d'indexation, qui contient `self.store.disable([doc.id])` : il concerne un document dont le traitement a échoué et reste inchangé.

### S4. Insérer le contrôle des droits juste après le try de la boucle documentaire

**À REPÉRER — ces deux lignes consécutives uniquement :**

```python
                for doc in docs:
                    try:
```

Dans les photos, la ligne suivante est `if not doc.blocks:`. Le contrôle est inséré **avant cette ligne**, avant `old = self.store.document(doc.id)`, avant `gens = ...` et avant les deux branches d'évitement de réindexation. Il n'est pas placé dans `for method in ('plain', 'structure')`.

**REMPLACEMENT des deux lignes sélectionnées :**

```python
                for doc in docs:
                    try:
                        if manual and request_user_id is not None:
                            if str(request_user_id) not in {str(x) for x in doc.allowed_user_codes}:
                                if self.store.document(doc.id) is not None:
                                    self.store.observed(doc.id, doc)
                                continue
```

Après ce remplacement, la première ligne ancienne qui suit doit toujours être :

```python
                        if not doc.blocks:
```

Cette dernière ligne n'est ni supprimée ni déplacée : elle possède le même retrait de vingt-quatre espaces que le nouveau `if manual`.

| Ligne | Espaces au début | Appartenance |
|---|---:|---|
| `for doc in docs:` | 16 | Corps de la boucle des sources |
| `try:` | 20 | Corps de la boucle des documents |
| `if manual and request_user_id is not None:` | 24 | Corps du `try` documentaire |
| `if str(request_user_id) not in ...:` | 28 | Corps du contrôle manuel |
| `if self.store.document(doc.id) is not None:` | 32 | Cas sans droit de lecture |
| `self.store.observed(doc.id, doc)` | 36 | Document déjà présent dans le Store |
| `continue` ajouté | 32 | Cas sans droit de lecture ; passe au document suivant |
| `if not doc.blocks:` existant | 24 | Reprise du traitement documentaire existant |

Le `continue` ne doit pas être à trente-six espaces : il doit aussi s'exécuter pour un document absent du Store. Il ne doit pas être à vingt-quatre espaces : cela ignorerait tous les documents.

Dans ce kit, `collect_source` a déjà téléchargé et parsé les documents avant ce passage. Ce contrôle empêche leur indexation/embedding dans ce chemin ; il n'est pas un contrôle placé avant téléchargement. Le complément SharePoint séparé apporte ce placement plus précoce.

### S5. Remplacer l'appel d'embedding dans la boucle des méthodes

**Emplacement précis :** toujours dans le `try` documentaire, mais plus bas, dans `for method in ('plain', 'structure'):`. La ligne est située **après la fin de `for i, c in enumerate(chunks):`** et son affectation de `chunk_id`, et avant `manifests.append(...)`.

**À REPÉRER — ces deux lignes :**

```python
                            vectors = self.api.embed([c['text'] for c in chunks])
                            self.vectors.publish(chunks, vectors, generation)
```

**REMPLACEMENT :**

```python
                            embedding = self.api.embed([c['text'] for c in chunks])
                            vectors = embedding['vectors']
                            self.vectors.publish(chunks, vectors, generation)
```

Les trois lignes commencent avec vingt-huit espaces, comme `chunks = chunker.chunks(doc, method)` dans la même boucle. Elles ne doivent pas entrer dans la boucle `for i, c`, dont le corps est à trente-deux espaces : l'API doit être appelée pour le lot, pas une fois par chunk.

Conserver `manifests.append(...)`, `old_keys = self.store.publish(...)` et le nettoyage des anciennes générations à leurs emplacements actuels.

### S6. Remplacer le nettoyage global en fin de once

**Emplacement :** après la fin de `for source in sources:`, à l'intérieur du `with self.store.sync_lock():`, juste avant `self.store.finish_sync(...)` et `return report`.

**À REPÉRER — seulement ces trois lignes :**

```python
            configured = [s['id'] for s in self.s.sources()]
            self.store.disable_other_sources(configured)
            self.store.prune(30)
```

**REMPLACEMENT :**

```python
            if not manual:
                configured = [s['id'] for s in self.s.sources()]
                self.store.disable_other_sources(configured)
                self.store.prune(30)
```

Les deux lignes suivantes restent en place, **hors du `if not manual`**, avec douze espaces :

```python
            self.store.finish_sync(rid, report['changed'], len(report['failures']))
            return report
```

Le nettoyage conditionnel se termine donc avant `finish_sync`. La synchronisation manuelle doit toujours clôturer son rapport et le retourner.

### S7. Vérifier la position du rafraîchissement des permissions

Les appels `self.store.observed(doc.id, doc)` des branches « document inchangé » restent en place. Ils utilisent désormais la méthode remplacée en section 6, qui met aussi à jour les permissions. Aucune insertion dans ces branches ni recalcul forcé des embeddings n'est demandé.

## 9. app/verification.py — remplacements et ajouts explicites

### V1. Imports

Ajouter aux imports du module, s'ils sont absents :

```python
import hashlib
import json
import re
import unicodedata
import os
import time
```

Conserver les imports existants de `Access`, `utcnow`, `safe_error` et `timed_step`, utilisés par le code livré. Les helpers de preuves sont désormais définis dans ce même module : ne pas garder un import depuis l'ancien `app.response_policy` pour ces mêmes symboles.

### V2. Affectations

| Symbole dans `patches/verification_functions.py` | Emplacement | Opération |
|---|---|---|
| `PROFILE_PROMPT` | Après les imports, avant les fonctions | Ajouter l'affectation entière, ou remplacer la précédente |
| `_response_policy_LABELS` | Au même endroit | Ajouter le dictionnaire entier |
| `VERIFY_PROMPT` | À son emplacement existant | Remplacer l'affectation complète, de `VERIFY_PROMPT =` à la fermeture de sa chaîne multiligne, sans inclure le `def` suivant |

### V3. Fonctions

**Remplacer entièrement, à leur emplacement actuel :** `extract_claims`, `parse_review`, `verify_answer`.

**Ajouter au niveau du module, avant `extract_claims` :** `_response_policy_canonical`, `_response_policy_hash`, `context_fingerprint`, `_response_policy_escape`, `profile_catalog`, `render_profile`, `check_proofs`, `extract_blocks`, `select_supported`.

Le corps de chaque fonction est celui du symbole homonyme dans `patches/verification_functions.py`. Toutes commencent en colonne 0 ; aucun de ces helpers n'est une fonction interne de `verify_answer`.

Si l'ensemble avait déjà été ajouté, remplacer ces définitions en place et ne pas garder une ancienne fonction du même nom plus bas dans le fichier. Un ancien `parse_review` situé après le nouveau annulerait le remplacement au chargement du module.

Le stockage du résultat de vérification et le mode brouillon sont déjà gérés dans le corps fourni de `verify_answer` : aucun second appel manuel au vérificateur n'est à ajouter dans le chat.

## 10. app/agent.py — remplacement des parcours

### G1. Imports

Dans le bloc d'imports de `app/agent.py`, ajouter ou compléter :

```python
import hashlib
import json
import os
import time
from app.context_cache import get_context
from app.routing import route_question, routing_metrics
from app.sources import document_scope
from app.verification import (
    PROFILE_PROMPT,
    profile_catalog,
    render_profile,
    context_fingerprint,
    select_supported,
    verify_answer,
)
```

Conserver les helpers et imports existants utilisés par le bloc : `Access`, `PROMPTS`, `digest`, `utcnow`, `complete`, `mcp_session`, `call_tool`, `check_current`, `safe_answer`, `cited_sources`, `citation_checks`, `identify_theme`, `timed_step`, `safe_error`, `export_run`.

Cette liste ne crée pas des implémentations nouvelles de ces helpers. Si un de ces noms n'existe pas dans le module ou ses imports actuels, c'est une interface locale à raccorder ; il ne faut pas inventer sa provenance en déplaçant du code au hasard.

### G2. Affectations et fonctions à intégrer

| Symbole fourni dans `patches/agent_functions.py` | Opération et emplacement |
|---|---|
| `NO_DOCUMENTARY_ANSWER`, `NO_DOCUMENTS_PREFIX`, `GENERAL_PROMPT` | Ajouter les trois affectations au niveau du module, après les imports et avant les fonctions ; remplacer leurs versions éventuelles |
| `generate_general` | Ajouter la fonction entière au niveau du module, juste avant `execute` |
| `execute` | Remplacer tout l'ancien `async def execute(...)` et son corps ; arrêter avant la prochaine définition de même niveau |
| `ask` | Remplacer tout l'ancien `async def ask(...)` et son corps |
| `validate_document_draft` | Ajouter la fonction entière après `ask`, ou remplacer sa version déjà intégrée |

`execute` et `ask` restent des fonctions `async`, au niveau du module. Leurs corps ne sont pas des fragments à fusionner ligne par ligne avec l'ancienne implémentation. Le bloc complet fourni prend en charge le routage, la recherche, la génération, la vérification, le stockage et l'export existant.

L'ancien appel de vérification situé à l'intérieur de l'ancien `execute` disparaît avec le remplacement complet de cette fonction. Il ne faut pas le recopier à la suite : cela provoquerait un second contrôle. La fonction nouvelle appelle `validate_document_draft`, qui appelle déjà `verify_answer`.

### G3. Vérifier les signatures des helpers locaux

Le corps livré appelle notamment `access.visible_messages(user_id, cid, context=context)`, `access.user_context(user_id)`, `complete(..., trace_input=...)` et `call_tool(session, name, arguments, steps)`. Ces interfaces doivent correspondre aux helpers réels. Leurs définitions complètes ne sont pas toutes visibles dans les captures ; elles ne sont pas remplacées par ce guide.

## 11. app/retrieval.py et gestionnaire MCP — périmètre avant la recherche

### R1. Ajouter le filtre au module retrieval

Ajouter la fonction entière `restrict_document_catalog` de `patches/retrieval_additions.py` **en fin de `app/retrieval.py`, au niveau du module**, après la fin de sa dernière fonction/classe. Le `def` commence en colonne 0. Aucun nouvel import n'est requis par ce helper.

Si cette fonction existe déjà dans le module, remplacer sa définition entière plutôt que l'ajouter en double.

### R2. Adapter search_documents : interface non visible dans les photos

**Recherche de l'emplacement réel :**

```bash
rg -n -C 8 'def search_documents|async def search_documents|search_documents' app/mcp_server.py app/retrieval.py
```

Le point à modifier est la fonction enregistrée comme outil MCP `search_documents`, pas l'appel à cet outil dans `agent.py` : ce dernier est déjà présent dans le bloc G2.

1. Dans les imports du module contenant le gestionnaire, ajouter `from app.retrieval import restrict_document_catalog` si le gestionnaire est dans un autre module.
2. Dans sa signature existante, ajouter `document_ids: list[str] | None = None`, en conservant les autres paramètres et son éventuel décorateur MCP. Si le gestionnaire délègue la recherche à une autre fonction, lui transmettre ce paramètre jusqu'au point où le catalogue autorisé est disponible.
3. Juste après l'obtention du catalogue déjà autorisé pour l'identité backend, appliquer `restrict_document_catalog(catalogue, document_ids)` et utiliser ce résultat pour les deux recherches, vectorielle et BM25, puis le reranking. Ne pas placer le filtre après le reranker ou après la génération.
4. Si le catalogue filtré est vide, retourner le format vide du gestionnaire existant sans lancer une recherche globale. `[]` ne doit jamais être remplacé par le catalogue complet au moyen de `document_ids or ...`.

La transformation est : ancienne liste autorisée → `restrict_document_catalog(ancienne_liste_autorisée, document_ids)` → recherche existante. Le nom réel de cette liste et la signature de la fonction de recherche n'apparaissent pas dans les photos : un bloc « avant/après » littéral serait inventé ici. Ce raccordement est identifié comme restant à reporter sur ce corps réel, et non comme déjà effectué par la copie du kit.

## 12. app/ui.py — fonctions, cache et emplacement du panneau

### U1. Ajouter les imports du panneau

Dans le bloc des imports de `app/ui.py`, ajouter ceux placés en tête de `patches/ui_show_review.py` :

```python
from app.sources import get_skill_state, set_document_search, select_source
from app.sync import enqueue_source_sync, get_source_job
from app.tracking import source_job_trace
from app.context_cache import get_context
```

`asyncio`, `st` et `Access` sont déjà utilisés par la vue existante et restent importés. Si `app.tracking` est déjà importé dans une même ligne pour `export_run`, ajouter `source_job_trace` à cette ligne au lieu de supprimer `export_run`.

### U2. Intégrer les deux fonctions du bloc UI

**`show_review` :** dans `app/ui.py`, sélectionner de `def show_review(verification):` à la dernière ligne de son corps, avant le prochain `def` de niveau 0. Remplacer cette fonction entière par celle de `patches/ui_show_review.py`.

**`document_skill_view` :** ajouter la fonction entière du bloc fourni au niveau du module, **juste avant `def chat_view(uid, client):`**. Son `def` commence en colonne 0, comme celui de `chat_view`. Ne pas l'insérer dans le corps de `chat_view`. Si elle existe déjà, remplacer sa définition entière.

Ses appels sont décrits en U4. La seule définition de `document_skill_view` ne fait pas apparaître le panneau dans le chat.

### U3. Retirer le profil complet de st.session_state

Dans `chat_view`, les captures montrent deux blocs successifs :

- le bloc commenté « Priming des données utilisateur », avec `if 'user_data' not in st.session_state:` et `st.session_state.user_data = data_api.fetch_full_user_context(...)` ;
- le bloc commenté « Récupération et affichage du profil », qui relit `st.session_state.get('user_data', {})`, appelle `clean_api_response`, puis contient le cas invité.

**Suppression exacte :** enlever ces deux blocs, depuis le commentaire « Priming des données utilisateur » jusqu'à la fin de leur branche `elif st.session_state.get('is_guest', False):`, sans enlever la ligne suivante `st.title('Assistant RH')`. Conserver le bloc initial qui initialise `selected_user_id` et `is_guest`. Ne pas supprimer `data_api = DataAPI(client)` s'il est encore utilisé pour la sélection utilisateur.

**À REPÉRER ensuite, dans la même fonction :**

```python
    access = Access(s, store, client)
    with st.sidebar:
```

**REMPLACEMENT de ces deux lignes :**

```python
    access = Access(s, store, client)
    if not st.session_state.get('is_guest', False):
        get_context(client, uid, lambda: access.user_context(uid))
    with st.sidebar:
```

`with st.sidebar:` conserve tout son corps existant : nouvelle discussion, historique et effacement. Le cache de profil reste dans le backend. Cette modification reprend le préchargement du profil ; elle ne crée pas de nouveau profil à afficher dans la session UI.

### U4. Insérer l'appel du panneau exactement avant st.chat_input

**À REPÉRER :** dans `chat_view`, après la boucle d'affichage de l'historique, la ligne :

```python
    submitted = st.chat_input('Question ou précision')
```

**REMPLACEMENT de cette seule ligne :**

```python
    document_skill_view(
        client, uid, st.session_state.cid,
        index_existing=synchronizer.index_from_chat,
        allowed_roots=configured_sharepoint_roots,
        export_job=lambda job: source_job_trace(mlflow, job, experiment_id),
    )
    submitted = st.chat_input('Question ou précision')
```

Le `document_skill_view(` commence avec quatre espaces. Il est **hors** de `for message in access.visible_messages(...)` : sinon le panneau serait rendu une fois par message. Il est aussi hors de `with st.sidebar:`. Les lignes suivantes `question = ...` et `if question:` restent en place.

Les noms `synchronizer`, `configured_sharepoint_roots`, `mlflow` et `experiment_id` sont des **raccordements locaux obligatoires**, pas des variables créées par les blocs du kit. Leur valeur doit être établie avant cet appel :

| Nom attendu par le fragment | Objet réel à réutiliser | Emplacement de son alias |
|---|---|---|
| `synchronizer` | Instance existante de `Synchronizer(settings, store, api, vectors)` utilisée par l'indexation ; ou instance construite avec les mêmes quatre objets backend | Avant `document_skill_view`, dans la portée de `chat_view`, ou dans un helper backend déjà utilisé par cette vue |
| `configured_sharepoint_roots` | Liste des racines HTTPS autorisées par la configuration backend | Avant l'appel ; aucune URL fixe inventée dans la vue |
| `mlflow` | Module/client déjà utilisé par l'export configuré | Dans les imports ou la portée où l'export est initialisé |
| `experiment_id` | Identifiant d'expérience réel déjà obtenu par l'export | Avant l'appel ; même configuration que l'export existant |

Les photos ne montrent pas la fabrique réelle de l'index vectoriel ni la récupération de l'expérience MLflow. Il n'est donc pas possible de donner une affectation exacte pour ces quatre alias sans inventer des attributs de `Settings` ou du Store. Ce tableau désigne explicitement la partie à raccorder ; le bloc U4 ne peut pas être copié comme si ces noms existaient automatiquement.

La fonction métier passée à `index_existing` est bien `synchronizer.index_from_chat`, ajoutée en B2. Il ne faut pas passer la fonction UI de l'ancien bouton « check SharePoint » au worker.

### U5. Remplacer le traitement de la question par la version avec progression

**Emplacement :** dans `chat_view`, dans le `else` qui traite une question de taille valide, après l'affichage du message utilisateur.

**À REPÉRER — bloc entier :**

```python
            try:
                with st.spinner('Recherche et préparation de la réponse…'):
                    asyncio.run(ask(s, store, client, uid, st.session_state.cid, question))
            except Exception as exc:
                problem(exc)
            else:
                st.rerun()
```

La chaîne du spinner peut avoir des points différents ; les repères stables sont le `try`, le `with st.spinner`, l'appel à `ask`, puis son `except/else`.

**REMPLACEMENT :**

```python
            try:
                with st.status('Traitement de la demande', expanded=True) as status_box:
                    def progress(label):
                        status_box.update(label=label)
                        status_box.write(label)
                    result = asyncio.run(ask(
                        s, store, client, uid, st.session_state.cid, question,
                        profile_enabled=not st.session_state.get('is_guest', False),
                        on_progress=progress,
                    ))
                    status_box.update(label='Traitement terminé', state='complete', expanded=False)
            except Exception as exc:
                problem(exc)
            else:
                st.rerun()
```

`try`, `except` et `else` commencent avec douze espaces ; ils restent dans le traitement de la question valide. `def progress` est une petite fonction interne au bloc de progression, avec vingt espaces. Ce callback est passé à `ask`, pas au constructeur du client.

Le corps fourni de `ask` prend déjà en charge la vérification avant l'enregistrement/affichage de la réponse. Aucun appel supplémentaire à `verify_answer` n'est ajouté après `asyncio.run`.

### U6. Amorçage du routeur : facultatif

Le routeur est construit au premier appel si aucun préchargement n'est effectué. Un préchargement facultatif peut être placé dans `chat_view` après la création du client/backend, avant `st.chat_input` : import de `warm_router` depuis `app.routing`, puis `asyncio.run(warm_router(client))`. Ce préchargement n'est pas nécessaire au raccordement du panneau et ne remplace aucune étape obligatoire ci-dessus.

## 13. Retirer les imports de l'ancien découpage, si ces fichiers ont été installés

Cette section n'est utile que si les modules supplémentaires d'une livraison antérieure ont été effectivement copiés. Une livraison jamais appliquée n'a rien à désinstaller.

| Ancien module ajouté par le kit | Destination des symboles dans le kit consolidé |
|---|---|
| `app.chat_generation` | `app.agent` |
| `app.chat_skill_ui` | `app.ui` |
| `app.embedding_observer` | `app.tracking` |
| `app.response_policy` | `app.verification` |
| `app.skills` | `app.sources` |
| `app.source_jobs` | `app.sync` |
| `app.source_scope` | `app.retrieval` |

**Ordre :** intégrer les nouvelles définitions, remplacer les imports qui pointent vers ces anciens modules, puis retirer uniquement les fichiers ajoutés par cet ancien kit. Ne pas supprimer `context.py` : il contient le contexte d'identité `current_user_id`, distinct du cache de profil.

Dans le module qui contient désormais les définitions, ne pas ajouter un import vers lui-même. Exemple : `check_proofs` est défini dans `verification.py` ; ce fichier n'a pas besoin de `from app.verification import check_proofs`.

Recherche des références restantes :

```bash
rg -n 'chat_generation|chat_skill_ui|embedding_observer|response_policy|app\.skills|app\.source_jobs|app\.source_scope' app
```

Les noms privés `_response_policy_*` ou `_embedding_observer_current` restent volontairement dans les modules consolidés. Ce sont les **imports de modules supprimés** qu'il faut retirer, pas les noms privés qui ont été conservés pour éviter les collisions.

## 14. Contrôles de fin d'intégration

### Contrôles mécaniques

Depuis la racine applicative :

```bash
python -m compileall -q app
python -m pip check
rg -n -C 3 '\.embed\(' app
rg -n 'def once|def index_from_chat|def observed|def disable_other_sources' app/sync.py app/store.py
```

La compilation détecte des erreurs de syntaxe/indentation, pas les objets manquants ni les divergences de signatures au moment de l'appel. Les commandes de tests fournies par le kit s'exécutent depuis son dossier extrait :

```bash
python -m unittest discover -s validation -p 'test_*.py' -q
```

Les 27 tests du kit consolidé utilisent des services synthétiques ; ils ne valident pas à eux seuls le raccordement au dépôt réel.

### Vérification ciblée de once

- [ ] `manual` est défini après `start_sync`, avant la boucle des sources.
- [ ] `gone` est conditionné par `manual` dans le `try` de collecte.
- [ ] La désactivation de `known` est conditionnelle uniquement dans le `except` de collecte.
- [ ] Le contrôle `if manual and request_user_id ...` est dans le `try` de `for doc in docs`, juste avant `if not doc.blocks`.
- [ ] Le `continue` ajouté possède trente-deux espaces, pas trente-six ni vingt-quatre.
- [ ] L'embedding est dans la boucle des méthodes, hors de la boucle de numérotation des chunks.
- [ ] `finish_sync` et `return report` restent hors du `if not manual` final.
- [ ] `index_from_chat` est une méthode de `Synchronizer`, pas une fonction interne de `once` ni une fonction de niveau 0.

### Raccordements qui ne peuvent pas être inventés

Le corps exact du gestionnaire MCP `search_documents`, les objets backend de création de l'index vectoriel et l'initialisation MLflow ne sont pas visibles dans les extraits disponibles. Les sections R2 et U4 distinguent donc les transformations requises des noms locaux à raccorder. Les signatures des helpers listées en G3 doivent également être vérifiées dans l'application.

Le kit de base ne prouve que la collecte des URL de fichiers déjà fournies. L'entrée d'une URL de site ou de bibliothèque et son exploration récursive utilisent le complément SharePoint séparé. Le présent guide peut être suivi pour intégrer la base sans appliquer ce complément ; il ne promet pas que le panneau de la base sait déjà explorer un site entier.

L'état du skill et des travaux est temporaire dans le processus backend : il survit aux reruns de la vue, pas au redémarrage du backend. Aucune persistance supplémentaire n'est créée par cette documentation.
