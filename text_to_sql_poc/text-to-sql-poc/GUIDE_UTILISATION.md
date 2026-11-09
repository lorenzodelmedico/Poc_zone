# Guide séquentiel d'installation et d'utilisation

## Résultat attendu

Depuis une page locale, saisir uniquement une question. Le backend récupère via MCP le schéma et les descriptions des graphiques. Un seul appel au LLM interne sélectionne une fiche et produit le SQL ; le backend contrôle le choix et la requête, obtient le jeton BDD, interroge PostgreSQL et retourne le JSON affiché en tableau et graphique. Le type de graphique choisi et sa justification sont visibles dans le résultat.

Toutes les valeurs sont fictives ou génériques. Aucun secret, nom interne ou certificat n'est nécessaire dans une conversation externe. Les remplacements s'effectuent exclusivement dans l'environnement local.

**Ordre de travail : étapes 1 à 14.** Chaque étape précise les fichiers concernés, le contenu attendu et le contrôle permettant de poursuivre.

Pour mettre à jour une installation précédente, remplacer les fichiers de code et de documentation par ceux de cette archive complète, en ajoutant notamment `config/chart_catalog.json`, `app/charts.py` et `frontend/chart-options.js`. Le ZIP ne contient ni `.env` ni `config/metadata.local.json` : conserver les fichiers locaux déjà personnalisés et le fichier ECharts installé. Aucun patch précédent n'est nécessaire. Redémarrer le backend puis recharger la page pour charger le nouveau JavaScript. Si le projet change de dossier, recréer le `.venv` plutôt que copier un environnement virtuel vers un autre chemin.

## 1. Extraire le ZIP et ouvrir la racine du projet

Extraire `text_to_sql_poc.zip`. Ouvrir un terminal dans le dossier `text-to-sql-poc`, celui qui contient `run.py` et `requirements.txt`.

Les commandes suivantes sont prévues pour **Windows avec Git Bash**, sauf mention explicite. Tous les chemins relatifs partent de cette racine. Aucun lancement depuis `app/` ou `frontend/`.

Contrôle :

```bash
pwd
ls run.py requirements.txt
```

Résultat attendu : les deux fichiers sont présents. Le chemin exact du dossier peut être quelconque et peut contenir des espaces.

## 2. Préparer Python et installer les dépendances

Prérequis : Python **3.11 ou 3.12**, accès à des paquets approuvés et droits de création d'un environnement virtuel local. Pas de Docker, WSL, npm ou droits administrateur requis.

Vérifier la version :

```bash
python --version
```

Créer l'environnement puis l'activer dans Git Bash sous Windows :

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

Si la commande `python` n'expose pas la bonne version mais que le lanceur Windows existe, utiliser `py -3.12 -m venv .venv` pour la création, puis reprendre l'activation ci-dessus.

Sous Linux, seule l'activation change : `source .venv/bin/activate`.

**Alternative PowerShell sans activation** :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dans ce cas, remplacer ensuite chaque commande `python ...` du guide par `.\.venv\Scripts\python.exe ...`.

Si l'installation passe par un miroir interne, appliquer la configuration `pip` approuvée. Si les paquets sont disponibles en fichiers wheel dans un dossier local :

```bash
python -m pip install --no-index --find-links /chemin/vers/wheelhouse -r requirements.txt
```

Le dossier doit contenir **toutes** les dépendances transitives, préparées pour la version de Python et l'OS utilisés. Des wheels Linux ne conviennent pas à Windows.

Contrôle :

```bash
python -c "import fastapi, uvicorn, mcp, psycopg, sqlglot, dotenv; print('Dépendances OK')"
```

Une erreur `ModuleNotFoundError` signifie que l'installation est incomplète ou que le terminal utilise un autre Python. Ne pas poursuivre tant que ce contrôle échoue.

## 3. Créer les fichiers locaux à personnaliser

Dans Git Bash :

```bash
cp .env.example .env
cp config/metadata.example.json config/metadata.local.json
```

Dans PowerShell :

