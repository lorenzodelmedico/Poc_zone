APPLY — Correctifs 1F et 1G

Corriger l’identité documentaire, le résultat des jobs d’indexation,
leur export MLflow et la reprise de sujet. Réutiliser le pipeline
SharePoint et les contrats Angular existants.

1. Dédupliquer le document après résolution SharePoint.
   Reproduire l’ajout d’un même fichier via la vue de sa bibliothèque
   puis via son lien direct. Suivre doc_id du résolveur au catalogue
   et jusqu’aux chunks et vecteurs. Appliquer la même règle d’identité
   dans le pipeline commun aux deux chemins. Réutiliser l’identifiant
   SharePoint stable dans son périmètre s’il est déjà disponible.
   Sinon, normaliser le chemin résolu pour que l’espace et %20 donnent
   la même clé. Laisser le résolveur interpréter les paramètres d’URL.

   Garder les deux périmètres de source et leurs rattachements.
   Un fichier inchangé doit réutiliser le doc_id sans republier ses
   vecteurs. Un fichier modifié doit mettre à jour ce même document.
   Pour les doublons existants, lister les références touchées et
   tester une réconciliation ciblée sur copie avec les ACL. Soumettre
   la simulation avant toute suppression dans la base d’usage.

2. Corriger le résultat et la trace du même job.
   Comparer le résultat du worker, l’état terminal persisté, le JSON
   de GET /api/conversations/{cid}/source-jobs/{jobId} et Angular.
   Compter les documents effectivement publiés. Distinguer un document
   déjà à jour d’un échec de publication. Sur un fichier inédit,
   attendre 1 document indexé au premier ajout, puis 0 nouveau et
   1 déjà à jour au second, avec un seul document dans l’index.

   Vérifier que export_job appelle source_job_trace avec le résultat
   terminal. Contrôler l’expérience et la destination réellement
   utilisées par local_mlflow(), puis retrouver la trace par job_id
   avec son statut et ses compteurs. Journaliser une erreur d’export
   séparément du résultat de l’indexation.

3. Valider la reprise sur un thème éligible.
   Créer depuis Angular un échange qui remplit les critères existants
   d’Access.suggestions. Vérifier l’écriture du thème par POST /turns,
   puis comparer uid, stockage, filtres et résultat du GET
   /api/conversations/suggestions. Corriger à l’étape où le thème
   disparaît. Au clic sur « Actualiser le sujet », vérifier l’ouverture
   de la bonne conversation et l’envoi unique du prompt.
