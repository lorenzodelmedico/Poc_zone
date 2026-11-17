Le plan est presque validé, mais quatre ajustements sont nécessaires :

1. Corriger le fast-path « Qui suis-je ? » : utiliser directement le contexte utilisateur déjà chargé en session, sans appeler trois outils MCP ni le LLM.
2. Valider le tool calling réel de Gemma 4 via le proxy existant avant de considérer ce mécanisme comme fiable. Comparer le nombre d'appels LLM et la latence au Planner JSON.
3. Remplacer la sélection des outils par préfixe "user_" par un registre explicite par workflow, alimenté par les schémas MCP réels. Prévoir un cache des métadonnées.
4. Garantir l'isolation des identités entre requêtes, la limitation des payloads et le maintien obligatoire des contrôles de vérification, y compris sur réponse partielle.

Conserver le routeur sémantique, les mécanismes MLflow et l'architecture existante. Mettre à jour le plan et les tests d'acceptation, sans coder pour l'instant.
