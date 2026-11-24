PLAN puis APPLY. Implémenter le tool calling natif de Chat Completions dans le parcours profile du chat Angular. Le LLM choisit l’outil et ses arguments à partir de la question. Le backend exécute l’outil MCP, renvoie son résultat au LLM, puis affiche la synthèse dans Angular.

Phase 1 — Vérifier la faisabilité avec un seul fichier de test

Créer et exécuter un fichier de test avec la même API compatible, le même modèle et la même authentification que l’application. Appeler POST /chat/completions via le transport HTTP existant, avec stream=false, pour observer la réponse brute de l’API.

Déclarer deux fonctions fictives dans tools, chacune au format {"type":"function","function":{"name":...,"description":...,"parameters":...}}. La première lit les postes avec une limite et un ordre de tri. La seconde lit les demandes de formation. Envoyer « Quel est mon dernier poste ? » avec tool_choice="required" pour demander un appel tout en laissant le modèle choisir la fonction. Si ce réglage échoue, rejouer la même demande une fois avec tool_choice="auto".

Vérifier dans choices[0].message.tool_calls que le modèle a choisi l’outil des postes et produit des arguments JSON valides pour un seul poste, du plus récent au plus ancien. Exécuter la fonction fictive avec ces arguments. Ajouter à messages le message assistant contenant les tool_calls, puis un message {"role":"tool","tool_call_id":<id de l’appel>,"content":<résultat sérialisé en texte>}. Relancer Chat Completions pour la synthèse et vérifier que sa réponse reprend un intitulé de poste fictif fourni uniquement par l’outil.

Passer à la phase 2 si cet aller-retour réussit. En cas d’échec, indiquer l’étape exacte et le résultat observé.

Phase 2 — Intégrer dans l’application

Réutiliser le routeur, le client LLM et l’exécuteur MCP existants. Pour la lecture métier, construire tools à partir des outils MCP autorisés pour la demande. Utiliser leur nom, leur description et leur inputSchema comme function.parameters. Reprendre le mode tool_choice validé et utiliser stream=false pour cet appel interne de sélection.

Lire les appels dans message.tool_calls. Valider le nom et les arguments contre les outils exposés. Utiliser l’identité issue de la session. Exécuter chaque appel valide via MCP et rattacher son résultat au tool_call_id correspondant. Appeler la synthèse après réception des résultats et publier son texte via le flux Angular existant. Pour un appel absent, invalide ou en échec, afficher un état explicite. Réserver « Aucun résultat » à une lecture réussie à zéro ligne.

Valider depuis Angular avec « Quel est mon dernier poste ? » sur un historique connu. Vérifier l’outil choisi, la limite et le tri selon son contrat réel, puis le poste affiché. Rendre la commande du test de faisabilité, son résultat et les fichiers modifiés.
