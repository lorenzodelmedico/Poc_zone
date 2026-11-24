APPLY — Rétablir l’indexation avec un correctif ciblé

Depuis le commit 82c6ed3, Chunker est passé d’un budget en mots à
une estimation en caractères. L’API d’embeddings renvoie HTTP 400
input_tokens au-delà de 512 tokens. Le plafond à 1 400 caractères
n’a pas résolu le problème.

1. Restaurer le découpage qui fonctionnait.
   Lire git diff 82c6ed3^ 82c6ed3 -- app/parsing.py. Réintégrer
   uniquement le découpage par mots du parent dans le Chunker
   actuel. Aligner count, split, le budget du préfixe et le
   chevauchement sur la même unité. Retirer le patch à 1 400
   caractères devenu redondant.

2. Protéger contre le dépassement résiduel.
   Si le tokenizer exact du modèle déployé est déjà disponible,
   vérifier l’entrée complète, titre et section compris, avant
   l’envoi. Sinon, sur le seul 400 de dépassement de contexte,
   reprendre une fois le document refusé avec un budget réduit
   via le même Chunker. Le repli doit aussi pouvoir couper un bloc
   sans espaces et conserver tout le texte. Si le refus persiste,
   remonter sa cause dans le job. Publier seulement une génération
   complète avec un vecteur par fragment final.

3. Rejouer le document qui échouait.
   Passer par « Ajouter et indexer » en mode API réel. Vérifier
   que le job termine, que la fin du document est retrouvable
   et que le document apparaît une seule fois dans « Mes documents
   indexés ». En cas d’échec de réindexation, vérifier que
   l’ancienne génération reste consultable.

Appliquer et tester dans ce passage. Rapporter le diff ciblé
et le résultat du job réel.