```powershell
Copy-Item .env.example .env
Copy-Item config/metadata.example.json config/metadata.local.json
```

Ces copies ne sont à effectuer qu'à la première installation : les répéter écraserait les valeurs déjà renseignées.

| Fichier | Usage | À versionner ? |
|---|---|---|
| `.env.example` | Modèle générique de configuration. | Oui, avec ses placeholders. |
| `.env` | Paramètres réels et secrets locaux. | Non. |
| `config/metadata.example.json` | Exemple synthétique fourni. | Oui. |
| `config/metadata.local.json` | Schéma et règles réels de la vue. | Non, dans le périmètre de ce dépôt générique. |

Contrôle : les deux copies existent et restent enregistrées en **UTF-8**. Les modifications suivantes concernent `.env` et `metadata.local.json`.

## 4. Installer le fichier ECharts local

L'application sert ECharts depuis son propre dossier ; aucun CDN n'est appelé par le navigateur. Le ZIP ne contient pas ce fichier tiers.

Choisir **une** des deux méthodes suivantes.

**Méthode hors Internet :** obtenir par le circuit autorisé l'archive npm originale `echarts-5.6.0.tgz`, puis :

```bash
python scripts/install_echarts.py --archive "/chemin/vers/echarts-5.6.0.tgz"
```

**Méthode avec accès Internet autorisé :**

```bash
python scripts/install_echarts.py --download
```

Le téléchargement explicite utilise le registre npm public en HTTPS. Si un bundle CA est nécessaire, ajouter `--ca-bundle "C:/chemin/ca-bundle.pem"`. Ne pas désactiver la validation TLS.

L'installateur copie uniquement `echarts.min.js`, LICENSE et NOTICE. Aucun npm ni build frontend n'est requis.

Contrôle : le fichier `frontend/vendor/echarts.min.js` existe. En son absence, le POC peut afficher des tableaux, mais pas de graphique.

## 5. Renseigner la vue et ses colonnes

Fichier : `config/metadata.local.json`.

Les identifiants sont des **noms bruts**, sans guillemets SQL ni préfixe ajouté. Exemple : `analytics`, et non `"analytics"` ; le schéma et la vue restent deux champs distincts.

| Champ JSON | Type et valeur attendue | Exemple générique |
|---|---|---|
| `view.schema` | Nom exact du schéma PostgreSQL. | `analytics` |
| `view.name` | Nom exact de la vue, sans le schéma. | `v_metric` |
| `view.description` | Description métier courte, non ambiguë. | Vue d'un indicateur validé. |
| `view.grain` | Définition précise d'une ligne. | Une ligne par participation validée. |
| `columns[].name` | Nom exact d'une colonne exposée par la vue. | `category` |
| `columns[].type` | Type PostgreSQL descriptif de la colonne. | `text`, `date`, `numeric` |
| `columns[].description` | Sens métier, unité et date de référence si pertinent. | Nombre d'heures délivrées. |
| `columns[].role` | `dimension` pour regroupement/filtre, ou `measure` pour mesure. | `dimension` |
| `columns[].allowed_aggregations` | Liste de fonctions explicitement admises : `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`. | `["SUM"]` |
| `allow_count_rows` | Booléen autorisant ou non `COUNT(*)`. | `false` |
| `business_rules` | Liste de phrases définissant les règles métier applicables. | Période par défaut, filtres et populations incluses. |

Remplacer ou retirer les trois colonnes de l'exemple pour qu'elles correspondent à la vue cible. Ajouter les colonnes nécessaires comme nouveaux objets dans `columns`. Les rôles et agrégations admis doivent correspondre à la définition métier, pas uniquement au type SQL.

Les types figurant dans le fichier servent de contexte au modèle ; le POC ne découvre pas automatiquement le schéma de la base et ne vérifie pas cette correspondance au démarrage.

Pour une première version, conserver des noms d'identifiants composés de lettres ASCII, chiffres et `_`, commençant par une lettre ou `_`. La casse est conservée : le modèle reçoit la consigne d'utiliser des identifiants SQL entre guillemets doubles.

