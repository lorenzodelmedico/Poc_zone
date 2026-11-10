# Correctifs consolidés — à intégrer dans les modules existants

Ce kit remplace le précédent. Il contient deux modules Python autonomes à copier : `routing.py` et `context_cache.py`. Les autres fonctions sont regroupées dans des blocs de modification des modules existants. Aucun module existant ne doit être remplacé par un bloc d’ajout incomplet.

## Répartition définitive

| Bloc fourni | Destination et opération |
|---|---|
| `app/routing.py`, `app/context_cache.py` | Copier ; conserver le cache séparé du contexte d’identité |
| `app/routes.json`, `app/routing_examples.json` | Copier les catalogues génériques |
| `patches/agent_functions.py` | Remplacer `execute`, `ask`, `validate_document_draft` et ajouter les constantes/fonctions de génération générale |
| `patches/verification_functions.py` | Remplacer les fonctions homonymes ; ajouter les helpers de preuves et de profil |
| `patches/tracking_trace.py` | Remplacer `_trace`, ajouter `source_job_trace` et l’observation embedding |
| `patches/clients_embed.py` | Remplacer la méthode `API.embed`, avec l’indentation de classe |
| `patches/sources_additions.py` | Ajouter à `sources.py` : sélection backend et construction des sources manuelles |
| `patches/sync_additions.py` | Ajouter à `sync.py` : lancement en arrière-plan et suivi UI du travail |
| `patches/sync_chat_method.py` | Ajouter `index_from_chat` à la classe `Synchronizer` |
| `patches/store_observed.py` | Remplacer `Store.observed` et `Store.disable_other_sources` |
| `patches/retrieval_additions.py` | Ajouter le filtre du catalogue à `retrieval.py` |
| `patches/ui_show_review.py` | Remplacer `show_review`, ajouter `document_skill_view` dans `ui.py` |

Les imports placés en tête des blocs doivent rejoindre les imports du module. Les symboles privés des ajouts sont préfixés pour éviter d’écraser ceux de l’existant. Les helpers de l’agent déjà utilisés restent requis : `complete`, `call_tool`, `check_current`, `safe_answer`, `cited_sources`, `citation_checks`, `export_run`, `Access`, `PROMPTS`, `digest`, `utcnow`, etc.

Imports complémentaires de l’agent :
```python
import hashlib
from app.context_cache import get_context
from app.routing import route_question, routing_metrics
from app.verification import (
    PROFILE_PROMPT, profile_catalog, render_profile, context_fingerprint, select_supported,
)
```
Imports complémentaires du vérificateur : `json`, `re`, `os`, `time`, `hashlib`, `Access`, `utcnow`, `safe_error` et `timed_step` déjà employés dans le kit précédent.

## Changements obligatoires dans Synchronizer.once

La signature visible est connue. Ajouter uniquement le paramètre `request_user_id` :
```python
def once(self, force=False, selected_urls=None, extra_user_ids=None, request_user_id=None):
```

Remplacer le bloc qui attribue le même identifiant `sharepoint_manual` à toutes les URL :
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
Chaque URL possède désormais un identifiant stable distinct. Une collecte de B ne considère plus les documents de A comme disparus.

Dans la collecte, remplacer le calcul/suppression des documents disparus par :
```python
gone = known - seen if not manual else set()
```
Conserver ensuite le traitement existant de `gone`. Une collecte manuelle ciblée ne constitue pas un inventaire complet autorisant une purge.

Dans la boucle `for doc in docs`, avant extraction/chunking :
```python
if manual and request_user_id is not None:
    if str(request_user_id) not in {str(x) for x in doc.allowed_user_codes}:
        if self.store.document(doc.id) is not None:
            self.store.observed(doc.id, doc)
        continue
```
Cela actualise les droits connus d’un document existant mais n’envoie pas un document non lisible à l’embedding. L’identité passée doit être celle autorisée par le backend. `extra_user_ids` n’est pas utilisé pour accorder automatiquement des droits.

La ligne d’embedding visible devient :
```python
embedding = self.api.embed([c['text'] for c in chunks])
vectors = embedding['vectors']
self.vectors.publish(chunks, vectors, generation)
```

En fin de `once`, remplacer les opérations globales par :
```python
if not manual:
    configured = [s['id'] for s in self.s.sources()]
    self.store.disable_other_sources(configured)
    self.store.prune(30)
```
Sinon, une indexation depuis le chat peut désactiver les documents manuels qu’elle vient de publier, car ils ne figurent pas dans les sources configurées. La purge des conversations n’a pas non plus à être déclenchée par chaque ajout documentaire.

Le rafraîchissement des permissions des documents inchangés passe par `Store.observed` fourni : la version visible actualisait les métadonnées mais pas les deux champs de permissions. Aucun besoin de forcer le recalcul des embeddings pour ce seul rafraîchissement.

## Collecte partielle dans sources.py

Dans la branche SharePoint de `collect_source`, le `except` extérieur à chaque URL journalise actuellement l’erreur puis fait `continue`. Cela contredit sa promesse « retour complet ou exception » et peut transformer une collecte partielle en inventaire complet.

