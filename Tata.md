Objectif : corriger la prise en charge des sources SharePoint dans l’application RAG.

Le périmètre concerne la chaîne qui reçoit un lien utilisateur, identifie la ressource SharePoint, récupère les documents concernés et transmet les bonnes valeurs à l’indexeur existant. Le fonctionnement interne de l’indexeur reste hors périmètre.

Première étape : analyser le dépôt et produire un diagnostic étayé ainsi qu’un plan de correction. Ne pas modifier les fichiers avant validation du plan.

BESOIN FONCTIONNEL CONFIRMÉ

L’utilisateur final n’est pas technique. Il fournit uniquement un lien copié depuis la barre d’adresse ou obtenu avec « Copier le lien ». Aucun chemin relatif, identifiant technique ou endpoint REST ne doit être demandé.

Comportement attendu :
- Lien vers un fichier : transmettre uniquement ce document à l’indexeur.
- Lien vers un dossier : récupérer tous ses documents et ceux de tous ses sous-dossiers, récursivement, sans sortir de ce périmètre.
- Lien vers une bibliothèque documentaire : parcourir sa racine et tous ses sous-dossiers.
- Hypothèse explicite pour un lien vers un site seul : couvrir les bibliothèques documentaires accessibles et non masquées de ce site, sans étendre automatiquement le parcours aux autres sites ou sous-sites. Les éventuelles exclusions techniques doivent être explicites.

Plusieurs sites SharePoint devront être pris en charge. L’URL actuellement codée en dur correspond seulement au site de test.

Le backend doit effectuer la résolution des liens de manière déterministe, avec les API SharePoint disponibles. Aucun appel LLM ne doit être nécessaire pour reconstruire une URL.

SYMPTÔMES ACTUELS

Aucun des liens essayés ne fonctionne :
- Ajout d’une source dans le chat : TypeError.
- Autre interface, au lancement de l’indexation : « attempted relative import with no known parent package ».

Les explications précédemment proposées sont des hypothèses. Ne pas considérer comme démontré que le TypeError provient d’un None retourné par le parseur, ni que Streamlit ou un thread provoque l’erreur d’import.

1. RETRACER LES DEUX PARCOURS RÉELS

Identifier, pour chaque interface :
- Le point d’entrée et les arguments reçus.
- La validation et le traitement du lien.
- Les fonctions du connecteur SharePoint appelées.
- Le contrat exact attendu par l’indexeur : types, champs, contenu ou références.
- Le mode d’import ou de lancement du traitement.

Retrouver les traces disponibles et reproduire les erreurs lorsque possible. Pour chaque cause retenue, fournir le fichier, la fonction, l’appel concerné et la preuve.

Si une erreur ne peut pas être reproduite, l’indiquer et prévoir l’instrumentation minimale nécessaire. Ne pas inventer la cause.

2. PRÉPARER UNE RÉSOLUTION COMMUNE DES LIENS

Les deux interfaces doivent utiliser le même traitement backend.

Examiner les fonctions existantes avant de créer une nouvelle abstraction. Le résultat de résolution doit identifier sans ambiguïté :
- Le site/Web SharePoint propriétaire de la ressource.
- La nature de la cible : fichier, dossier, bibliothèque ou site.
- Le chemin canonique et/ou l’identifiant retourné par SharePoint.
- Les informations nécessaires au contrat actuel de l’indexeur.

Adapter ce résultat aux structures existantes, sans imposer un nouveau format incompatible.

Formats à examiner :
- URL directe de fichier ou de dossier.
- Vue de bibliothèque Forms/AllItems.aspx.
- Vue avec paramètres de navigation, notamment id ou RootFolder.
- Visualiseur Office, notamment WopiFrame.aspx ou Doc.aspx avec sourcedoc.
- Liens générés par « Copier le lien ».

Pour les vues, extraire la cible lorsqu’elle est portée par les paramètres, puis la vérifier avec SharePoint. Une vue sans cible de dossier doit être rattachée à sa bibliothèque réelle.

Pour sourcedoc, distinguer un chemin d’un identifiant GUID. Si le lien fournit un GUID, retrouver la ressource via une capacité disponible sur le serveur, par exemple GetFileById si elle est prise en charge. Ne pas inventer un chemin à partir du seul nom de fichier affiché.

Un lien de visualisation n’est pas nécessairement un lien inutilisable. Une résolution API peut être nécessaire en complément du parsing.

