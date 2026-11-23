APPLY — Lot 1G — Mémoire et reprise de sujet

1. Clôturer la recette 1F. Depuis Angular en mode API réel, ajouter
   un petit dossier SharePoint autorisé. Vérifier le POST 200 avec
   le job_id, suivre ce job jusqu’à completed et retrouver le document
   attendu dans l’index. Limiter le mini-correctif à un défaut reproduit.
   Vérifier aussi export_job. Si le suivi MLflow est actif et que le
   callback d’export est déjà disponible côté backend, le raccorder.

2. Vérifier ou compléter GET /api/conversations/suggestions.
   Réutiliser Access.suggestions(uid). Retourner jusqu’à trois objets
   Suggestion conformes à chat.models.ts avec conversation_id,
   theme_key, title, prompt et description si disponible. Reprendre
   le comportement Streamlit pour construire le prompt à partir de
   last_query et last_used. Angular doit rouvrir la conversation
   correspondante et envoyer ce prompt au clic sur « Actualiser le sujet ».

3. Vérifier ou compléter DELETE /api/conversations.
   Résoudre uid avec le mécanisme serveur existant. Appeler
   Store.forget(uid), puis Store.new_conversation(uid). Retourner
   la nouvelle Conversation avec conversation_id et title pour
   qu’Angular l’ouvre après confirmation. Respecter la conservation
   des traces d’évaluation prévue par le comportement Streamlit.

4. Tester l’effacement sur un stockage isolé avec des données jetables.
   Vérifier que l’historique de l’utilisateur testé contient uniquement
   la nouvelle conversation vide et que les données d’un second
   utilisateur sont préservées. Rapporter les routes vérifiées ou
   modifiées, les résultats observés et tout blocage restant.