À vérifier dans les règles métier :

- ce que représente une ligne ;
- l'additivité de la mesure et les éventuels doublons ;
- la date de référence pour une période ;
- les populations déjà incluses ou exclues par la vue ;
- le comportement attendu en l'absence de période ;
- les demandes qui doivent conduire à une clarification.

Les règles en texte guident le modèle. Elles ne deviennent pas automatiquement des contrôles programmatiques ; les résultats de référence de l'étape 12 servent à vérifier leur respect.

Contrôle du JSON dans le terminal :

```bash
python -m json.tool config/metadata.local.json
```

Cette commande affiche les métadonnées **localement**. Ne pas recopier une sortie contenant des informations internes dans un service externe.

### Catalogue des graphiques déjà fourni

Fichier : `config/chart_catalog.json`, version `1.1`. Il est livré prêt à l'emploi et ne contient aucun placeholder interne.

| Élément d'une fiche | Rôle |
|---|---|
| `id` | Identifiant stable retourné par le LLM : `bar` ou `line`. |
| `label`, `description` | Nom et description française basés sur la documentation officielle ECharts. |
| `use_when`, `avoid_when` | Cas d'usage et exclusions pris en compte lors de la sélection. |
| `examples` | Formulations de demandes illustrant les intentions. |
| `data_requirements` | Dimension et mesure attendues dans les résultats SQL. |
| `echarts` | Type de série et types d'axes associés à un modèle fixe du frontend. |
| `sources` | URLs des pages officielles utilisées ; aucune lecture Internet à l'exécution. |

Le MCP retourne ces fiches avec `get_chart_catalog`. Elles sont réellement ajoutées au contexte du LLM, séparément des métadonnées de la vue. Le rapprochement entre la question et la fiche est effectué par le LLM existant ; aucun modèle d'embeddings ni framework de routage supplémentaire n'est requis.

La fiche `bar` correspond à une comparaison de groupes ; `line` à une évolution temporelle dans ce POC. ECharts accepte aussi des courbes sur d'autres axes : la restriction temporelle est une règle de ce projet, pas une limite générale d'ECharts.

Les descriptions peuvent être affinées localement ; l'ajout d'un nouvel identifiant nécessite d'implémenter son contrôle et son modèle de rendu. Ajouter une fiche arbitraire ne suffit pas à rendre son graphique exécutable. Les paramètres `echarts` des deux modèles sont contrôlés côté serveur.

## 6. Renseigner la connexion au LLM

Fichier : `.env`.

| Variable | Valeur attendue | Exemple de format |
|---|---|---|
| `METADATA_PATH` | Chemin relatif depuis la racine ou chemin absolu du JSON local. | `config/metadata.local.json` |
| `LLM_CHAT_URL` | URL **complète** de l'appel compatible chat/completions. | `https://<LLM_GATEWAY>/v1/chat/completions` |
| `LLM_MODEL` | Identifiant exact accepté par le relais interne. | Alias réellement déclaré pour Gemma ou Nemotron disponible. |
| `LLM_API_KEY` | Clé ou jeton Bearer statique du relais si nécessaire ; vide sinon. | Valeur réelle locale, sans ajouter le mot `Bearer`. |
| `LLM_TIMEOUT` | Délai HTTP maximal en secondes. | `120` |
| `LLM_MAX_TOKENS` | Nombre maximal de tokens de sortie demandé au modèle. | `1800` |

Ne pas doubler `/v1/chat/completions` : l'application utilise exactement l'URL fournie. L'identifiant du modèle est celui du service, pas nécessairement son nom public.

Le client LLM transmet `model`, `messages`, `temperature`, `max_tokens` et `stream=false`, puis lit `choices[0].message.content`. Si le relais utilise un autre contrat, l'adaptation se limite à `app/llm.py`. Aucun mode JSON propriétaire ni tool calling du modèle n'est requis. La même réponse JSON doit contenir le SQL et la sélection du graphique ; une ancienne réponse ne contenant que le SQL est désormais refusée.

