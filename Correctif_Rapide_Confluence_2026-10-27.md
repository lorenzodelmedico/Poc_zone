# Correctif rapide — appels Confluence plus directs

## Ce qui est applicable maintenant

Ces modifications corrigent des causes visibles dans les captures. Elles ne dépendent pas des lots suivants du plan.

| Modification | Apport |
|---|---|
| Contrat prepare_update explicite et contrôle groupé des arguments | Réduit les essais « il manque le titre », puis « il manque le contenu » |
| Aperçu limité à 1 200 caractères | Évite le retour simultané du XHTML complet et de sa copie textuelle |
| resume(detail=True) | Permet toujours de récupérer une proposition complète après une interruption |
| Description de replace_document et règle de routage | Réduit les écritures locales et le recours au parcours guidé pour un simple remplacement distant |
| Confirmation courte quand tu fournis déjà tout le contenu | Évite de réimprimer la page entière ; une confirmation d’écriture reste demandée |

Le nombre d’appels du modèle n’est pas imposé par ces changements : descriptions et règle orientent son comportement. En revanche, le contrôle groupé et la taille bornée du retour sont des comportements du code.

Le déclenchement automatique des checkpoints et leur réinjection dans le contexte relèvent toujours du lot 4. Ces changements rapides n’implémentent pas ce lot.

## Où appliquer

`<KIT>` : racine du dépôt contenant `continue_kit` et son Python `.venv`.
`<CIBLE>` : racine du projet passé à `--project` dans le profil MCP actif. Les deux racines peuvent être identiques.

| Fichier sur ton poste | Action |
|---|---|
| `<KIT>/continue_kit/confluence_tools.py` | Blocs A à G |
| `<KIT>/continue_kit/workflow_mcp.py` | Bloc H, uniquement une description |
| `<CIBLE>/.continue/rules/01-coding.md` | Ajouter la règle I à la fin |
| `<KIT>/continue_kit/templates/01-coding.md` | Ajouter la même règle pour les futures installations |

Les blocs A à H ont été vérifiés avec la livraison Confluence de base et avec celle enrichie du correctif de vérification du 26 octobre. Aucun besoin d’appliquer ce dernier uniquement pour bénéficier du correctif rapide. Celui-ci ne remplace pas la vérification des écritures.

Si tu appliques ensuite l’ancien correctif de vérification, ses remplacements complets de `public` et `register_confluence_tools` rétabliraient certains anciens blocs : appliquer le présent correctif rapide en dernier. Ne recopier aucun ancien client Confluence/authentification.

## Blocs à recopier

Les blocs ci-dessous sont des modifications manuelles, avec indentation complète. Aucun remplacement complet de fichier existant.

### A — Retour compact de la proposition

Fichier : `<KIT>/continue_kit/confluence_tools.py`. Dans la méthode `public`, dans le bloc `if draft.get("pending"):`.

Remplacer :

```python
            result["proposal"] = {**pending, "preview": PageText(pending["content"]).text.strip()}
            result["next_action"] = "Présenter la proposition et attendre une confirmation écrite avant save."
```

par :

```python
            preview = PageText(pending["content"]).text.strip()
            result["proposal"] = {k: v for k, v in pending.items() if k != "content"}
            result["proposal"].update(
                content_chars=len(pending["content"]), preview=preview[:1200],
                preview_truncated=len(preview) > 1200,
            )
            if detail:
                result["proposal"]["content"] = pending["content"]
            result["next_action"] = (
                "Présenter la proposition et attendre une confirmation écrite avant save. "
                "Si le contenu intégral vient de l’utilisateur, rappeler la cible et le remplacement "
                "prévu sans recopier tout le document. Si une proposition doit être relue après "
                "perte du contexte, utiliser resume avec detail=True."
            )
```

### B — Lecture complète du brouillon seulement sur demande

Fichier : `<KIT>/continue_kit/confluence_tools.py`. Dans la signature de la fonction MCP `confluence_pages`, dans `register_confluence_tools`.

