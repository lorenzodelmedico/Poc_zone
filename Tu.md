APPLY ciblé — Mes documents indexés et Reprendre un sujet

1. Rendre le retrait utilisable dans Angular.
Ajouter « Mes documents indexés » dans le chat. Brancher la liste
sur GET /api/me/indexed-documents et le bouton « Retirer » sur
DELETE /api/me/indexed-documents/{doc_id}. Actualiser la liste après
l’ajout d’une source et après un retrait réussi, sans rechargement.

Côté serveur, vérifier le lien du compte courant et ses droits
effectifs. Le retrait doit sortir le document de sa liste et de son
RAG personnel, même si une ancienne source reste sélectionnée.
Un rescan ou un ancien job doit respecter ce retrait.

Vérifier remove_my_document. Au dernier retrait, la purge doit
couvrir SQLite et l’index vectoriel. Tenir compte des rétentions
existantes et rendre le nettoyage relançable et sûr face à un ajout
concurrent. Vérifier sur copie la compatibilité avec l’ancien
catalogue SharePoint, y compris les doc_id dérivés de l’URL.

2. Rétablir la création automatique et la reprise des thèmes.
Rechercher les écritures existantes dans themes et suivre un tour
réussi depuis POST /turns. Si Angular contourne une écriture déjà
présente, la raccorder. Si elle manque réellement, créer ou mettre
à jour le thème après un tour éligible, à partir du sujet déjà
identifié par le routage. Utiliser le schéma réel du Store et
conserver une clé stable. Le Store reste chargé de la persistance.

Dans GET /api/conversations/suggestions, produire le champ prompt
attendu par Angular à partir du thème et de sa dernière question.
Vérifier le rôle de context_hash avant de valider sa suppression.
La suggestion et la conversation doivent rester accessibles au
compte courant selon ses droits actuels. Au clic, ouvrir le
conversation_id existant et envoyer le prompt une seule fois.

Recette à exécuter sur données de test.
- A et B utilisent le même SQLite et le même index. B ajoute le
  fichier déjà indexé par A avec zéro nouvelle écriture vectorielle.
  A le retire depuis Angular. B le retrouve encore dans sa recherche.
  B le retire à son tour. Vérifier la purge SQLite et vectorielle
  si le document n’a plus aucune référence à conserver.
- Un compte sans thème en crée un via un échange éligible dans le
  chat. Vérifier sa présence dans « Reprendre un sujet » et son
  actualisation dans la conversation d’origine.

Rapporter les causes confirmées et les tests réellement exécutés.
