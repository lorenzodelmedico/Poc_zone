Appliquer une correction ciblée en intégrant les réserves suivantes, sans nouveau cycle de planification.

1. Établir la cause réelle du TypeError.
Retrouver sa traceback dans le suivi existant : fichier, fonction, ligne et message nettoyé. Vérifier tous les appelants de check_proofs et le code effectivement exécuté.

Sur le chemin montré, evidence=None est déjà rejeté par isinstance(proof, list), avec un ValueError avant check_proofs. Ce scénario ne démontre donc pas le TypeError observé.

Si la trace manque, ajouter l’instrumentation minimale pour identifier l’étape et le champ fautifs. Ne pas présenter une hypothèse comme une cause confirmée.

2. Valider les structures sans masquer les anomalies.
Distinguer champ absent, null, liste vide et type incorrect, selon le contrat attendu.
Ne pas transformer systématiquement les données invalides en listes ou dictionnaires vides.

Une enveloppe de résultat contenant claims et counts peut rester stable, mais une vérification invalide doit conserver son erreur et ne jamais être présentée comme réussie.

3. Préserver la signification des résultats.
Une affirmation ou une preuve mal formée doit rester identifiable comme non vérifiée.
Ne pas supprimer silencieusement les affirmations invalides des compteurs.
Ne pas réduire artificiellement le dénominateur du taux de couverture.
Une liste vide alors que des affirmations sont attendues ne doit pas devenir une validation.
Conserver la politique d’acceptation et les seuils existants.

4. Tester le comportement complet.
Couvrir : résultat valide, claims=null, evidence=null, éléments de types incorrects, affirmations omises et résultat partiel.
Vérifier les statuts, les compteurs et le comportement final de l’application, au-delà du parsing seul.

Réutiliser la journalisation/MLflow existante sans enregistrer de payload sensible complet. Préserver la cause initiale des exceptions.

Terminer par un bilan court : cause démontrée ou encore inconnue, modifications, tests réellement exécutés et validation restante.