Remplacer :

```python
        offset: int = 0, limit: int = 12000, format: Literal["text", "storage"] = "text",
```

par :

```python
        offset: int = 0, limit: int = 12000, format: Literal["text", "storage"] = "text",
        detail: bool = False,
```

### C — Contrat explicite de prepare_update

Fichier : `<KIT>/continue_kit/confluence_tools.py`. Dans la docstring de `confluence_pages` uniquement.

Remplacer :

```python
        prepare_create : url=page PARENTE confirmée. prepare_update : url=page cible et version lue.
```

par :

```python
        prepare_create : url=page PARENTE confirmée.
        prepare_update exige dans UN SEUL appel : url=page cible, version=version lue,
        title=titre existant ou demandé, content=contenu XHTML COMPLET final. Ce n’est pas une
        préparation vide. Si le contenu intégral est fourni par l’utilisateur, le réutiliser ;
        ne pas recréer la page depuis son ancien contenu. replace_document vise les fichiers locaux.
```

### D — Confirmation courte pour un document déjà fourni

Fichier : `<KIT>/continue_kit/confluence_tools.py`. Dans la docstring de `confluence_pages` uniquement. La confirmation d’écriture est conservée.

Remplacer :

```python
        Présenter le texte proposé dans le chat et attendre UNE confirmation utilisateur.
```

par :

```python
        Présenter la proposition et attendre UNE confirmation utilisateur. Si le contenu intégral
        vient de l’utilisateur, rappeler la cible et la portée du remplacement sans le recopier.
```

### E — Expliquer le nouvel argument detail

Fichier : `<KIT>/continue_kit/confluence_tools.py`. Dans la même docstring de `confluence_pages`.

Remplacer :

```python
        resume lit un brouillon. recover rattache une écriture incertaine à sa page après vérification.
```

par :

```python
        resume lit un brouillon ; detail=True restitue son XHTML complet uniquement si nécessaire.
        Un aperçu tronqué n’est jamais le contenu à sauvegarder ; save utilise le brouillon complet.
        recover rattache une écriture incertaine à sa page après vérification.
```

### F — Tous les arguments manquants signalés en une fois

Fichier : `<KIT>/continue_kit/confluence_tools.py`. Dans la fonction imbriquée `run` de `confluence_pages`, pas celle de `confluence_document`. Le remplacement conserve la branche read et son corps.

Remplacer :

```python
        def run():
            if action == "read":
```

par :

```python
        def run():
            if action == "prepare_update":
                missing = [name for name, present in (
                    ("url", bool(url.strip())), ("version", version > 0),
                    ("title", bool(title.strip())), ("content", bool(content.strip())),
                ) if not present]
                if missing:
                    raise WorkflowError("prepare_update : arguments manquants ou invalides : "
                                        + ", ".join(missing)
                                        + ". Fournir url, version positive, title et content XHTML complet dans le même appel.")
            if action == "read":
```

### G — Transmettre detail à resume

Fichier : `<KIT>/continue_kit/confluence_tools.py`. À la fin de `run` dans `confluence_pages`, après les branches save et recover.

Remplacer :

```python
            return tools.resume(draft_id)
```

par :

```python
            return tools.resume(draft_id, detail=detail)
```

### H — Distinguer explicitement fichier local et page Confluence

Fichier : `<KIT>/continue_kit/workflow_mcp.py`. Dans la docstring de la fonction MCP `replace_document`, dans `build_server`.

Remplacer :

```python
        """Remplacer exactement un document texte existant par son contenu final.
```

par :

```python
        """Remplacer exactement un document texte existant par son contenu final.

        path est un chemin de FICHIER LOCAL relatif au projet. Pour une page Confluence,
        utiliser confluence_pages ; ne pas créer de fichier intermédiaire pour son remplacement.
```

### I — Règle active et modèle

