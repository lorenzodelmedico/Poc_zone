# Rectificatif — génération du harness, séparation des profils et limites

Ce document corrige trois défauts des livraisons précédentes : la source de génération de harness.json n’avait pas été complétée, des consignes Confluence avaient été placées dans des outils génériques, et le choix du workflow de tests avait été présenté trop implicitement.

Il s’applique après les Compléments Confluence/Tests/Références déjà recopiés. Aucun besoin de recopier leurs fichiers complets. Les changements ci-dessous remplacent les consignes contradictoires de leurs sections A7 et D.

`<KIT>` désigne la racine du dépôt contenant continue_kit ; `<CIBLE>` le projet passé à --project. Les deux peuvent être identiques.

## 1 — Retirer le routage Confluence des outils génériques

### project_facts

Fichier : `<KIT>/continue_kit/workflow_mcp.py`, dans la docstring de project_facts.
**Supprimer** ces deux lignes, si elles ont été ajoutées :

```python
        Pour une opération sur une page Confluence, appeler directement confluence_pages ;
        ne pas inventorier le dépôt ni lire .env/config.yaml/harness pour rechercher ses accès.
```

Ne pas les remplacer par une autre exception liée à un service. project_facts décrit son inventaire du dépôt ; le profil spécialisé choisit le parcours du domaine.

### replace_document

Dans la docstring de replace_document, dans le même fichier, remplacer :

```python
        path est un chemin de FICHIER LOCAL relatif au projet. Pour une page Confluence,
        utiliser confluence_pages ; ne pas créer de fichier intermédiaire pour son remplacement.
```

par son contrat propre, sans référence à un service distant :

```python
        path est un chemin relatif vers un fichier texte existant du projet courant.
        Cet outil agit sur le système de fichiers local.
```

### Contrat de confluence_pages

Fichier : `<KIT>/continue_kit/confluence_tools.py`, docstring de confluence_pages.
Remplacer la ligne :

```python
        reste et capture sa version. Ne pas lire .env, config.yaml, harness ou project_facts pour cela.
```

par :

```python
        reste et capture sa version. Les paramètres d’accès sont gérés par le serveur.
```

Cette phrase décrit un fait du contrat : c’est le serveur qui prend en charge ses accès. Les consignes sur le raisonnement et le choix de parcours restent dans le profil.

## 2 — Source de génération des nouveaux harness.json

Le fichier `<CIBLE>/.continue/harness.json` est une configuration de projet, pas un modèle global. Tu avais raison : le modifier seul ne pouvait pas transmettre ces valeurs aux nouveaux projets.

Le générateur actuel configure.py appelle Workflow(project).initialize(). C’est donc initialize qui doit lire la source commune avant de créer ou compléter le fichier cible.

### 2A — Nouveau modèle de configuration

Créer `<KIT>/continue_kit/templates/harness.json` avec ce contenu complet :

```json
{
  "python": ".venv/Scripts/python.exe",
  "checks": {},
  "exclude": [],
  "read_repositories": {
    "ragdoc": "../ragdoc"
  }
}
```

Adapter ou retirer l’exemple ragdoc selon les références réellement souhaitées. Une table vide `{}` est valide.

Justification du nouveau fichier : il contient la configuration à générer et éditer dans le kit. Il sépare les valeurs communes du code Python et des copies propres à chaque projet. Il n’ajoute aucune dépendance et n’est pas un fichier de tests.

### 2B — Relier le modèle au générateur existant

Fichier : `<KIT>/continue_kit/workflow.py`.
Ajouter read_json à l’import existant depuis workspace. Dans la version livrée, remplacer :

```python
from .workspace import Workspace, WorkflowError, atomic_json, digest
```

par :

```python
from .workspace import Workspace, WorkflowError, atomic_json, digest, read_json
```

Si cet import comporte déjà d’autres noms dans ta version, les conserver et ajouter seulement read_json.

Dans la classe Workflow, remplacer uniquement la méthode initialize, depuis sa ligne def jusqu’à son return, par :

