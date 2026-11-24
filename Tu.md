feat(api): exposer le profil utilisateur (1A)

- Ajoute GET /api/me avec résolution de l’identité POC côté serveur.
- Projette le profil dans le modèle SessionProfile.

feat(chat): raccorder les conversations et l’historique (1B)

- Expose la liste, la création et la lecture des conversations.
- Raccorde le proxy Angular et indique quels messages peuvent être évalués.

feat(chat): diffuser la progression des tours (1C)

- Ajoute POST /turns et les événements de progression en NDJSON.
- Corrige la fin de flux et recharge les messages persistés.

feat(chat): enregistrer les évaluations par message (1D)

- Raccorde la lecture et l’enregistrement d’un avis au run du message.
- Relie la sauvegarde de l’avis à l’export du run vers MLflow.

feat(rag): exposer les réglages documentaires et le suivi des jobs (1E)

- Raccorde la recherche documentaire, la vérification et la sélection des sources.
- Expose le statut et la progression des jobs d’indexation.

feat(rag): ajouter une source SharePoint depuis Angular (1F)

- Ajoute POST /sources et réutilise la file d’indexation existante.
- Retourne l’état documentaire mis à jour avec le job_id.
- Corrige l’import de enqueue_source_sync dans la route.

feat(chat): raccorder la mémoire et l’export des jobs (1G)

- Expose jusqu’à trois suggestions de reprise via Access.suggestions.
- Efface les échanges et les thèmes de l’utilisateur puis ouvre une discussion vide.
- Branche source_job_trace sur le callback d’export des jobs.
