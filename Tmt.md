## Rédaction guidée à partir d’un schéma technique

Lorsqu’un utilisateur demande de créer un document à partir d’un guide,
modèle ou schéma technique existant, engager un entretien section par
section avec confluence_document.

La connaissance du sujet ou la présence d’informations dans le dépôt
ne vaut pas accord pour rédiger directement un document complet.

### Démarrage

1. Identifier la page parente. Si seul son nom est fourni, consulter
   confluence_pages(action="read", format="metadata") sans urls pour
   retrouver les pages configurées. Demander une précision uniquement
   si les résultats ne permettent pas une identification certaine.
2. Appeler confluence_document(action="start") avec le parent,
   le titre et l’objectif.
3. Présenter les guides retournés et attendre le choix de l’utilisateur,
   sauf si celui-ci a déjà désigné précisément le guide.
4. Appeler choose avec le guide retenu.
5. Présenter la première rubrique et poser une question adaptée
   à ses indications. Terminer la réponse et attendre l’utilisateur.

### Pour chaque rubrique

- S’appuyer sur current_section, guidance et les faits déjà connus.
- Poser une question ciblée pour recueillir le contenu souhaité.
- Ne pas appeler propose avant une réponse de l’utilisateur portant
  sur cette rubrique.
- Rédiger uniquement la rubrique courante, puis présenter sa proposition.
- Après confirmation, sauvegarder cette proposition et vérifier le résultat.
- Passer ensuite à la rubrique suivante et attendre sa réponse.

Le titre, le sujet, l’URL parente et le choix du guide sont des informations
de cadrage. Ils ne constituent pas une réponse aux rubriques du document.

Ne pas préparer un document complet avec confluence_pages pour contourner
cet entretien. Un passage à la rédaction complète nécessite une demande
explicite de l’utilisateur.

Si l’utilisateur souhaite sauter une rubrique, la laisser à compléter.
Ne pas inventer de contenu pour terminer le document.






        """Construire un document guidé, rubrique par rubrique.
        start initialise un brouillon sans créer de page distante.
        choose charge le guide et expose current_section avec ses indications.
        propose prépare uniquement le contenu de la rubrique section_id.
        answer contient la réponse utilisateur recueillie pour cette rubrique,
        et non le titre, l’objectif ou le choix du guide.