```python
    def initialize(self):
        profile = self.root / ".continue" / "harness.json"
        kit_root = Path(__file__).resolve().parent.parent
        template = kit_root / "continue_kit" / "templates" / "harness.json"
        defaults = {"python": ".venv/Scripts/python.exe", "checks": {}, "exclude": [],
                    "read_repositories": {}}
        if template.exists():
            supplied = read_json(template)
            if not isinstance(supplied, dict):
                raise WorkflowError("Le modèle harness.json doit contenir un objet JSON.")
            defaults.update(supplied)
        roots = defaults.get("read_repositories", {})
        if not isinstance(roots, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v.strip()
                                              for k, v in roots.items()):
            raise WorkflowError("Le modèle read_repositories doit associer des noms à des chemins.")
        defaults["read_repositories"] = {
            name: (Path(value).expanduser() if Path(value).expanduser().is_absolute()
                   else kit_root / Path(value).expanduser()).resolve().as_posix()
            for name, value in roots.items()
        }
        current = read_json(profile) if profile.exists() else {}
        if not isinstance(current, dict):
            raise WorkflowError("harness.json doit contenir un objet JSON.")
        merged = {**defaults, **current}
        if not profile.exists() or merged != current:
            atomic_json(profile, merged)
        for name in (".gitignore", ".continueignore"):
            path = self.root / name
            content = path.read_text(encoding="utf-8-sig") if path.exists() else ""
            if ".coding-harness/" not in content.splitlines():
                path.write_text(content.rstrip() + "\n.coding-harness/\n", encoding="utf-8")
        return {"status": "ready", "storage": ".coding-harness/tasks.sqlite3"}
```

### Comportement obtenu

- Nouveau projet : les champs du modèle sont utilisés pour créer .continue/harness.json.
- Projet existant : ajout des champs manquants, sans écraser les champs déjà présents.
- Une propriété read_repositories déjà présente dans un projet est sa surcharge locale, y compris si elle vaut `{}`. Les alias ne sont pas fusionnés automatiquement.
- Les chemins relatifs de read_repositories dans le MODELE sont résolus depuis la racine du KIT et écrits comme chemins absolus dans le fichier généré. Ils restent corrects si un projet cible se trouve plusieurs niveaux plus bas. Utiliser les alias dans read_reference.
- Les chemins relatifs que tu écris directement dans le harness d’un PROJET continuent à être résolus depuis ce projet.
- python reste relatif au projet cible : il ne devient pas le Python du kit.
- Changer le modèle ne réécrit pas silencieusement les projets existants ; leurs configurations gardent la priorité.

Après ces modifications, tes prochaines commandes configure utilisent automatiquement ce modèle. Aucun changement de configure.py n’est nécessaire : son appel initialize existe déjà.

Pour compléter un projet existant sans régénérer ses profils de modèles, lancer depuis le KIT, en adaptant le chemin cible :

```bash
".venv/Scripts/python.exe" -m continue_kit.workflow --project "$(cygpath -am /c/work/projet_cible)" init
```

Si read_repositories y existe déjà, il reste prioritaire. Pour faire hériter ce champ du modèle, retirer uniquement cette propriété du harness cible puis relancer init. Conserver les autres champs.

## 3 — Répartition des consignes

| Type de contenu | Emplacement approprié |
|---|---|
| Paramètres, formats d’entrée/sortie et effets d’un outil | Description/docstring de cet outil |
| Validation des arguments, versions, persistance et vérification après écriture | Implémentation du module concerné |
| Choix d’un parcours Confluence, validation conversationnelle, rédaction guidée | Ton profil spécialisé Confluence |
| Manière d’écrire et lancer les tests de diagnostic de l’agent | Règle transversale de développement |
| Valeurs communes à générer pour les projets | Modèle harness.json du kit |

Retirer de 01-coding.md les blocs exclusivement Confluence ajoutés par les livraisons précédentes et les conserver dans ton profil spécialisé, comme tu le fais déjà. Garder les règles générales sur les tests, le Python du projet et les dépendances. Effectuer la même séparation dans les modèles du kit pour les prochaines installations.

Je n’ai pas le chemin exact de ton profil spécialisé : ne pas créer un nom de fichier supposé. Si c’est un prompt installé depuis `<KIT>/continue_kit/templates/prompts/<nom>.md`, la copie cible est `<CIBLE>/.continue/prompts/<nom>.md`, et install_guidance copie les .md de ce dossier. Dans ce cas, modifier la source du kit et la copie active. Cette correspondance est conditionnelle au type de profil que tu utilises.

Bloc de méthode à placer dans le profil Confluence existant, en remplacement des instructions qui imposeraient toujours confluence_pages :

```markdown
## Choix du parcours Confluence

Choisir parmi les outils et actions Confluence réellement exposés celui dont le
contrat correspond à la demande : lecture, modification directe ou rédaction guidée.
Ne pas réduire le domaine à un outil unique ; tenir compte de leurs capacités actuelles.

Pour une opération documentaire, utiliser les accès pris en charge par ces outils.
Explorer le code ou la configuration du projet seulement si la demande concerne
leur implémentation ou leur diagnostic.

Présenter le changement à confirmer selon le parcours choisi. Si le contenu final
vient déjà intégralement de l’utilisateur, éviter de le réimprimer inutilement.
Respecter le résultat réel des sauvegardes et leurs critères de vérification.
```

## 4 — Tests : décision de l’agent, sans demande spéciale du user

