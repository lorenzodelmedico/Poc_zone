class ReviewFormatError(ValueError):
    pass


def parse_review(raw, claims, evidence, user_context=None):
    if not isinstance(raw, str):
        raise ReviewFormatError("invalid_review_text")

    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewFormatError("invalid_review_json") from exc

    reviewed = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(reviewed, list):
        raise ReviewFormatError("invalid_review_schema")

    by_id = {claim["id"]: [] for claim in claims}
    ignored_items = 0
    for item in reviewed:
        cid = item.get("id") if isinstance(item, dict) else None
        if isinstance(cid, str) and cid in by_id:
            by_id[cid].append(item)
        else:
            ignored_items += 1

    verdicts = ("supported", "contradicted", "insufficient")
    context = user_context or {}
    rows = []

    for claim in claims:
        items = by_id[claim["id"]]
        item = items[0] if len(items) == 1 else {}
        proposed = item.get("verdict")
        llm_verdict = proposed if isinstance(proposed, str) and proposed in verdicts else None
        proofs = item.get("evidence")
        reason = item.get("reason")
        validated = []

        if not items:
            errors = ["claim_missing"]
        elif len(items) > 1:
            errors = ["duplicate_claim_id"]
        elif llm_verdict is None:
            errors = ["invalid_verdict"]
        elif proofs is None:
            errors = ["proof_missing"]
        elif not isinstance(proofs, list):
            errors = ["malformed_evidence"]
        elif not proofs and llm_verdict != "insufficient":
            errors = ["proof_missing"]
        else:
            validated, errors = check_proofs(proofs, evidence, context)

        rows.append({
            "id": claim["id"],
            "statement": claim["text"],
            "verdict": "indeterminate" if errors else llm_verdict,
            "llm_verdict": llm_verdict,
            "evidence": validated,
            "reason": reason if isinstance(reason, str) else "",
            "warning": ", ".join(errors),
            "validation_errors": errors,
        })

    counts = {
        verdict: sum(row["verdict"] == verdict for row in rows)
        for verdict in (*verdicts, "indeterminate")
    }
    return {"claims": rows, "counts": counts, "ignored_review_items": ignored_items}










-------------------














    trace = steps if steps is not None else []
    phase = "prepare_request"
    try:
        body = json.dumps(payload, ensure_ascii=False, default=str)

        phase = "llm"
        with timed_step(trace, "LLM de vérification", "llm") as step:
            step["inputs"] = {
                "payload_chars": len(body),
                "claim_count": len(claims),
                "passage_count": len(evidence),
            }
            response = api.llm(
                [
                    {"role": "system", "content": VERIFY_PROMPT},
                    {"role": "user", "content": body},
                ],
                return_metadata=True,
            )
            usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(usage, dict):
                step["usage"] = usage

        phase = "parse_review"
        with timed_step(trace, "Validation des preuves", "verification") as step:
            raw = response.get("text") if isinstance(response, dict) else None
            parsed = parse_review(raw, claims, evidence, context)
            step["details"] = {
                "counts": parsed["counts"],
                "ignored_review_items": parsed["ignored_review_items"],
            }

        result.update(parsed, status="completed", usage=usage, prompt=VERIFY_PROMPT, raw=raw)
    except Exception as exc:
        error_code = f"{phase}_failed"
        if isinstance(exc, ReviewFormatError):
            error_code = str(exc)
        elif isinstance(exc, TimeoutError):
            error_code = f"{phase}_timeout"

        result.update(
            status="error",
            error_phase=phase,
            error_code=error_code,
            error=type(exc).__name__ if is_draft else safe_error(exc),
        )
        if not is_draft:
            raise





















---------------------------------------------------------------------------------------------



MODE PLAN

Préparer un correctif ciblé du vérificateur documentaire. Lire le chemin réel du chat depuis ask/execute jusqu’à validate_document_draft, puis app/verification.py, le client de api.llm, le rendu UI et le bouton manuel verify_recorded. Rendre un plan court avec les fonctions à modifier et les tests ciblés. Appliquer le plan en mode APPLY.

Problème reproduit. Avec 12 affirmations correctement vérifiées sur 13, parse_review peut lever un ValueError à cause de la 13e entrée. select_supported bloque alors toute la réponse. Le même message UI peut aussi provenir d’un timeout ou de zéro affirmation validée. La politique de publication actuelle autorise une réponse partielle composée des seules affirmations validées.

En APPLY, réutiliser la chaîne de vérification et les fichiers existants.

1. Dans parse_review, rejeter globalement un JSON illisible ou une racine sans liste claims. Traiter par ID attendu les entrées de cette liste. Un ID absent, dupliqué, un verdict invalide ou une preuve invalide rend l’affirmation concernée indeterminate. Pour un doublon, invalider les deux entrées de cet ID. Ignorer et compter les entrées d’ID inconnu. Conserver llm_verdict, verdict et validation_errors par affirmation. Exiger les preuves valides pour supported et contradicted.

2. Publier uniquement des unités compréhensibles seules. Remplacer le découpage par ligne de Markdown sur le chemin automatique. Conserver ensemble une règle, ses conditions et ses exceptions. Exclure les titres et séparateurs Markdown du comptage. Utiliser les unités déjà disponibles côté génération si elles existent. Pour un brouillon historique dont les unités sont ambiguës, vérifier le bloc complet. Vérifier l’attribution des citations. Si un numéro désigne plusieurs extraits du même document, chercher la citation exacte dans chaque extrait séparément. Si le numéro désigne plusieurs documents, signaler une citation ambiguë.

3. Tracer séparément le chargement du run, le contrôle d’accès, l’appel LLM et le parsing avec timed_step. Garantir un délai borné dans le client HTTP réellement appelé, en tenant compte des retries. Propager jusqu’à l’UI error_phase et error_code. Distinguer au minimum source inaccessible, timeout LLM, autre erreur API, réponse LLM invalide et vérification terminée sans affirmation publiable. Tracer les durées, tailles, compteurs et codes d’erreur existants dans MLflow. Garder les passages, le profil et le JSON brut hors de cette télémétrie.

4. Sur le chemin du chat, vérifier que result["verification"], result["answer"] et result["sources"] reflètent la sélection finale et que l’UI affiche bien une réponse partial. Contrôler les droits avant l’appel LLM et la publication. Bloquer si le contrôle d’accès échoue, si la vérification échoue globalement ou si aucune unité n’est validée. Construire les sources affichées à partir des preuves des seules unités publiées.

5. Pour le bouton manuel, vérifier le contrat MCP et la disponibilité du snapshot de profil côté serveur. Sur un run mixte, utiliser le snapshot autorisé correspondant à profile_hash ou afficher explicitement profile_snapshot_unavailable / profile_snapshot_mismatch. Vérifier la version et les empreintes du brouillon, des preuves et du contexte avant toute réutilisation du cache, après le contrôle d’accès. Tracer la sauvegarde et l’export de façon à préserver le diagnostic initial si l’export échoue.

Validation avec des données synthétiques dans les tests existants.
- 12 affirmations validées et C13 invalide → partial, 12 affichées.
- C12 dupliquée à la place de C13 → partial, 11 affichées.
- JSON tronqué, zéro preuve valide ou source révoquée → blocage avec le motif correspondant.
- Timeout du client LLM → erreur LLM identifiable dans l’UI et dans les traces.
- Règle et condition sur deux lignes → aucune publication de la règle seule.
- Run mixte revérifié sans snapshot → motif explicite.
- Tester le chemin normal du chat en plus des appels directs au parseur.