Dans `.env`, conserver une affectation `NOM=valeur` par ligne. Pour un mot de passe contenant des espaces ou un caractère `#`, employer des guillemets adaptés, par exemple `AUTH_PASSWORD='valeur_locale'`. Ne jamais ajouter le préfixe `Bearer` à la valeur d'un jeton si le code le construit déjà.

L'authentification du LLM et celle de la base sont distinctes. Si le relais LLM renouvelle lui-même ses jetons, laisser ce fonctionnement au relais. Une authentification dynamique spécifique au LLM n'est pas fournie dans ce POC.

Contrôle : les placeholders `<...>` des champs LLM obligatoires ont été remplacés ; aucune clé réelle n'est ajoutée à `.env.example`.

## 7. Renseigner le service de récupération du jeton BDD

Fichier : `.env`. Le contrat fourni est un appel HTTP `POST` avec corps JSON ou formulaire. Il est configurable sans modifier le code pour les variantes ci-dessous.

| Variable | Contenu à fournir |
|---|---|
| `AUTH_URL` | URL complète du service de jeton, sans valeur de secret dans l'URL. |
| `AUTH_ID` | Identifiant de service ou de compte utilisé pour acquérir le jeton. |
| `AUTH_PASSWORD` | Mot de passe correspondant. |
| `AUTH_BODY_FORMAT` | `json` pour un objet JSON, ou `form` pour un formulaire encodé. |
| `AUTH_ID_FIELD` | Nom du champ attendu par le service pour l'identifiant : par exemple `id` ou `username`. |
| `AUTH_PASSWORD_FIELD` | Nom du champ attendu pour le mot de passe : par exemple `password`. |
| `AUTH_EXTRA_JSON` | Objet JSON de champs supplémentaires connus, ou `{}`. |
| `AUTH_TOKEN_FIELD` | Chemin du jeton dans la réponse JSON : par exemple `access_token` ou `data.token`. |
| `AUTH_EXPIRES_FIELD` | Chemin d'une **durée en secondes**, par exemple `expires_in` ou `data.ttl`. Vide si indisponible. |

Exemple fictif de contrat :

```json
{
  "username": "<SERVICE_LOGIN>",
  "password": "<SERVICE_PASSWORD>",
  "scope": "database.read"
}
```

Il correspond aux réglages :

```dotenv
AUTH_BODY_FORMAT=json
AUTH_ID_FIELD=username
AUTH_PASSWORD_FIELD=password
AUTH_EXTRA_JSON={"scope":"database.read"}
```

Pour une réponse fictive `{"data":{"token":"<JETON>","ttl":3600}}` :

```dotenv
AUTH_TOKEN_FIELD=data.token
AUTH_EXPIRES_FIELD=data.ttl
```

Une date absolue `expires_at` n'est **pas** une durée `expires_in`. Si le service ne retourne qu'une date absolue, laisser `AUTH_EXPIRES_FIELD` vide ou adapter `app/auth.py` pour ce contrat.

Sans durée exploitable, le POC redemande un jeton lors de la connexion suivante. Avec une durée connue, il le conserve en mémoire avec une petite marge avant expiration. Aucune sauvegarde du jeton sur disque.

Si le service utilise Basic Auth, des en-têtes spéciaux, une authentification interactive ou un corps imbriqué plus complexe, adapter la requête dans `app/auth.py` et éventuellement `app/http_client.py`. Ces contrats ne peuvent pas être déduits depuis les seules notions d'identifiant et de mot de passe.

Contrôle : les noms de champs correspondent au contrat réel. Aucun appel live n'est réalisé par le simple remplissage de `.env`.

## 8. Renseigner PostgreSQL et confirmer l'utilisation du jeton

Fichier : `.env`.