L’outil run_project_test exécute déjà le fichier de test dans le venv du projet avec load_dotenv. Ce que le code ne fait pas : intercepter une commande de terminal native de Continue et la transformer automatiquement en appel à cet outil.

Le comportement demandé pour l’utilisateur repose donc sur une règle permanente et transversale : dès que l’agent décide d’écrire un test de diagnostic, il suit ce workflow sans attendre que l’utilisateur le réclame. Ce n’est pas une simple instruction à ajouter dans chaque prompt. Cette règle ne doit pas rester enfermée dans le seul profil Confluence.

### Éliminer une ancienne consigne contradictoire si elle existe

Une ancienne version de templates/01-coding.md livrée dans cette conversation contenait cette phrase, devenue inexacte avec les nouveaux outils :

```markdown
- Utilise les outils natifs Continue pour lire, chercher, éditer, appliquer et lancer les commandes. Le MCP apporte le suivi et la carte ; il ne remplace pas ces outils.
```

Si elle est encore présente, la remplacer dans la règle active ET son modèle par :

```markdown
- Choisis les outils selon leurs capacités et contrats. Réutilise les workflows dédiés
  du projet lorsqu’ils couvrent l’opération ; conserve les outils natifs pour les
  opérations qu’ils prennent effectivement en charge.
```

### Règle permanente à installer

Ajouter le bloc suivant dans `<CIBLE>/.continue/rules/01-coding.md` et `<KIT>/continue_kit/templates/01-coding.md`.
Conserver l’en-tête existant. Dans la version livrée, il comporte `alwaysApply: true` ; si ton fichier n’est pas permanent, corriger ce champ dans son en-tête YAML existant, sans ajouter un second en-tête.

```markdown
## Tests de diagnostic écrits par l’agent

Lorsque tu décides qu’un nouveau test de comportement ou de diagnostic est utile,
crée ou réutilise un fichier autonome sous tests/agent/ du projet concerné, puis
exécute-le avec run_project_test. N’attends pas une demande spéciale de l’utilisateur
sur la manière de tester. Utilise ce workflow au lieu de saisir le test sous forme
de Python ad hoc dans le terminal.

Les tests importent le code productif ; le code productif ne les importe jamais.
Supprimer ces fichiers doit laisser l’application utilisable. Utilise le venv et
le .env du projet cible. Si le workflow échoue ou manque, signale le problème au
lieu d’essayer successivement des Python globaux ou ceux d’autres projets.

Réutilise les tests existants et leur workflow de validation lorsqu’ils couvrent
déjà le besoin ; ne crée pas une seconde suite inutile. Ne crée pas de nouveau
test pour chaque lecture, question ou contrôle de routine.
```

Le choix du modèle reste gouverné par ses instructions : le code livré ne garantit pas qu’il ne contournera jamais cette règle avec un outil natif. Les tests locaux vérifient le fonctionnement du workflow, pas l’obéissance systématique du modèle. Une contrainte technique absolue nécessiterait un point de contrôle de l’exécution des outils de l’IDE ; cette interception n’est pas implémentée ici.

## 5 — Explication des limites actuelles, sans changer leurs valeurs

### Confluence

