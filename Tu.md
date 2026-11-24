APPLY avec ces corrections au plan.

- Imposer l’unicité sur la clé native SharePoint (périmètre, ID fichier). Le lien direct et le parcours doivent résoudre la même clé, y compris via sourcedoc. Réconcilier l’historique sur copie, uniquement si cette identité est confirmée. Le titre et raw_hash servent au repérage.
- Brancher la vue Angular « Mes documents indexés » sur les demandes explicites du compte ET ses droits actuels. Appliquer ce filtre au RAG personnel. Retirer le lien immédiatement et empêcher sa recréation par un rescan ou un ancien job.
- Enregistrer la purge dans la transaction du dernier retrait, en tenant compte des rétentions existantes. Le nettoyage des chunks et vecteurs doit être relançable et coordonné avec les ajouts concurrents.
- Pour la reprise, projeter les thèmes existants dans la route HTTP. Ouvrir le conversation_id de la suggestion et envoyer son prompt une seule fois via POST /turns.
