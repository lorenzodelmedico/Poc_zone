# Intégration — routage générique, skill documentaire et vérification

Cette version cumulative remplace le kit précédent et la proposition seule. Les fichiers fournis constituent du code à intégrer ; le dépôt réel de l’application n’est pas monté ici. La réutilisation du « check SharePoint » s’effectue par un raccordement à sa fonction métier existante : aucune nouvelle ingestion SharePoint n’est créée.

## 1. Contenu à copier et fonctions à remplacer

Copier les fichiers de `app/` dans le répertoire `app/` de l’application.

| Fichier | Fonction |
|---|---|
| `app/context_cache.py` | Cache backend du profil API, repris du kit précédent |
| `app/response_policy.py` | Preuves API/documentaires et restitution des blocs validés |
| `app/routing.py` | Aurelio Semantic Router, politique des skills et repli conversationnel |
| `app/routes.json` | Capacités génériques et phrases représentatives |
| `app/routing_examples.json` | Calibration, tests sémantiques distincts et cas d’orchestration |
| `app/chat_generation.py` | Réponse générale et préambule après absence de réponse documentaire |
| `app/skills.py` | Sources et activation du skill par identité et conversation, dans le backend |
| `app/source_jobs.py` | Lancement asynchrone de la fonction d’indexation existante |
| `app/chat_skill_ui.py` | Panneau URL/sources et progression dans le chat |
| `app/source_scope.py` | Intersection entre documents autorisés et documents sélectionnés |
| `app/embedding_observer.py` | Observation des lots pendant l’indexation, sans second appel API |

Les fichiers de `patches/` contiennent les fonctions à insérer ou remplacer dans les modules existants. Ce ne sont pas des modules à importer sous le nom `patches`.

| Fichier fourni | Destination |
|---|---|
| `patches/clients_embed.py` | Remplacer `API.embed()` dans `app/clients.py`, avec l’indentation des méthodes de la classe |
| `patches/agent_functions.py` | Remplacer `execute()`, `ask()` et ajouter `validate_document_draft()` dans `app/agent.py` ; conserver les imports placés en tête du fichier fourni |
| `patches/verification_functions.py` | Remplacer `VERIFY_PROMPT`, `extract_claims()`, `parse_review()`, `verify_answer()` dans `app/verification.py` |
| `patches/tracking_trace.py` | Remplacer `_trace()` et ajouter `source_job_trace()` dans `app/tracking.py` |
| `patches/ui_show_review.py` | Remplacer `show_review()` dans `app/ui.py` |

Les helpers de l’agent déjà présents, le Store et `export_run()` restent utilisés. Ce kit n’invente pas leurs signatures internes.

## 2. Dépendances et imports

Installer le paquet direct épinglé avec le registre autorisé de l’environnement :

```bash
python -m pip install -r requirements-routing.txt
python -m pip check
```

Les dépendances transitives ne constituent pas un verrouillage complet. Le panneau utilise `st.popover`, son paramètre `icon`, `st.toggle` et `st.fragment` : Streamlit 1.40 ou ultérieur est requis pour les API utilisées. La version déployée reste à vérifier dans l’environnement cible.

Dans `app/clients.py`, ajouter `import time` si absent. Les imports `math`, `os` et le helper `endpoint` utilisés par la méthode existaient dans les captures.

Dans `app/agent.py`, ajouter les imports suivants aux imports existants :

```python
import hashlib
from app.context_cache import get_context
from app.routing import route_question, routing_metrics
from app.response_policy import (
    PROFILE_PROMPT, context_fingerprint, profile_catalog, render_profile, select_supported,
)
```

Le fichier de remplacement importe directement `document_scope` et les fonctions de réponse générale.

Dans `app/verification.py` :

```python
import hashlib
from app.response_policy import check_proofs, context_fingerprint, extract_blocks, profile_catalog
```

## 3. Embedding — contrat unique et migration des appels

`API.embed(texts)` renvoie toujours un dictionnaire avec `vectors`, `model`, `usage`, `usage_batches` et `batches`. Le paramètre `return_metadata` est supprimé pour cette méthode, pas pour `API.llm()`.

Le changement concerne surtout l’exploitation du résultat. L’appel `api.embed(texts)` demeure syntaxiquement valide.

```python
# Ancien appel consommant directement la liste :
vectors = api.embed(texts)
# Remplacement :
vectors = api.embed(texts)['vectors']
```

```python
# Ancien appel pour un seul vecteur :
query_vector = api.embed([query])[0]
# Remplacement :
query_vector = api.embed([query])['vectors'][0]
```