| Variable | Type attendu | Exemple de format |
|---|---|---|
| `PGHOST` | Hôte de connexion, sans protocole ni port. | `<POSTGRES_HOST>` |
| `PGPORT` | Port entier. | `5432` |
| `PGDATABASE` | Nom de base. | `<POSTGRES_DATABASE>` |
| `PGUSER` | Rôle PostgreSQL autorisé à lire la vue. | `<POSTGRES_READONLY_ROLE>` |
| `DB_TOKEN_MODE` | `password` ou `custom`. | `password` |
| `PGSSLMODE` | `verify-full` par défaut ; `verify-ca` ou `require` seulement si le contrat l'exige. | `verify-full` |
| `PGSSLROOTCERT` | Chemin local du certificat CA PEM PostgreSQL ; vide si le magasin utilisé suffit. | `C:/certificates/postgres-ca.pem` |
| `DB_CONNECT_TIMEOUT` | Délai de connexion en secondes. | `10` |
| `MAX_ROWS` | Nombre maximal de groupes retournés, entre 1 et 5000. | `500` |
| `STATEMENT_TIMEOUT_MS` | Délai maximal d'une instruction, entre 100 et 60000 ms. | `10000` |

**Cas fourni :** le jeton est accepté comme mot de passe par PostgreSQL ou sa passerelle. Conserver `DB_TOKEN_MODE=password`. Le connecteur appelle Psycopg avec `password=<jeton>`.

**Autre cas :** le jeton doit être utilisé avec un mécanisme spécifique. Choisir `custom`, puis implémenter `connect_with_custom_token(settings, token)` dans `app/database.py`. Le point d'adaptation lève volontairement `TOKEN_ADAPTER_REQUIRED` tant qu'il n'est pas renseigné.

**API HTTP intermédiaire :** un jeton Bearer envoyé à une API ne s'utilise pas automatiquement comme mot de passe PostgreSQL. Dans ce cas, adapter `execute_query` dans `app/database.py` au contrat de l'API et conserver la validation SQL en amont. Le connecteur d'API n'est pas fourni, car ses paramètres ne sont pas connus.

Les modes `verify-ca` et `require` n'offrent pas exactement les mêmes vérifications que `verify-full`. Le mode le plus strict compatible avec l'environnement reste préférable ; ne pas ajouter de désactivation TLS pour contourner une erreur.

Les permissions du rôle doivent être définies dans la base : accès au schéma et lecture de la vue, sans privilèges inutiles ni élévation. Le code ne crée pas de rôle et n'exécute pas de `GRANT` au démarrage. Une transaction en lecture seule complète ces permissions ; elle ne les remplace pas. Références techniques : [S2 et S3](SOURCES.md).

Contrôle : confirmer localement le mécanisme du jeton et l'accès à la vue avec le rôle prévu. Le simple succès de l'appel au service de jeton ne prouve pas que la base l'accepte.

## 9. Renseigner les certificats HTTP si nécessaire

Fichier : `.env`.

`HTTP_CA_BUNDLE` concerne les appels au LLM et au service de jeton. `PGSSLROOTCERT` concerne PostgreSQL. Ce sont deux réglages indépendants.

Exemple de format sous Windows :

```dotenv
HTTP_CA_BUNDLE="C:/certificates/http-ca-bundle.pem"
PGSSLROOTCERT="C:/certificates/postgres-ca.pem"
```

Employer des chemins absolus avec `/`, ou laisser le champ vide si les certificats sont déjà reconnus. Les fichiers doivent être des bundles CA PEM approuvés. Aucune copie de certificat dans le dépôt n'est nécessaire.

Contrôle : les fichiers existent et le processus Python peut les lire. Ne pas remplacer la vérification TLS par `verify=False`.

## 10. Vérifier la configuration locale

Depuis la racine :

```bash
python scripts/check_config.py
```

Résultat attendu : `Configuration locale : OK`. Ce contrôle vérifie les champs obligatoires et la structure des métadonnées ; il **ne teste pas** les services, les certificats, les droits ou la correspondance du schéma réel.

Si `CONFIG_INCOMPLETE` apparaît, la sortie liste les **noms** des variables à compléter, sans afficher leurs valeurs.

## 11. Exécuter les tests puis démarrer

```bash
python -m unittest discover -s tests -v
```

