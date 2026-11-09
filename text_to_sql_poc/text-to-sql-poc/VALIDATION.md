# État des vérifications de la livraison

Mise à jour : 9 novembre 2026 — sélection automatique des graphiques.

## Contrôles exécutés

| Contrôle | Résultat | Limite |
|---|---|---|
| Cache de jeton, expiration, réponse imbriquée et contrat d'authentification | Réussite | Service simulé, aucun identifiant réel. |
| Contrat HTTP JSON/form et gestion des erreurs | Réussite | Transport simulé. |
| Catalogue et choix du graphique | Réussite | Fiches réelles du projet ; sélections de modèle simulées. |
| Transmission des fiches au LLM | Réussite | Corps du véritable client inspecté avec transport simulé. |
| Rejet d'un choix inconnu, d'options libres, de labels invalides et d'une réponse sans graphique | Réussite | Contrats unitaires, pas d'inférence réelle. |
| Formatage JSON, dates UTC, tri, valeurs nulles et courbes incompatibles | Réussite | Données synthétiques. |
| Métadonnées et rejet d'identifiants invalides | Réussite | Fichier fictif. |
| Préparation des fichiers tiers ECharts | Réussite | Archive artificielle ; pas de véritable ECharts téléchargé. |
| Syntaxe des modules Python et JavaScript | Vérifiée lors de la préparation de l'archive | Aucun chargement des dépendances manquantes. |
| Options barres/courbe et mapping x/y | Réussite | JavaScript réel exécuté avec Node, sans moteur ECharts. |
| Interface sans sélecteur, question seule et clarification | Réussite | JavaScript réel avec DOM et réponses API simulés. |
| Liens Markdown locaux, variables documentées et archive extraite | Vérifiés lors de la préparation de l'archive | Pas de contrôle des services internes. |

### Tests Python

```bash
python -m unittest discover -s tests -v
```

**58 tests découverts : 36 exécutés avec succès, 22 non exécutés faute de dépendances dans l'environnement de préparation.**

Les 22 tests non exécutés se répartissent en 13 tests SQLGlot, 1 test MCP stdio et 8 tests API/MCP/SQL. Ils sont fournis dans l'archive. L'installation des paquets a été tentée ; le registre de paquets n'est pas accessible dans cet environnement. Aucun de ces tests n'est présenté comme réussi.

Les nouveaux tests API incluent le rejet de l'ancien champ manuel, la sélection inconnue, une courbe non temporelle bloquée avant accès à la base et le parcours temporel avec LLM/BDD simulés.

### Tests JavaScript

```bash
node --test tests/frontend.test.cjs
```

**5 tests exécutés avec succès, aucun test ignoré.**

Les tests utilisent le générateur d'options et le code d'interface réels, avec un DOM simulé. Ils ne remplacent pas une vérification visuelle dans un navigateur avec le véritable fichier ECharts.

## Vérifications nécessitant l'environnement cible

- Installation des dépendances puis exécution des 22 tests SQL/MCP/API restants.
- Compatibilité de l'API interne avec `chat/completions` et le nouveau contrat JSON SQL + graphique.
- Qualité du choix `bar`/`line`, du SQL et des clarifications sur des questions métier de référence.
- Contrat du service de jeton et acceptation du jeton par la base ou sa passerelle.
- Réseau, certificats, droits et correspondance entre les métadonnées et la vue.
- Résultats SQL réels comparés aux valeurs de référence.
- Rendu navigateur avec ECharts installé localement.

Le chemin applicatif est implémenté. Aucune validation complète sur les services réels ni performance de routage chiffrée n'est revendiquée. Le mode `DB_TOKEN_MODE=custom` reste un point d'adaptation explicite pour un mécanisme inconnu.