```python
# Ancien appel demandant les métadonnées :
reply = api.embed(texts, return_metadata=True)
# Remplacement :
reply = api.embed(texts)
```

Pour conserver les métadonnées à disposition du code appelant :

```python
embedding = api.embed(texts)
vectors = embedding['vectors']
usage = embedding['usage']
```

Le consommateur connu dans `app/routing.py` est déjà migré. Les consommateurs non disponibles dans les captures, notamment l’ingestion et la recherche, doivent recevoir ce remplacement mécanique :

```bash
rg -n -C 8 '\.embed\(' app
```

Aucune couche acceptant alternativement l’ancienne liste et le nouveau dictionnaire n’est ajoutée. `on_batch` reste une option d’observation, utile pour enregistrer un lot échoué avant qu’une exception empêche le retour. Les tokens manquants restent inconnus : `usage` additionne seulement les compteurs reçus.

## 4. Routage et comportements

Le catalogue sémantique comporte `profile`, `documents`, `mixed`. Il décrit des capacités, pas les sujets contenus dans les sources. `general` et `clarify` sont des issues d’orchestration.

| Situation | Traitement |
|---|---|
| Profil seul identifié | Cache API, un appel LLM pour choisir les champs, réinjection des valeurs exactes ; aucune recherche documentaire |
| Skill actif, besoin combiné identifié | Documents sélectionnés et profil API |
| Skill actif, autre demande ou abstention sémantique | Recherche documentaire, quel que soit le sujet |
| Skill inactif, demande hors profil | Réponse générale |
| Reprise conversationnelle reconnue | Classification et reformulation dans un même appel LLM |
| Source sélectionnée en cours d’indexation ou échouée | État indisponible, sans prétendre que la recherche n’a rien trouvé |

Le skill est désactivé par défaut dans le chat. Son activation sans source sélectionnée utilise le périmètre autorisé déjà indexé. L’ajout d’une URL active automatiquement le skill et sélectionne cette source.

Une question autonome sans route suffisamment étayée ne déclenche plus un classifieur LLM uniquement pour classer son thème : la politique du skill fixe le parcours. Le classifieur reste utilisé pour les reprises conversationnelles repérées ; cette détection reste une heuristique limitée, comme dans le kit précédent.

Une recherche terminée sans document exploitable déclenche le LLM général. Si des passages ont été retrouvés mais ne permettent aucune réponse, le générateur peut produire uniquement le marqueur d’abstention documentaire défini dans `chat_generation.py`, puis un appel général répond à la question.

Le backend ajoute alors ce préambule :

> Je n’ai pas trouvé d’informations relatives à votre question dans la base documentaire consultée. Voici ce que je sais sur le sujet, indépendamment de ces documents.

Cette décision ne repose pas sur le seul nom de route. L’abstention du générateur reste un jugement du modèle et peut comporter des faux négatifs ; ce n’est pas une preuve d’absence de toute information dans l’ensemble du corpus.

Une erreur de recherche n’est pas traitée comme une recherche vide. Une erreur du juge, ou un brouillon dont aucun bloc n’est supporté, ne déclenche pas le parcours général et ne permet pas de réafficher le brouillon.

Sans outil fournissant des prévisions météo récentes, le parcours général explique cette limite sans inventer de prévisions. Les réponses documentaires antérieures ne sont pas réinjectées comme des connaissances générales ; ce parcours conserve uniquement les questions utilisateur récentes.

## 5. Réutiliser le « check SharePoint » depuis le chat

Le nouveau code ne sait pas le nom de la fonction métier appelée par le bouton existant. Le raccordement consiste à transmettre cette fonction, et non à recréer la découverte, l’extraction ou les embeddings.

Le contrat du petit adaptateur est :

```python
def index_source_for_chat(user_id, url, report):
    report('Lecture et indexation du SharePoint')
    result = existing_indexer(user_id, url)
    return {'document_ids': [doc['doc_id'] for doc in result['documents']]}
```

`existing_indexer` représente ici **l’appel métier déjà utilisé par le check SharePoint**, à remplacer par son nom et ses paramètres réels. Ce snippet est le point de raccordement, pas une fonction existante supposée. Si l’indexeur renvoie déjà `document_ids`, retourner directement cette liste dans le dictionnaire attendu. S’il ne renvoie qu’un compteur, récupérer les identifiants par son opération de Store déjà disponible ; un compteur seul ne permet pas de restreindre les recherches à la source sélectionnée.

La liste doit représenter les documents indexés du périmètre choisi et lisibles par la personne connectée, y compris ceux déjà à jour dans l’index. La nouvelle URL doit remplacer l’ancienne URL fixe dans cet appel ; indexer silencieusement une autre source est invalide.

