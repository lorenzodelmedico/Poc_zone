# Chat Angular — plan et prompts par lot

Les API métier sont traitées en premier, avec l’historique des postes comme pilote. Le sourcing documentaire intervient après validation du parcours API depuis Angular. Chaque bloc est un prompt autonome pour Continue. Dans une nouvelle conversation, seul le résultat court du lot précédent est à joindre.

| Ordre | Lot | Mode | Critère de sortie |
| --- | --- | --- | --- |
| 1 | A1 · Vérifier le routage et les contrats API | Plan | Appel réel identifié et premier écart de cardinalité localisé par une preuve, ou vérification manquante explicitée. |
| 2 | A2 · Rendre la réponse sur les postes sensible à la demande | Agent · APPLY | Depuis Angular, les demandes « dernier », « tous » et « les 2 premiers » affichent les lignes attendues. |
| 3 | A3 · Étendre aux demandes de formation et aux autres lectures métier | Agent · APPLY | Chaque opération utilisée par le chat applique son contrat et passe ses propres tests. |
| 4 | B1 · Reproduire le problème de sourcing confirmé | Plan | Premier écart prouvé sur un cas documentaire reproductible. |
| 5 | B2 · Corriger le point de rupture documentaire | Agent · APPLY | Le cas reproduit passe depuis Angular et les droits d’accès sont vérifiés. |

## Ce que les captures permettent d’établir

Le client de données montré initialise `skip=0`, envoie éventuellement des filtres et transforme la réponse en lignes. Aucune taille de page n’est visible dans cet extrait. La taille par défaut, le mécanisme de pagination, l’ordre des résultats et le point où une liste se réduit à une occurrence restent à vérifier. Les descriptions de `documents` et `mixed` se contredisent sur le déclenchement des outils métier. Le test décisif part du chat Angular et identifie l’opération effectivement appelée.

## A1 · Vérifier le routage et les contrats API

```text
MODE PLAN. Expliquer pourquoi une seule occurrence apparaît sur l’historique des postes et les demandes de formation. Examiner le code actuel et utiliser les tests ou sondes de lecture autorisés. Proposer le correctif après le diagnostic.

1. Partir du chat Angular et suivre son endpoint réel, le routeur sémantique, le dispatch, l’outil métier ou le client direct, puis le retour affiché. Rejouer « Quel est mon dernier poste ? », « Quels sont mes postes ? » et « Quelles sont mes demandes de formation ? ». Donner la route, l’opération effectivement exécutée et les preuves code ou trace. Vérifier le rôle réel des routes profile, documents et mixed.
2. Pour les deux opérations, retrouver le contrat local ou une preuve issue d’un test de lecture approuvé. Relever les filtres et tris acceptés, la taille par défaut, le mécanisme de continuation, le signal de fin et la forme de la réponse. Vérifier la signification de skip et l’existence d’un paramètre de taille avant de proposer un nom ou une valeur. Repérer si la transformation en lignes perd une information de pagination.
3. Sur un jeu de données connu pour contenir plusieurs entrées, relever le statut HTTP, les lignes renvoyées par page, les lignes conservées par le client, les lignes envoyées au LLM et celles affichées. Distinguer la preuve du comportement de l’API réelle et le résultat d’un test simulé. Si un étage est inaccessible, le signaler et indiquer le test minimal qui manque.
4. Inventorier les lectures métier réellement accessibles depuis le chat. Pour les postes, relever toute règle métier documentée concernant le poste en cours, la date de référence, les ex æquo et « mes premiers postes » sans nombre. Demander une décision si la règle est absente ou incohérente.

Rendre un compte rendu court avec le trajet réel et ses fichiers et lignes, le contrat vérifié par opération, le premier écart par requête, les inconnues, puis les fichiers et tests prévus pour A2. Garder les preuves sous forme de statuts et de compteurs, avec des données synthétiques ou anonymisées.
```

## A2 · Implémenter le pilote sur l’historique des postes