Une installation complète doit exécuter les tests de base, SQL, MCP et API. Les tests API simulent le LLM et la base mais utilisent le véritable client/serveur MCP et le validateur SQL. Aucune connexion à une base réelle ni à un LLM réel n'est déclenchée par la suite.

Les tests des modèles de graphiques et du parcours JavaScript peuvent être lancés avec Node.js 18 ou ultérieur, si cet outil est disponible :

```bash
node --test tests/frontend.test.cjs
```

Node.js est uniquement nécessaire pour ces tests frontend ; le lancement de l'application reste entièrement basé sur Python. Ces tests exécutent le JavaScript dans un DOM simulé et contrôlent les options produites ; ils ne constituent pas une inspection visuelle dans un navigateur réel.

Si la sortie indique des tests `skipped`, les dépendances correspondantes manquent : ne pas interpréter `OK (skipped=...)` comme une validation complète. L'état des vérifications réalisées lors de la livraison est détaillé dans [VALIDATION.md](VALIDATION.md).

Démarrer :

```bash
python run.py
```

Le backend lance automatiquement le MCP local dans le même environnement Python. Aucun second terminal n'est nécessaire. L'interface est servie depuis le même processus, sans serveur frontend séparé.

Ouvrir <http://127.0.0.1:8000>.

Contrôles :

1. <http://127.0.0.1:8000/health> retourne `status: ok`. `echarts_ready` doit valoir `true` pour les graphiques. Ce point vérifie uniquement le processus et la présence du fichier JS.
2. <http://127.0.0.1:8000/api/catalog> retourne la description de la vue et les graphiques. Cela vérifie l'appel réel au MCP, mais pas la connexion BDD.
3. La page affiche la description de la vue et le bouton « Analyser » devient actif.

Arrêt : `Ctrl+C`. Après modification de `.env`, arrêter puis relancer ; les réglages sont chargés au démarrage. Les métadonnées sont relues à chaque demande par le MCP.

## 12. Effectuer les premiers essais fonctionnels

### 12.1. Préparer une référence

Option A : utiliser la vue cible et une requête de référence validée localement.

Option B : sur une **base de test autorisée uniquement**, faire créer la vue fictive décrite dans `examples/synthetic_view.sql`. Ce fichier n'est jamais exécuté automatiquement. Il nécessite un compte de préparation disposant du droit de créer une vue ; le rôle du POC reste un rôle de lecture.

Pour cette option B, conserver les noms de `config/metadata.example.json` dans le fichier local. Les paramètres de connexion et le service de jeton restent à configurer ; aucune authentification PostgreSQL fictive n'est fournie.

### 12.2. Tester les barres

Question de l'exemple synthétique :

> Total des heures par catégorie sur l'année 2025.

Cliquer sur **Analyser**. Aucun type de graphique n'est à sélectionner.

Résultat attendu sur la vue synthétique : `A = 4`, `B = 5`. Les noms SQL de sortie sont `x` et `y`. La présentation automatique attendue est « Barres de comparaison », avec une justification. La requête exécutée apparaît dans le panneau prévu et peut être comparée à `examples/reference_queries.sql`.

### 12.3. Tester la courbe

Question :

> Comment les heures ont-elles évolué chaque mois au cours de l'année 2025 ?

Cliquer sur **Analyser**. La fiche attendue est automatiquement `line`, car la demande porte sur une évolution mensuelle.

Résultat attendu : janvier `5.5`, février `3.5`. Le modèle doit produire une date ou un horodatage en `x`, typiquement avec `DATE_TRUNC('month', ...)`. La réponse utilise des dates ISO normalisées en UTC, le backend les ordonne chronologiquement et le client remplit un modèle ECharts à axe `time`.

Une catégorie textuelle arbitraire ne convient pas à ce modèle de courbe. Le modèle doit clarifier la demande ; si une sélection incompatible est malgré tout retournée, le backend la bloque avec `CHART_INCOMPATIBLE`, sans proposer de menu manuel.

### 12.4. Tester les limites

