Corrige l’échec actuel du tool MCP user_jobs et la poursuite du workflow
avec des données absentes.

Constats observés :
- Le client reçoit une réponse MCP avec isError=True.
- Le contenu indique : "Error executing tool user_jobs: [Errno 9] Bad file descriptor".
- execute_tools transforme ensuite cet échec en final_data vide.
- Le workflow continue et appelle le LLM avec {}.
- Juste avant ce test, les prints du serveur MCP ont été redirigés vers sys.stderr.
- Le timeout de la session MCP a aussi été forcé à 30 secondes.
- Les précédents logs montraient des messages de debug sur le stdout MCP.

Travail demandé :

1. Inspecte le diff récent ainsi que le code réel de :
   - user_jobs et les fonctions appelées ;
   - création et durée de vie de la session MCP stdio ;
   - gestion de stderr et du processus serveur ;
   - execute_tools et le workflow qui appelle le LLM.

2. Identifie la ligne qui lève réellement Errno 9 côté serveur.
   Vérifie en priorité les écritures vers stderr, y compris avant le try
   de user_jobs, puis les autres opérations sur les flux ou fichiers.
   Conclus à partir du traceback et des tests, sans supposer que stderr
   est forcément responsable.

3. Corrige le raccordement ou la durée de vie du flux de diagnostic
   si la cause est confirmée. Réutilise la configuration de logging
   existante lorsque c’est possible. Les logs du serveur doivent rester
   hors du stdout réservé au protocole MCP. Une erreur de journalisation
   ne doit pas faire échouer la récupération des données.

4. Corrige la propagation des erreurs :
   - conserver l’échec du tool jusqu’au workflow ;
   - distinguer un résultat métier réellement vide d’un échec technique ;
   - si les données requises pour répondre sont indisponibles, ne pas
     générer une réponse de profil à partir de {} ;
   - retourner à l’interface un message d’erreur clair.

5. Rétablis le timeout configurable précédent si la valeur de 30 secondes
   a été imposée sans justification. Ne modifie pas les autres timeouts.

6. Vérifie aussi le cas observé précédemment où les arguments semblaient
   contenir des chaînes "True" et où fields valait []. Contrôle les types
   reçus à l’entrée du tool et corrige la conversion à la source si nécessaire.
   Préserve le comportement attendu lorsqu’aucun filtre n’est demandé.

7. Teste le parcours réel avec :
   - une requête simple ;
   - la requête large qui échouait ;
   - un échec simulé du tool pour vérifier que le LLM n’est pas appelé
     avec des données absentes ;
   - une vérification que stdout contient uniquement les messages MCP.

À la fin, indique la ligne exacte à l’origine d’Errno 9, le correctif,
les résultats des tests et toute cause qui reste non confirmée.