L’adaptateur peut appeler `report(label, completed, total)` pour enrichir la progression, mais le fonctionnement ne dépend pas d’un nouveau callback dans l’indexeur.

Ne pas appeler une fonction qui rend des widgets Streamlit depuis le worker. Réutiliser la fonction métier appelée par l’ancien bouton. Si le Store ou le client utilisé dépend du thread qui l’a créé, les instancier via leur constructeur habituel dans l’adaptateur du worker.

Le résolveur et les contrôles de lecture existants restent responsables de l’autorisation SharePoint et des redirections finales. Les racines autorisées passées au nouveau panneau proviennent de la configuration backend, jamais d’un champ saisi par l’utilisateur.

## 6. Panneau dans `app/ui.py`

Ajouter :

```python
from app.chat_skill_ui import document_skill_view
from app.tracking import source_job_trace
```

Dans `chat_view()`, après validation de l’identité et de la conversation, juste avant `st.chat_input()` :

```python
document_skill_view(
    client, uid, st.session_state.cid,
    index_existing=index_source_for_chat,
    allowed_roots=configured_sharepoint_roots,
    export_job=lambda job: source_job_trace(mlflow, job, experiment_id),
)
```

Les trois noms locaux à raccorder sont explicites : l’adaptateur de la section précédente, les racines SharePoint déjà configurées et le client/id d’expérience MLflow initialisés comme dans l’export existant. `mlflow` et `experiment_id` ne sont pas de nouvelles API du Store.

Le panneau contient l’activation, l’URL, l’ajout/indexation, les sources sélectionnables et une progression relue chaque seconde depuis le backend avec `st.fragment`. L’indexation ne bloque pas l’interface pendant tout le parcours du SharePoint.

Les champs, identifiants de widgets et texte de l’URL en cours de saisie restent des états d’interface. Le profil, le catalogue des sources et les travaux ne sont pas stockés dans un nouvel état frontend.

## 7. Périmètre de recherche — ajout court dans le gestionnaire MCP existant

L’agent transmet `document_ids` à `search_documents` uniquement lorsqu’une source explicite est sélectionnée. Le gestionnaire doit accepter ce paramètre optionnel ; sans cela, l’outil rejettera l’appel et la demande indiquera une erreur, sans recherche globale silencieuse.

Ajouter au paramétrage de l’outil et à sa signature actuelle :

```python
document_ids: list[str] | None = None
```

Puis importer :

```python
from app.source_scope import restrict_document_catalog
```

Après obtention du catalogue des documents autorisés, **avant recherche vectorielle/BM25/reranking**, filtrer la variable contenant ce catalogue :

```python
documents = restrict_document_catalog(documents, document_ids)
```

Le nom `documents` désigne la variable du gestionnaire existant : conserver son nom réel. Le moteur doit utiliser ce catalogue filtré pour toute la recherche. Si le moteur prend un filtre d’identifiants plutôt qu’un catalogue, transmettre l’intersection obtenue via cette liste à son filtre existant. Ne pas appliquer seulement un filtre aux passages après le reranking.

`None` conserve le périmètre autorisé existant. `[]` signifie aucun document, jamais tous les documents. L’agent vérifie également que les résultats appartiennent au périmètre transmis. Les contrôles d’accès courants restent nécessaires ; le manifeste d’indexation n’est pas une autorisation permanente.

Le périmètre transite explicitement vers MCP : les sous-processus n’ont pas besoin de lire le registre mémoire du processus Streamlit.

## 8. Cache du profil et étapes du chat, repris du kit précédent

Retirer le chargement complet de `user_data` dans `st.session_state` s’il est encore présent. Le chargeur du backend est :

```python
from app.context_cache import get_context, invalidate_context
from app.routing import warm_router
```

Dans `chat_view()`, après création de `Access`, charger le profil via :

```python
get_context(client, uid, lambda: access.user_context(uid))
```

L’agent réutilise ce cache. Le mode invité conserve `profile_enabled=False` et ne charge pas le profil API. Amorcer facultativement le routeur avec `asyncio.run(warm_router(client))` au chargement, comme précédemment.

Remplacer le spinner entourant `ask()` par :

```python
with st.status('Traitement de la demande', expanded=True) as status_box:
    def progress(label):
        status_box.update(label=label)
        status_box.write(label)
    result = asyncio.run(ask(
        s, store, client, uid, st.session_state.cid, question,
        profile_enabled=not st.session_state.get('is_guest', False),
        on_progress=progress))
    status_box.update(label='Traitement terminé', state='complete', expanded=False)
```