```text
MODE AGENT — APPLY. Partir du compte rendu A1 et des règles métier confirmées. Faire varier l’appel et la réponse sur l’historique des postes selon le message reçu dans le chat Angular. Traiter cette opération avec Gemma 4 31B IT via le client interne existant.

1. Relier l’intention « historique des postes » à la bonne opération dans le workflow réellement utilisé par Angular. Réutiliser le routeur sémantique et le client ou outil existants. Déclencher l’extraction seulement une fois l’opération choisie. Pour une demande portant uniquement sur l’historique, utiliser l’API métier comme source.
2. Pour extraire les critères de la demande, envoyer à Gemma uniquement le message utile, le schéma des paramètres sélectionnables pour cette opération et les règles de sélection confirmées. Le backend choisit l’opération d’après le routage et prend l’identité et le périmètre autorisé depuis la session. Il valide les clés, types et valeurs avant l’appel. Une sortie invalide donne un état explicite sans appel métier. Une ambiguïté métier donne le cas de clarification prévu par le schéma.
3. Appliquer la sélection dans le backend. « Dernier poste » demande une ligne selon l’ordre métier validé. « Mes postes », « tous mes postes » et « historique des postes » demandent la liste complète autorisée. « Mes 2 premiers postes » demande les deux plus anciens selon l’ordre métier, ou toutes les lignes disponibles s’il y en a moins. Pour « mes premiers postes » sans nombre, appliquer la règle confirmée. Demander une décision si le cas reste ouvert.
4. Traduire les paramètres validés vers le vrai contrat HTTP. Quand l’API garantit le filtre et l’ordre requis, demander le volume utile. Sinon, lire les pages nécessaires et sélectionner côté backend après un tri fiable sur l’ensemble autorisé requis. Faire avancer la pagination selon le contrat. Si elle s’interrompt avant la fin attendue, signaler un résultat incomplet. Quand l’ordre global reste indéterminé, signaler que « dernier » ou « premiers » ne peuvent pas être établis. Distinguer résultat vide, résultat partiel et échec API.
5. Envoyer au second appel Gemma les lignes sélectionnées, dans leur ordre, avec les seuls champs nécessaires. Utiliser le flux de réponse Angular existant. Contrôler que le rendu contient les lignes sélectionnées et conserve les valeurs de l’API. Si le rendu est incomplet ou le volume dépasse le contexte disponible, afficher les lignes à partir des données validées. Garder la trace de la route, de l’opération, du mode de sélection et des compteurs par étape avec la corrélation existante.

Prompt d’extraction à intégrer
Contrat de l’opération : {{SCHEMA_JSON_DES_PARAMETRES}}
Règles de sélection : {{REGLES_METIER_CONFIRMEES}}
Demande : {{MESSAGE}}
Retourner uniquement un objet JSON conforme au schéma. Utiliser seulement les champs et valeurs autorisés. Si une donnée requise est indéterminable, retourner le cas de clarification prévu par le schéma.

Prompt de présentation à intégrer
Demande : {{MESSAGE}}
État de la lecture : {{ETAT}}
Résultats sélectionnés : {{LIGNES_VALIDEES}}
Présenter les résultats dans l’ordre fourni, à raison d’une entrée par ligne de données. Reprendre les valeurs présentes. Indiquer un résultat vide ou incomplet selon l’état fourni. Répondre brièvement dans la langue de la demande.

Utiliser au moins cinq postes synthétiques sur plusieurs pages. Depuis Angular et avec Gemma, prouver que « dernier » affiche la bonne ligne, « mes postes » affiche les cinq, et « mes 2 premiers postes » affiche les deux bons dans l’ordre attendu. Tester les cas zéro et une ligne, sortie JSON invalide, échec sur une page et règle d’ambiguïté validée. Contrôler le parcours profil et une question documentaire comme cas de régression. Rendre les commandes réellement lancées, distinguer les étapes simulées et indiquer les points encore à vérifier.
```

## A3 · Étendre le parcours aux API métier de lecture

```text
MODE AGENT — APPLY. Partir de la preuve A2 depuis Angular et de l’inventaire A1. Commencer par les demandes de formation, puis appliquer le même parcours aux autres opérations de lecture listées. Traiter et valider une opération à la fois.

1. Pour chaque opération, relier l’intention métier au bon outil et relever la cardinalité, les filtres et leurs types, le tri, la pagination et les champs utiles. Pour les formations, vérifier quel outil représente les demandes, les formations suivies et le catalogue, selon les capacités existantes. Distinguer ces intentions lorsqu’elles correspondent à des données différentes.
2. Réutiliser l’extraction courte, la validation, le client, la présentation et les traces d’A2. Injecter uniquement le schéma de l’opération sélectionnée. Appliquer uniquement les tris, limites et filtres valides pour cette opération. Pour un résultat unique par contrat, respecter cette cardinalité. Demander une décision sur tout défaut métier absent du contrat.
3. Tester chaque parcours depuis Angular. Pour une liste, vérifier plusieurs occurrences, le cas vide et au moins une sélection ou un filtre pris en charge. Pour une fiche unique, vérifier une seule fiche. Contrôler le routage d’une question documentaire et le parcours local « Qui suis-je ? » s’il est présent, avec zéro appel LLM pour ce dernier.

Rendre un compte rendu court par opération avec le message, la route, l’outil, la sélection ou le filtre observé, les pages et lignes lues, le résultat affiché et le test exécuté. Signaler les opérations dont le contrat ou le test reste indisponible.
```

