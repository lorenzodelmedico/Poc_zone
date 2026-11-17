---
name: Format lisible des réponses
alwaysApply: true
---

Ces consignes s’appliquent aux réponses du chat, y compris après un appel d’outil.

- Utiliser des titres courts et séparer les sections par une ligne vide. Pour un inventaire, utiliser une puce par élément et mettre son nom en gras.
- Dans la prose et dans les cellules de tableau, écrire directement les symboles usuels en Unicode. Pour une flèche vers la droite, utiliser le caractère littéral → (U+2192). Le rendu attendu est « collecte → validation ».
- Proscrire la syntaxe LaTeX pour ces symboles. Pour la flèche, les formes `\rightarrow`, `\to` et `$\rightarrow$` sont interdites.
- Réserver les tableaux aux demandes explicites. Écrire le tableau en Markdown, hors bloc de code, avec une ligne vide avant et après. Utiliser de vrais retours à la ligne entre l’en-tête, le séparateur et chaque ligne de données.
- Encadrer chaque ligne de tableau par des pipes et garder le même nombre de colonnes sur toutes les lignes. Utiliser un séparateur compact sans alignement. Placer sous le tableau les extraits de code contenant un pipe littéral.
- Afficher la réponse et les résultats d’outils utiles. Omettre les balises de protocole, les marqueurs de canaux internes et les traces de raisonnement.
- Utiliser des backticks pour les chemins et les identifiants, et des blocs de code pour les extraits multilignes.

Exemple pour une demande explicite de tableau

| Étape | Statut |
|---|---|
| Collecte → validation | Terminé |
| Publication | À faire |
