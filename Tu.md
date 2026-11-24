APPLY — Stabiliser l’indexation sur la limite de 512 tokens

Le retour à une ancienne version de parsing.py a laissé des HTTP
400 input_tokens sur POST /embeddings. Corriger dans le Chunker et
le client existants.

1. Vérifier le Chunker chargé par le backend actif et mesurer la
   longueur maximale des chaînes finales juste avant le POST.
   En dépannage, appliquer 250 caractères maximum à chaque chaîne
   finale, préfixe compris. Redécouper le corps pour le conserver
   en entier. Raccourcir le préfixe d’embedding s’il prend toute
   la place et conserver les titres complets dans les métadonnées.

2. Si le tokenizer JSON de la révision déployée peut être importé,
   charger ce fichier une fois et compter l’entrée finale avec
   encode(..., add_special_tokens=True), troncature désactivée.
   Valider le comptage contre le service sur une entrée synthétique
   seule. Appliquer ensuite le plafond confirmé en tokens dans
   le Chunker.

3. Si l’import est indisponible, conserver le plafond de dépannage.
   Sur un 400 input_tokens persistant, tester l’entrée seule dans
   la requête. Si elle passe seule, réduire le lot via le batching
   existant. Si elle échoue seule, redécouper ce fragment via le
   même Chunker avec des tentatives bornées. Garder la cause du
   refus dans le job si le repli échoue.

Rejouer le document qui échouait depuis « Ajouter et indexer ».
Vérifier un job terminé, un vecteur par fragment et la fin du
document retrouvable. En cas d’échec, préserver l’indexation
précédente du document.