Pour les liens de partage opaques, vérifier les mécanismes réellement disponibles. Si certains formats ne peuvent pas être résolus raisonnablement dans cet environnement, définir précisément cette limite et proposer un message simple indiquant quel lien copier à la place.

Ne jamais envoyer une page HTML de navigation à l’indexeur comme s’il s’agissait du document.

3. GÉRER LES SITES ET LES ENCODAGES CORRECTEMENT

Déterminer la base REST adaptée au site/Web identifié. Ne pas réutiliser systématiquement le site de test, supposer que tous les sites suivent /sites/<nom>, ni modifier une base globale partagée entre requêtes.

Séparer :
- Le découpage de l’URL.
- L’extraction des paramètres.
- Le décodage du chemin.
- L’échappement des chaînes OData.
- L’encodage de la requête HTTP.

Prévoir espaces, accents, apostrophes, caractères + et chemins déjà encodés. Éviter les décodages répétés et les doubles encodages.

Pour les caractères % et #, vérifier la disponibilité des API ResourcePath sur le serveur avant de les retenir. Ne pas supposer qu’une API documentée pour SharePoint Online est disponible sur cette installation.

Réutiliser l’authentification et la configuration réseau existantes. Ne pas introduire de dépendance à Microsoft Graph ou à un service cloud.

Les URL reconstruites, redirections et liens de pagination doivent rester dans le périmètre SharePoint autorisé, sans transmission d’identifiants à une autre origine.

4. PARCOURIR ET TRANSMETTRE LES DOCUMENTS

Prévoir :
- Tous les niveaux de sous-dossiers.
- Toutes les pages de résultats renvoyées par SharePoint.
- La prévention des parcours répétés et des doublons avec une identité fiable.
- La conservation de l’identité, de la provenance et des métadonnées de droits utilisées actuellement.
- Des appels HTTP avec délais bornés.

Transmettre chaque document selon le contrat réel de l’indexeur. Ne pas remplacer arbitrairement une valeur attendue par une URL REST ou par des octets.

Une erreur de résolution ne doit jamais provoquer un élargissement silencieux du périmètre, par exemple indexer toute la bibliothèque parce que le dossier demandé n’a pas été retrouvé.

Un parcours incomplet doit être signalé comme incomplet. Une erreur ne doit pas devenir une liste vide présentée comme un succès.

5. CORRIGER LES ERREURS AUX BONS ENDROITS

Pour le TypeError, identifier les types attendus et réellement transmis, puis corriger le contrat ou l’appel fautif. Un simple try/except affichant « URL invalide » ne suffit pas.

Pour l’erreur d’import, vérifier le contexte d’exécution effectif et corriger le point d’entrée ou les imports concernés. Éviter les modifications de sys.path et les imports de secours qui masquent le problème.

Distinguer dans les erreurs :
- Format de lien non pris en charge ou cible ambiguë.
- Ressource introuvable.
- Authentification ou accès refusé.
- API indisponible, timeout ou réponse inattendue.
- Erreur interne Python.

Conserver une trace exploitable côté backend, avec étape, classe d’erreur, statut HTTP et identifiant de corrélation, sans secrets ni contenu documentaire. L’interface doit afficher un motif compréhensible.

6. VALIDATION À PRÉVOIR

Préparer des tests ciblés avec liens fictifs et réponses SharePoint simulées :
- Fichier seul.
- Dossier contenant plusieurs niveaux de sous-dossiers.
- Bibliothèque et convention retenue pour un site seul.
- Formats de navigation, visualisation et partage pris en charge.
- Deux sites différents, sans utilisation accidentelle du site de test.
- Encodages et caractères particuliers.
- Plusieurs pages de résultats.
- Erreurs HTTP, timeout et réponse HTML inattendue.
- Passage par chacune des deux interfaces jusqu’à un indexeur simulé.

Les tests doivent vérifier les documents effectivement transmis et l’absence de documents hors périmètre, pas seulement l’absence d’exception.

RÉSULTAT ATTENDU POUR CETTE PREMIÈRE RÉPONSE

Fournir :
1. Les deux chaînes d’appels réellement observées.
2. Les causes démontrées et les points restant à vérifier.
3. Le plan minimal, avec les fichiers et fonctions concernés.
4. Les formats de liens pris en charge, conditionnels ou non pris en charge.
5. Les tests et critères d’acceptation.

Préserver le pipeline RAG existant. Éviter toute refonte générale ou ajout de dépendances sans nécessité démontrée. Distinguer les validations simulées des validations réellement effectuées contre SharePoint.