| Demande | Comportement attendu |
|---|---|
| « Total récent » sans règle définissant récent. | Clarification sans exécution SQL. |
| Filtrer selon une colonne absente. | Demande impossible ou clarification ; aucun nom inventé ne doit être exécuté. |
| Modifier ou supprimer des données. | Refus du modèle ou blocage par le validateur. |
| Lire une autre table. | Refus ou blocage avant connexion métier. |
| Période sans donnée. | Message « Aucun résultat » ; pas d'ancien graphique conservé. |
| Trop de groupes. | `RESULT_LIMIT`, sans graphique partiel. |
| Demande d'un graphique absent du catalogue, par exemple un nuage de points. | Demande hors périmètre ; aucun type de graphique inventé. |
| « Une courbe des heures par catégorie » sans temps. | Clarification sur la dimension temporelle ; si le modèle renvoie néanmoins une courbe incompatible, blocage avant exécution métier. |

Le comportement de clarification dépend de la qualité du modèle. Les tests déterministes vérifient le blocage du SQL hors périmètre, pas une garantie absolue de bonne interprétation.

Pour l'évaluation métier, préparer ensuite 20 à 30 questions représentatives avec résultat de référence et relever séparément : exécution correcte, résultat correct, bonne clarification et temps de réponse.

### 12.5. Vérifier le contrat JSON automatique

Le client envoie seulement :

```json
{"question": "Comment les heures évoluent-elles chaque mois en 2025 ?"}
```

L'ancien champ client `chart_type` est supprimé et refusé avec une erreur de validation HTTP 422. La réponse LLM attendue est structurée ainsi :

```json
{
  "status": "ok",
  "sql": "SELECT ... AS x, SUM(...) AS y FROM ... GROUP BY ... ORDER BY x",
  "chart": {
    "id": "line",
    "reason": "La demande porte sur une évolution mensuelle.",
    "x_label": "Mois",
    "y_label": "Heures délivrées"
  },
  "assumptions": [],
  "clarification_question": null
}
```

Le backend ajoute à la présentation validée le modèle et les champs fixes, puis associe les lignes réellement obtenues. Aucune option ECharts libre n'est acceptée depuis la réponse du modèle. Une clarification ou un refus impose `sql=null` et `chart=null` ; aucune requête métier n'est alors exécutée.

## 13. Comprendre les erreurs et les traces

| Code ou symptôme | Contrôle suivant |
|---|---|
| `CONFIG_INCOMPLETE` | Compléter les variables listées dans `.env`. |
| `METADATA_INVALID` ou `MCP_TOOL` | Vérifier le chemin, l'UTF-8 et les champs du JSON local. |
| `UPSTREAM_HTTP` | Vérifier le contrat du service de jeton ou de l'API LLM ; le code HTTP est indiqué sans réponse brute. |
| `UPSTREAM_CONNECTION` | Vérifier DNS, proxy, accès, délai et bundle CA HTTP. |
| `AUTH_TOKEN_MISSING` | Corriger le chemin `AUTH_TOKEN_FIELD` en fonction du JSON réel. |
| `TOKEN_ADAPTER_REQUIRED` | Implémenter le mécanisme `custom`, ou utiliser `password` seulement si ce mode est effectivement accepté. |
| `DB_CONNECTION` | Vérifier hôte/port, TLS, rôle et acceptation du jeton. Un HTTP 200 du service de jeton ne suffit pas. |
| `LLM_FORMAT` | Vérifier `choices[0].message.content`, la limite de sortie et le respect du JSON demandé. |
| `CHART_CATALOG_INVALID` | Vérifier le catalogue fourni et conserver les deux modèles exécutables `bar` et `line`. |
| `CHART_UNKNOWN` ou `LLM_CHART_FORMAT` | Le modèle doit retourner une sélection valide parmi les fiches MCP, pas un nouveau graphique ni des options libres. |
| `SQL_REJECTED` | Lire la raison ; vérifier la requête proposée et les colonnes/agrégations configurées. Ne pas supprimer le contrôle pour contourner une sortie erronée. |
| `DB_QUERY` | Vérifier noms, types, règles et permissions. Si nécessaire, inspecter le SQL localement avec un point d'arrêt dans `app/api.py` ; il n'est pas enregistré dans les logs. |
| `DB_TIMEOUT` | Restreindre la demande ; examiner localement la vue avant d'augmenter le délai. |
| `RESULT_LIMIT` | Réduire période, filtres ou nombre de catégories. |
| `CHART_INCOMPATIBLE` | Préciser la dimension de l'analyse et vérifier les types du schéma ; le système choisit automatiquement la présentation, sans sélecteur manuel. |
| Graphique absent, tableau présent. | Installer ECharts puis recharger la page. |
| Le backend ne démarre pas. | Vérifier l'environnement Python, les imports et la disponibilité du port 8000. |