Conserver la gestion d’exception et le `st.rerun()` déjà présents. Dans la boucle des messages :

```python
saved = run.get('result') or {}
if saved.get('answer_scope') == 'general':
    st.caption('Connaissances générales du modèle — sans validation documentaire.')
if saved.get('answer_status') == 'partial':
    st.caption('Réponse partielle : certains passages n’ont pas été validés.')
if saved.get('verification'):
    with st.expander('Détail de la validation'):
        show_review(saved['verification'])
```

À la déconnexion ou à l’effacement des conversations, invalider le profil et la sélection documentaire backend :

```python
from app.skills import clear_skills
invalidate_context(client, uid)
clear_skills(client, uid)
```

## 9. Stockage et limites explicites du premier périmètre

L’état des skills et travaux est temporaire, dans le processus backend principal. Il survit aux reruns de la page, pas au redémarrage du serveur. Les documents indexés restent dans le Store et les index existants : aucun second stockage documentaire n’est créé.

Le registre des conversations est borné et les entrées inactives expirent après huit heures. Deux workers exécutent au maximum seize travaux actifs/en attente ; les travaux terminés conservés sont bornés. Deux validations de la même URL pendant le même travail réutilisent ce travail.

Le contrat proposé plus tôt avec un curseur durable et une reprise après redémarrage n’est **pas** présenté comme implémenté ici. La reprise, les mises à jour et suppressions de documents suivent les capacités de l’indexeur existant. Après redémarrage, les sélections de sources doivent être rétablies. Un déploiement avec plusieurs processus frontend nécessite un registre backend partagé ; ce kit vise le POC Streamlit à processus principal unique.

## 10. Vérification et MLflow

Le vérificateur conserve les preuves documentaires exactes et les preuves API typées. Douze blocs supportés sur treize restent restituables. L’erreur du juge ne donne pas de réponse générale de substitution. Une réponse générale porte `answer_scope='general'` et `verification.status='not_applicable'`, y compris lors d’une vérification différée.

La trace de chat expose `route`, `active_skills`, `retrieval_status`, `answer_scope`, `fallback_reason`, les identifiants opaques des sources et leur révision. La décision sémantique initiale et le parcours effectivement exécuté restent distincts dans `routing`.

Chaque indexation reçoit une trace séparée, rattachée au `job_id` et à la source opaque. Les appels au `API.embed()` modifié exécutés dans ce travail sont observés par lot avec modèle, durée, taille du lot, compteurs disponibles et erreur éventuelle. Aucune URL ni libellé de progression métier n’est ajouté à ces nouvelles traces.

Les autres étapes internes de l’indexeur ne sont pas inventées comme des spans si elles ne sont pas instrumentées dans son code. Un échec d’export laisse l’indexation enregistrée et donne un avertissement UI. La configuration et l’identifiant de l’expérience doivent être les mêmes que ceux de l’export existant.

## 11. Validation

```bash
python -m unittest discover -s validation -p 'test_*.py' -v
```

Le rapport `validation/VALIDATION.json` distingue les tests effectivement exécutés et ceux indisponibles. Les tests de workflows utilisent des API, un Store et un objet MLflow synthétiques. Le routage réel Aurelio et les APIs internes ne sont pas présentés comme mesurés par ces tests.

L’installation PyPI et l’accès GitHub du paquet ont été bloqués dans l’environnement de préparation de cette version. Les tests natifs Aurelio sont conservés pour l’environnement disposant de `semantic-router`; aucune implémentation maison du moteur n’a été substituée dans la livraison.

## 12. Sources primaires

Pondération documentaire indicative, sans signification statistique :

| Source | Part | Appui |
|---|---:|---|
| [Aurelio : routeurs](https://docs.aurelio.ai/docs/semantic-router/v1/user-guide/components/routers) | 20 % | IndexedRouter et contrat d’encodeur |
| [Aurelio : calibration](https://docs.aurelio.ai/docs/semantic-router/v1/user-guide/features/calibration) | 15 % | Jeux distincts et abstention |
| [Streamlit : popover](https://docs.streamlit.io/develop/api-reference/layout/st.popover) | 15 % | Panneau du skill |
| [Streamlit : fragment](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment) | 15 % | Progression sans refaire toute la page |
| [MLflow : traçage manuel](https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing/) | 25 % | Traces, attributs et étapes |
| [Microsoft : fichiers et dossiers](https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-folders-and-files-with-rest) | 10 % | Périmètre du connecteur existant, non réimplémenté |

Les choix du registre temporaire et des adaptateurs sont des décisions d’implémentation pour ce POC, pas des fonctionnalités natives attribuées aux frameworks.