Remplacer ce `continue` par :
```python
raise RuntimeError('Collecte SharePoint incomplète.') from e
```
Placer la fermeture du client dans un `finally` autour de la boucle pour la garantir également en cas d’exception. Le bloc interne de résolution des permissions peut rester en échec fermé avec une liste de droits vide ; il ne doit pas accorder de droits par défaut.

Le chemin d’erreur de `once` désactive actuellement `known`. Pour une collecte manuelle, éviter cette désactivation globale de la source sur une simple erreur réseau :
```python
if not manual:
    self.store.disable(list(known))
```
Le refus de lecture effectif reste contrôlé par les permissions courantes ; aucune réponse n’est produite à partir d’un lot échoué.

## Branchement réel du chat

Le point d’entrée connu n’est plus un hypothétique `existing_indexer` :
```python
index_existing = synchronizer.index_from_chat
```
`synchronizer` désigne l’instance déjà construite par l’application avec `settings`, `store`, `api`, `vectors`. La méthode utilise `once` et `active_docs_for_user`, effectivement présents dans les photos. Elle inclut les documents déjà à jour et n’invente pas un champ `documents` dans le rapport de synchronisation.

Dans `chat_view`, avant `st.chat_input` :
```python
document_skill_view(
    client, uid, st.session_state.cid,
    index_existing=synchronizer.index_from_chat,
    allowed_roots=configured_sharepoint_roots,
    export_job=lambda job: source_job_trace(mlflow, job, experiment_id),
)
```
Importer `source_job_trace` depuis `tracking.py`. Réutiliser la configuration MLflow et les racines autorisées du backend. Aucun secret ni URL réelle n’est fourni dans ce kit.

**Limite révélée par les photos :** la branche SharePoint visible appelle `get_file_content(url)` pour chaque URL. Elle démontre la collecte de fichiers, pas une exploration récursive d’un site ou d’une bibliothèque. Le branchement ci-dessus est concret pour ces URL de fichiers. L’indexation de tout un site exige de brancher le listing déjà utilisé par le « check SharePoint », s’il existe, avant `once(selected_urls=file_urls, ...)`. Sa signature n’apparaît pas dans les extraits ; aucune méthode de listing n’a été inventée. Le panneau ne doit pas annoncer une bibliothèque entièrement indexée sur la seule réussite de lecture d’un fichier.

## Recherche et vérification

Le gestionnaire MCP `search_documents` doit accepter `document_ids: list[str] | None = None` et appliquer `restrict_document_catalog` du module `retrieval` au catalogue déjà autorisé, avant recherche vectorielle, BM25 et reranking. `[]` reste vide ; `None` conserve le périmètre existant. Ce gestionnaire ne figurait pas dans les photos reçues.

Le routage, le repli général et la vérification conservent le comportement précédent : profil API rapide ; recherche active même sur un thème inconnu ; préambule uniquement après recherche sans réponse ; aucune réutilisation du brouillon après échec du juge ; restitution des blocs supportés.

Le cache API conserve son module : `context.py` ne contient que `current_user_id`, variable d’identité de requête. Aucun cache ni choix documentaire n’est placé dans cette variable. L’exécuteur de synchronisation reste un petit suivi temporaire du travail d’interface ; les écritures documentaires, le verrou d’exclusion et les statistiques de synchronisation continuent à passer par le Store et `once`. Aucun second moteur d’indexation n’est créé.

L’état temporaire des choix et du travail survit aux reruns, pas au redémarrage du backend. Cette consolidation réduit les fichiers, sans prétendre avoir remplacé cet état temporaire par une persistance SQLite nouvelle.

## Migration depuis le kit à neuf modules

Après intégration des blocs et remplacement des imports, retirer seulement les fichiers créés par le kit précédent : `chat_generation.py`, `chat_skill_ui.py`, `embedding_observer.py`, `response_policy.py`, `skills.py`, `source_jobs.py`, `source_scope.py`. Ne pas supprimer les fichiers préexistants ayant d’autres usages.

Remplacements d’import : génération vers `agent`, preuves vers `verification`, UI vers `ui`, instrumentation vers `tracking`, sélection vers `sources`, travaux vers `sync`, filtre vers `retrieval`. Les blocs livrés contiennent déjà les imports actualisés. Vérifier les imports restants avec la recherche de l’IDE avant retrait des anciens fichiers.

Les autres appels d’embedding suivent la même migration : `api.embed(texts)['vectors']`, et `api.embed([query])['vectors'][0]` pour un seul vecteur. Supprimer `return_metadata` uniquement sur `embed`, pas sur `llm`.

Les diagnostics UI et l’amorçage du cache/routeur décrits dans le guide fonctionnel précédent restent applicables, avec ces nouveaux imports. Les tests livrés vérifient les workflows regroupés avec des services synthétiques ; le dépôt réel, la collecte SharePoint et le serveur MLflow ne sont pas exécutés ici.

## Protection contre la synchronisation globale suivante

Les sources manuelles reçoivent le préfixe `chat:`. La seconde méthode de `store_observed.py` empêche le cycle global suivant de désactiver ces sources au motif qu’elles sont absentes de la configuration statique. Leur retrait explicite utilise les opérations de désactivation existantes. Leur rafraîchissement de contenu/droits demeure nécessaire via la synchronisation ciblée et les contrôles d’accès courants ; la conservation d’une source n’accorde aucun droit supplémentaire.
