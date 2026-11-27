Analyse l’implémentation actuelle du routage et de la recherche documentaire
dans ce dépôt. Objectif : déterminer précisément ce qui est réellement utilisé
lorsqu’une requête est envoyée depuis l’interface de l’application.

Contexte :
- Le projet peut utiliser la bibliothèque semantic-router d’Aurelio.
- Un modèle Granite est disponible pour les embeddings.
- Une recherche BM25 et un reranker peuvent également exister.
- Ne suppose pas que ces composants sont tous utilisés, ni qu’ils le sont
  aux mêmes étapes.

Consignes :
- Diagnostic uniquement : ne modifie aucun fichier, ne crée aucun fichier,
  n’installe aucune dépendance et ne change aucune configuration.
- Suis le vrai chemin d’exécution depuis l’envoi d’un message dans l’interface
  jusqu’au traitement backend. Ne te limite pas aux imports ou aux tests.
- Distingue clairement les faits prouvés par le code, les observations
  d’exécution et les points impossibles à confirmer.
- Pour chaque constat important, indique le fichier, la fonction et les lignes.
- Réutilise les tests existants si leur exécution est sans effet de bord.
  Sinon, indique la vérification minimale à effectuer, sans inventer de résultat.
- Ne lance pas d’opération sur de vraies données ou sur des services externes.

Questions à traiter :

1. CHEMIN RÉEL DEPUIS L’INTERFACE
   - Quel composant frontend envoie la requête et à quel endpoint backend ?
   - Quelles fonctions sont appelées ensuite ?
   - Le routeur est-il effectivement appelé ? Si non, à quel endroit
     est-il contourné ?
   - Si plusieurs chemins existent, précise lequel correspond à l’interface
     utilisée et dans quelles conditions les autres chemins sont activés.

2. ROUTAGE AURELIO
   - Quelle version de semantic-router est déclarée ou installée ?
     Précise si la version effectivement exécutée reste inconnue.
   - Quelle classe est instanciée ? Où, quand et par qui est-elle appelée ?
   - Quelles routes et quels exemples sont chargés, et dans quel index ?
   - Quel encodeur produit les embeddings des exemples et de la requête ?
     Granite est-il effectivement raccordé ?
   - Un encodeur lexical BM25 est-il configuré et effectivement utilisé
     dans le routeur ? Ne déduis pas son utilisation de sa présence dans le RAG.
   - Indique, si présents, le mode de combinaison, les paramètres top_k,
     les seuils et leur comportement en cas d’absence de route.
   - À quoi correspond le résultat du routeur et où est-il utilisé pour
     déclencher le traitement suivant ?

3. RECHERCHE DOCUMENTAIRE
   - Une fois le workflow documentaire déclenché, quelle est la chaîne
     effectivement appelée ?
   - Granite et BM25 sont-ils tous deux utilisés ? Sur quels index ou corpus ?
   - Comment leurs résultats sont-ils combinés ?
   - Le reranker Jina est-il réellement appelé ? Quand, sur quels candidats,
     et dans quelles conditions peut-il être ignoré ou échouer ?
   - Distingue bien cette recherche documentaire du choix initial de route.

4. VÉRIFICATION CIBLÉE
   - Si possible sans effet de bord, utilise une requête synthétique avec
     les tests ou mécanismes existants pour observer les étapes atteintes.
   - Indique séparément : routeur appelé ou non, route retournée,
     recherche dense appelée ou non, recherche BM25 appelée ou non,
     reranker appelé ou non.
   - Si l’exécution complète n’est pas possible, indique exactement ce qui
     manque pour confirmer chaque étape. Un test isolé du routeur ne prouve
     pas son appel depuis l’interface.

Format de réponse concis :

A. Tableau des composants : composant | rôle | configuré | appelé dans le
   parcours de l’interface | preuve fichier:ligne | certitude.

B. Parcours réel, sous forme de liste numérotée, depuis l’interface jusqu’au
   résultat. Précise les embranchements et les éventuels contournements.

C. Écarts ou problèmes constatés, classés par impact, avec preuves.
   Sépare les faits des hypothèses.

D. Vérifications restantes et, seulement si les preuves le justifient,
   proposition courte de correction. Ne pas implémenter.