## B1 · Identifier l’étape qui perd ou fausse la source

Le scénario documentaire reste à confirmer. Le doublon présumé entre deux représentations d’un chemin, le compteur à zéro et la trace manquante ont été signalés dans le fil Angular. La question exacte qui motive ce lot n’apparaît pas dans les cinq captures.

```text
MODE PLAN. Partir de {{CAS_DOCUMENTAIRE_CONFIRME}} avec l’action ou la question, le résultat observé et le résultat attendu. Reproduire ce cas depuis Angular sur des données synthétiques ou autorisées. Si le cas reste ambigu, demander la précision minimale avant de diagnostiquer.

1. Si le signalement concerne l’indexation, rejouer l’action et, si deux points d’entrée sont en cause, présenter le même fichier par les deux chemins. Relever l’identité donnée par le connecteur, la clé réellement utilisée dans l’index, le nombre d’entrées persistées et les statuts de chaque job avec ses compteurs. Si le chemin peut être représenté avec un espace ou %20, vérifier côté connecteur qu’il s’agit bien du même fichier. Comparer le compteur Angular au champ backend exact et retrouver la trace par identifiant de job. Confirmer la signification de « 0 » avant de conclure.
2. Si le signalement concerne une réponse sourcée, choisir un document autorisé qui contient la preuve attendue. Suivre la route, la recherche, le filtrage des droits, les passages transmis au modèle, les sources retenues par le vérificateur s’il existe, la réponse finale du backend et l’affichage Angular. Relever la première étape à laquelle la source attendue disparaît ou une autre source apparaît.

Rendre la reproduction, le premier écart prouvé, l’étape et les lignes de code, l’état attendu à cette étape et le test qui doit échouer avant B2. Limiter le plan de correction au point de rupture confirmé.
```

## B2 · Appliquer le correctif documentaire prouvé

```text
MODE AGENT — APPLY. Partir du diagnostic B1 validé, de sa preuve et du test reproductible. Corriger le composant à l’origine du premier écart et utiliser le pipeline documentaire existant.

1. Si l’identité documentaire diverge, utiliser l’identifiant stable du connecteur si son périmètre d’unicité est confirmé, ou une normalisation de chemin validée pour cette source. Tester les deux représentations du même fichier, la répétition de l’indexation et deux fichiers distincts. Vérifier le traitement des entrées déjà indexées et préserver leurs versions et leurs droits. Présenter séparément toute opération nécessaire sur des doublons historiques.
2. Si les compteurs ou la trace divergent, lier l’interface au bon job et aux statuts ou compteurs réellement persistés. Tester le premier ajout et la répétition de l’indexation pour distinguer documents ajoutés et documents déjà présents.
3. Si les preuves ou citations divergent, corriger l’étape identifiée dans B1. Vérifier que les sources affichées s’appuient sur les passages retenus, qu’elles sont autorisées pour la session et que leur lien pointe vers le bon document. Tester également un cas sans preuve accessible. Appliquer les règles de vérification déjà actives.

Réexécuter le cas B1 depuis Angular. Rendre l’étape corrigée, le résultat avant/après, les tests exécutés et les limites de validation.
```

## Références publiques

Pondération indicative de leur contribution au plan. Le comportement des API et du chat se vérifie sur le dépôt et les tests internes.

- **25 % · OpenAPI 3.1.1.** Définition des paramètres et des réponses par opération. [Spécification](https://spec.openapis.org/oas/v3.1.1.html#operation-object)
- **20 % · JSON Schema.** Validation des propriétés et rejet des clés hors schéma. [Référence](https://json-schema.org/understanding-json-schema/reference/object#additional-properties)
- **20 % · Google AIP-158.** Taille de page et signal de fin comme éléments du contrat. Une page courte peut avoir une suite. [Pagination](https://google.aip.dev/158)
- **15 % · RFC 3986.** Règles d’encodage par composant et prévention du double décodage. [Section 2.4](https://www.rfc-editor.org/rfc/rfc3986#section-2.4)
- **10 % · ALCE.** Évaluation de la qualité des citations à partir des preuves retrouvées. [Publication](https://aclanthology.org/2023.emnlp-main.398/)
- **10 % · OWASP LLM08.** Contrôle des droits d’accès aux documents pendant la recherche. [Recommandations](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/)