| Paramètre/valeur | Unité et effet |
|---|---|
| read : limit=12000 par défaut | Budget de CARACTÈRES du contenu renvoyé au modèle, pas de tokens, lignes ou taille maximale de page |
| Répartition entre plusieurs URL | Le code utilise max(1, limit // nombre_d_URL). Avec 3 URL et limit=12000 : environ 4000 caractères par page, pas 12000 pour chacune. C’est un budget indicatif ; le minimum de 1 caractère/page et les doublons peuvent faire varier le total |
| read : offset=0 | Position de départ dans le texte extrait ou le XHTML, indexée à partir de 0 ; appliquée à chaque page de l’appel |
| next_offset | Position de la suite pour la page concernée. Lire la suite en ciblant de préférence cette URL. Ce retour n’effectue pas lui-même l’appel suivant |
| 1 <= limit <= 30000 | Plafond applicatif de restitution choisi dans l’implémentation. Ce n’est pas une limite de l’API Confluence. 0 ne signifie pas illimité |
| format=text | Les caractères sont ceux du texte extrait |
| format=storage | Les caractères comprennent les balises XHTML ; un extrait peut couper au milieu d’une balise. Lire le corps complet avant une réécriture complète à partir de ces extraits |
| format=metadata | Renvoie titre/URL/version sans le corps. Le budget de contenu et offset n’ont pas d’effet sur le corps retourné dans ce mode |
| preview limité à 1200 | Aperçu textuel d’une proposition, distinct du budget de read. preview_truncated signale la coupe. Le contenu complet reste dans SQLite |
| resume(detail=True) | Restitue le XHTML complet de la proposition ; ce n’est pas une pagination de l’aperçu |
| prepare_remove / save | Ces actions utilisent le corps complet côté serveur et ne sont pas tronquées par limit=12000 ou l’aperçu 1200 |

Exemple : une page de 25000 caractères, lue seule avec limit=12000, est récupérée avec offset 0, puis 12000, puis 24000. Le dernier résultat a next_offset=null. Avec plusieurs pages, chaque next_offset appartient à sa propre page ; ne pas supposer un avancement commun si les tailles diffèrent.

### read_reference

| Paramètre/valeur | Unité et effet |
|---|---|
| limit=120, path fourni | Au maximum 120 LIGNES du fichier ; pas 120 caractères |
| limit=120, sans path ni query | Au maximum 120 noms de FICHIERS dans l’inventaire |
| limit=120, query fourni sans path | Au maximum 120 CORRESPONDANCES de recherche |
| 1 <= limit <= 300 | Nombre maximal d’éléments renvoyés pour l’appel. 0 n’est pas accepté |
| start_line=1 avec path | Première ligne du fichier, indexée à partir de 1 |
| start_line avec inventaire | Index du premier fichier dans la liste, aussi à partir de 1 ; le nom est réutilisé pour deux unités différentes |
| next_line | Position de reprise pour le mode fichier ou inventaire |
| query | Recherche textuelle insensible à la casse dans les noms et lignes ; ce n’est pas une analyse sémantique ni une recherche de symboles exhaustive |
| start_line en recherche | N’effectue PAS de pagination des résultats de query dans cette version ; affiner la recherche ou lire le path trouvé |

### Autres plafonds réellement présents

| Valeur | Effet et conséquence |
|---|---|
| 1000 fichiers en recherche de référence | Le code ne parcourt que les 1000 premiers fichiers admissibles, dans leur ordre de liste. Au-delà, truncated=true. Il faut conserver cette réserve dans le compte rendu ; ne pas conclure à une analyse exhaustive |
| 600 caractères par ligne de résultat de recherche | Aperçu de la ligne ; ouvrir ensuite le fichier par path pour son contenu complet |
| 2 000 000 octets par fichier de référence | Les fichiers plus gros sont refusés en lecture directe et sautés en recherche. Ce n’est pas la taille maximale d’un dépôt |
| UTF-8 | Les fichiers de référence non lisibles en UTF-8 sont refusés/sautés et comptés dans skipped_files en recherche |
| Test : timeout_seconds=60 | Délai par défaut d’exécution du test ; paramétrable jusqu’à 300 secondes dans run_project_test |
| HTTP Confluence : (10,60) | Délais du client actuellement livré pour connexion et lecture ; sans rapport avec le budget de caractères |

Ces valeurs bornent les restitutions et certains traitements ; elles ne constituent pas une politique de mémoire du modèle. En particulier, 120 lignes peuvent contenir beaucoup de caractères. Les plafonds de recherche 1000 fichiers/2 Mo sont de vraies limitations de cette première implémentation et doivent être annoncés, pas interprétés comme une absence de contenu.

## 6 — Principe à conserver pour les prochaines modifications

Bloc que tu peux ajouter à tes consignes de projet :

```markdown
Respecter les responsabilités des composants. Une description d’outil documente
son contrat, ses paramètres, résultats et effets. Ne pas y injecter une exception
spécifique à un autre domaine pour compenser une erreur de sélection du modèle.
Corriger les défauts de contrat ou de validation dans le composant concerné ;
placer les méthodes métier dans les profils spécialisés et les règles réellement
transversales dans la guidance commune. Toute valeur destinée aux futurs projets
doit être reliée à sa source de génération, sans écraser les surcharges locales.
```

## Chargement et validation

Les changements Python de ce rectificatif portent sur workflow.py, workflow_mcp.py et une ligne de description dans confluence_tools.py. Le nouveau fichier est le modèle templates/harness.json. Les changements de méthode se font dans les règles/profils selon leur périmètre.

Depuis le KIT, vérifier la syntaxe avec son Python local, puis recharger VS Code (Developer: Reload Window). Ouvrir une nouvelle conversation Agent ; les méthodes doivent déjà être dans le contexte permanent ou dans le profil spécialisé invoqué, sans recopier une consigne de test dans le prompt utilisateur.

Validation locale : 88 tests réussis, dont 7 nouveaux tests sur la génération du harness : création, chemins relatifs depuis le kit, conservation des surcharges, modèle absent, idempotence, modèle invalide et appel depuis configure sans --install-guidance. Les limites de validation précédentes restent applicables : MCP simulé, sous-processus/venv locaux, aucune validation sur ton poste Windows ou ton instance interne.