Ajouter le bloc suivant à la fin de `<CIBLE>/.continue/rules/01-coding.md`, après le corps Markdown existant et sans modifier son éventuel en-tête YAML.
Ajouter le même bloc à la fin de `<KIT>/continue_kit/templates/01-coding.md` pour les prochaines installations de guidance. La copie du projet cible est celle qui prend effet maintenant.

```markdown
## Parcours direct pour une modification Confluence simple

- Pour remplacer une page Confluence dont le contenu final est fourni intégralement,
  utiliser confluence_pages. Ne pas passer par confluence_document, un guide ou un
  fichier local intermédiaire, sauf demande explicite distincte de l’utilisateur.
- Lire une fois la page si son URL, son titre ou sa version actuelle sont nécessaires.
  Pour un remplacement intégral explicite, ne pas reconstruire le nouveau document
  depuis l’ancien et ne pas parcourir les autres pages configurées sans nécessité.
- Appeler prepare_update une seule fois avec url, version, title et content XHTML
  complet dans le même appel. Ajouter les critères de vérification si cette version
  de l’outil les exige. Une préparation ne sauvegarde pas la page distante.
- Si un appel échoue, lire son erreur et corriger tous les arguments manquants avant
  de réessayer. Ne pas recréer plusieurs brouillons quand un brouillon correct existe.
- Si l’utilisateur a déjà fourni le contenu final complet, présenter seulement la
  page cible, le remplacement prévu et un bref aperçu ; demander la confirmation
  sans réimprimer tout le document. Pour un contenu rédigé ou transformé par le
  modèle, présenter les modifications utiles avant cette confirmation.
- Après confirmation, appeler save avec draft_id et revision renvoyés par la
  préparation. Un aperçu tronqué n’est jamais un contenu de remplacement.
- Relire une proposition complète par resume(detail=True) seulement si elle est
  nécessaire et n’est plus disponible dans le contexte. Respecter les contrôles
  d’écriture et de vérification existants avant le bilan de réussite.
```

## Chargement et test

1. Enregistrer tous les fichiers.
2. Depuis Git Bash à la racine du KIT, vérifier la syntaxe :

```bash
".venv/Scripts/python.exe" -m py_compile continue_kit/confluence_tools.py continue_kit/workflow_mcp.py
```

3. Dans VS Code : `Ctrl+Shift+P` → `Developer: Reload Window` / « Développeur : Recharger la fenêtre ».
4. Ouvrir une nouvelle conversation en mode **Agent**, avec le profil qui utilise le bon kit et le bon projet cible. Les outils confluence_pages et confluence_document gardent leurs noms ; confluence_pages accepte désormais detail.
5. Sur une page de test, redemander un remplacement avec un contenu intégral. Attendu : read si nécessaire → prepare_update → confirmation courte → save. Pas de replace_document pour cette opération.

Test de contrôle sans écriture : demander un prepare_update incomplet avec seulement l’URL et la version. L’erreur doit signaler title ET content ensemble. Aucun appel HTTP n’est nécessaire pour détecter ces champs manquants.

Pour une longue proposition, son retour doit avoir `preview_truncated=true`, un aperçu de 1 200 caractères maximum et `content_chars` indiquant la taille du XHTML complet. Ce marqueur n’appelle pas une pagination automatique. `save` utilise toujours le contenu complet conservé dans le brouillon ; `resume(detail=True)` peut le restituer si besoin.

La confirmation actuelle reste en place. Ces changements ne garantissent pas à eux seuls que le modèle choisira toujours le parcours minimal, ni qu’il raisonnera moins longtemps. Ils enlèvent des ambiguïtés et une duplication de contexte identifiées dans le code.

## Validation locale

Validation réussie : 60 tests sur la variante avec le correctif de vérification, et 43 sur la variante de base ; chacune inclut 6 tests ciblés supplémentaires pour le présent correctif. Les ancres manuelles reconstruisent exactement le code testé. Tests HTTP et SQLite locaux ; enregistrement MCP simulé et schémas Pydantic vérifiés. Aucune validation sur le poste Windows ou l’instance interne.
