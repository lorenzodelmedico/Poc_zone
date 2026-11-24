PLAN puis APPLY — Identité documentaire, « Mes documents indexés » et reprise

Appliquer les étapes dans l’ordre, selon le workflow du dépôt. Partir
des services et du schéma réels. Les deux problèmes observés sont un
doublon entre lien direct et parcours SharePoint, et une liste de
suggestions vide alors que la table themes contient déjà des entrées.

1. Donner une identité unique à chaque fichier SharePoint

Suivre les deux parcours jusqu’à collect_source et à l’attribution de
doc_id. Comparer les métadonnées réellement renvoyées pour le même
fichier. Utiliser comme clé l’identifiant natif du fichier, dans sa
portée d’unicité réelle. UniqueId est un candidat à vérifier dans le
client actuel. Compléter la résolution par ce même client si nécessaire.

Appliquer la règle dans le point commun, avant la recherche du document
existant et la création des chunks. Imposer l’unicité de cette clé en
SQLite. Conserver l’URL comme lien de navigation et raw_hash comme
indicateur de changement de contenu. Un fichier modifié garde son
doc_id et suit le mécanisme existant de mise à jour des vecteurs.

Pour les doublons historiques, préparer une réconciliation relançable
sur copie. Prouver l’identité commune avant fusion et préserver la
version active, les droits, les rattachements et les citations. Fournir
une simulation avant toute suppression sur la base d’usage.

2. Rattacher l’indexation à chaque utilisateur

Réutiliser une liaison persistante existante si elle couvre ce besoin,
sinon ajouter une relation unique (uid, doc_id). Résoudre uid côté
serveur. Cette relation représente une demande d’indexation et s’ajoute
aux contrôles d’accès existants. Pour l’ajout d’un dossier ou d’une
bibliothèque, rattacher les fichiers autorisés réellement collectés
par ce job, y compris les fichiers déjà à jour.

Si A a indexé un fichier et que B, autorisé, en demande l’ajout, créer
le lien de B vers le même doc_id. Réutiliser les chunks et vecteurs à
version inchangée. Distinguer dans le job « document indexé » et
« document existant ajouté à mes documents ». Pour l’historique,
reconstituer les liens uniquement lorsque la demande de l’utilisateur
est prouvée par les données existantes.

Ajouter une vue Angular « Mes documents indexés », reliée à une
projection de SQLite via l’API. Proposer GET /api/me/indexed-documents
et DELETE /api/me/indexed-documents/{doc_id} si aucun contrat équivalent
n’existe. La liste contient les documents à la fois demandés par le
compte courant et accessibles selon les règles existantes.

Le bouton « Retirer de mes documents » retire le lien de ce compte et
actualise la liste dès le succès du DELETE. Le document sort aussi
de son périmètre de recherche personnel, même si une ancienne source
de conversation le référence encore. Un ancien job ou un rescan
automatique doit respecter ce retrait. Un nouvel ajout explicite peut
rétablir le lien après contrôle des droits.

Tant qu’une demande active subsiste, conserver le document partagé.
Au départ du dernier demandeur, déclencher la purge du catalogue, des
chunks et des vecteurs de l’application, sous réserve des références
collectives ou règles de rétention déjà prévues par le projet.
Décider du dernier retrait dans la même transaction que la suppression
du lien. Coordonner les ajouts et la purge par identité documentaire
pour qu’une purge en cours ne puisse supprimer une nouvelle génération.
Rendre le nettoyage relançable en cas d’échec partiel.

3. Réparer « Reprendre un sujet » à partir des thèmes existants

Inspecter le schéma réel de themes et suivre une entrée existante.
Vérifier que le GET /api/conversations/suggestions utilise la même
base et le même uid que le chat. Contrôler le rattachement à une
conversation et relever le premier filtre d’Access.suggestions qui
écarte l’entrée, ou l’écart de projection si elle arrive jusqu’à
l’API. Corriger à cet endroit. Utiliser les entrées existantes pour
le diagnostic. Le clic « Actualiser le sujet » doit ouvrir la bonne
conversation et envoyer le prompt une seule fois.

Recette sur données de test

- Même fichier ajouté par lien direct et par parcours de dossier,
  avec et sans %20. Vérifier un doc_id et une seule génération active.
  Deux fichiers distincts au contenu identique gardent deux identités.
- A indexe, B déjà autorisé voit le fichier seulement après sa demande.
  L’ajout de B crée un lien et zéro publication vectorielle. Un compte
  sans accès ne peut ni le lister ni le rattacher.
- A retire le fichier. Il disparaît pour A et reste utilisable par B.
  B le retire à son tour. Vérifier la purge finale pour un document
  uniquement détenu à la demande. Tester aussi ajout concurrent,
  retrait répété et reprise après un échec de nettoyage.
- Vérifier les compteurs du job dans l’API, Angular et la trace MLflow.
  Vérifier une suggestion admissible depuis Angular et préserver le
  parcours « Effacer les échanges ».

Rapporter le champ SharePoint retenu et sa portée, la cause confirmée
du problème de reprise, les migrations et les résultats exécutés.
Identifier séparément les essais qui restent à faire en API réelle.
