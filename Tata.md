Le plan est validé dans son architecture générale. Avant APPLY, intégrer ces derniers correctifs :

1. Vérifier que "get_context()" ne reconstruit pas le contexte monolithique. Le fast-path « Qui suis-je ? » doit exploiter les données déjà en session, avec 0 appel LLM et 0 appel MCP supplémentaire.
2. Distinguer explicitement l'intention "qui_suis_je" de la route générique "profile".
3. Valider le tool calling natif avec un jeu de tests plus représentatif (50–100 cas), incluant les arguments, les multi-tools et les erreurs.
4. Remplacer la troncature arbitraire du payload par une réduction structurée des champs, avec pagination et signalement des résultats incomplets.
5. Vérifier la compatibilité de "verify_answer" avec les réponses issues des outils structurés, ainsi que l'isolation des identités entre requêtes concurrentes.

Ensuite, implémenter de manière incrémentale en réutilisant les composants existants. Ne pas effectuer de réécriture complète inutile. Conserver MLflow, les contrôles d'accès et les autres workflows inchangés.

Exécuter les tests et présenter les résultats avant de considérer l'implémentation terminée.