Les logs du traitement applicatif contiennent uniquement un identifiant de requête, un statut et une durée. Le SQL et les résultats sont affichés dans le navigateur local mais pas journalisés par l'application. Aucun historique conversationnel, checkpoint ou export de données n'est créé.

Les services amont et PostgreSQL peuvent avoir leurs propres politiques de journalisation, indépendantes du POC.

## 14. Préparer le dépôt GitHub

Le ZIP contient les exemples génériques et le code source. Les fichiers réels de configuration et les secrets doivent rester locaux.

Après un essai concluant, figer si nécessaire les versions installées dans l'environnement validé :

```bash
python -m pip freeze > requirements.lock.txt
```

Ce fichier décrit cet environnement particulier ; il n'a pas été produit ou validé par avance pour tous les OS. `requirements.txt` reste le fichier d'installation initiale.

Pour un dépôt Git neuf, depuis la racine :

```bash
git init
git add .
git status --short
git diff --cached --stat
```

Vérifier que `.env`, `config/metadata.local.json`, l'environnement virtuel, les certificats et les logs sont absents des fichiers ajoutés. `.env.example` et `metadata.example.json` doivent conserver leurs valeurs génériques. Ne pas placer d'URL interne ni de nom réel dans un fichier versionné pour ce dépôt générique.

Après cette vérification locale :

```bash
git commit -m "Initial minimal Text-to-SQL MCP POC"
git branch -M main
git remote add origin <URL_DU_DEPOT_GITHUB>
git push -u origin main
```

`<URL_DU_DEPOT_GITHUB>` est à remplacer par l'URL du dépôt vide créé dans l'espace GitHub autorisé. La commande `remote add` ne s'applique que si aucun remote `origin` n'existe déjà. Pour un dépôt existant, reprendre son workflow habituel.

L'archive n'est pas publiée automatiquement. Les identifiants réels et métadonnées internes restent exclus du dépôt. Le workflow GitHub Actions fourni installe les dépendances et exécute les tests avec des données fictives ; il n'utilise aucun secret ni service interne.

## Périmètre à conserver pour la première fonctionnalité

Une vue, une dimension, une mesure agrégée, deux modèles de graphiques. Le MCP expose le schéma et les fiches ECharts. Le backend transmet ce contexte au LLM, qui choisit une fiche et écrit le SQL en un seul appel. Le backend contrôle et exécute ; le client remplit le modèle fixe. Aucun sélecteur manuel, aucune génération de JavaScript et aucun renvoi des résultats au LLM.

La sélection du bon graphique est une proposition du modèle, à mesurer sur des questions de référence. Une forme de résultat compatible ne prouve pas à elle seule la bonne interprétation métier. Les périodes absentes ne sont ni ajoutées ni remplies avec des zéros.

Les résultats numériques sont convertis en nombres JSON adaptés à ECharts. Une conversion `Decimal` vers un nombre flottant peut arrondir les très grandes valeurs ou les décimales de forte précision ; ce POC ne convient pas tel quel à une restitution comptable exigeant une précision décimale exacte.

Les sources techniques et leur rôle sont documentés dans [SOURCES.md](SOURCES.md). Les contrôles et limites de validation de la livraison sont documentés dans [VALIDATION.md](VALIDATION.md).
