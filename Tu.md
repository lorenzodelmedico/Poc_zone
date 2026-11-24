APPLY — Correctif ciblé et recette 1F–1G

1. Vérifier la ligne réellement présente dans app/http_api.py.
   Si le callback utilise source_job_trace(*local_mlflow(), job,
   local_mlflow()[1]), le remplacer par un callback qui récupère
   mlflow et experiment_id une seule fois, puis appelle
   source_job_trace(mlflow, job, experiment_id). Confirmer la signature
   dans le dépôt. En cas d’échec d’export, journaliser l’exception avec
   le job_id et restituer le résultat réel de l’indexation.

2. Vérifier le résultat retourné par index_from_chat. Transmettre
   séparément les document_ids rattachés à la source, y compris les
   fichiers inchangés, et le report de once() pour ce job. Adapter
   _source_jobs_run pour alimenter les compteurs à partir de changed
   et unchanged. Vérifier que changed correspond aux publications
   réussies. Exposer le résultat cohérent dans l’API, Angular et MLflow.

3. Tester le même fichier via parcours de bibliothèque et lien direct.
   Comparer le file_url transmis à stable_id, le doc_id et les écritures
   vectorielles. Si les identités divergent, corriger la normalisation
   dans le flux commun après résolution SharePoint. Tester aussi la
   mise à jour du fichier et le rattachement aux deux sources.

4. Tester la reprise sur un thème admissible créé depuis Angular.
   Si le GET renvoie [], suivre l’écriture du thème, les critères
   d’Access.suggestions et la projection HTTP pour localiser l’écart.

Rendre les résultats exécutés avec le job_id de test, le JSON final,
la présence de la trace MLflow et le résultat de la reprise. Pour
chaque test bloqué, indiquer l’étape et le motif précis.
