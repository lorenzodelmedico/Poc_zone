APPLY correctif 1B — Réparer « Nouvelle discussion ».

Le profil et les anciens échanges s’affichent après une conversion de type sur GET /messages. Le bouton « Nouvelle discussion » affiche « Création de la discussion impossible ».

1. Reproduire un seul POST /api/conversations avec le corps {}, comme Angular. Relever le statut HTTP et l’erreur serveur anonymisée. Si le POST échoue, vérifier dans la liste des discussions si l’écriture a déjà eu lieu avant de réessayer.
2. Inspecter le handler dans app/http_api.py. Vérifier les champs requis à l’entrée, la signature et le retour réel de Store.new_conversation(uid), puis la validation du modèle de sortie. Angular attend {conversation_id: string, title: string}. Si une conversion est nécessaire, l’appliquer au champ concerné à la frontière HTTP. Préserver le correctif de lecture déjà appliqué.
3. En mode start:api, vérifier qu’un clic crée une seule discussion, l’ouvre avec un historique vide et qu’elle est retrouvée après actualisation. Vérifier aussi la réouverture d’une ancienne discussion.

Pour « L’avis enregistré est indisponible », relever uniquement le statut du GET /api/conversations/{cid}/messages/{messageId}/feedback et vérifier si la route existe. L’avis sera traité dans son propre lot.

Rapporter la cause constatée, le correctif et les résultats réellement observés. Le lot 1C sera testé après cette correction.
