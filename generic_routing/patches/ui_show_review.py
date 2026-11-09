# Remplacer show_review() dans app/ui.py. Aucun nouvel import requis.
def show_review(verification):
    reasons = {
        'profile_snapshot_unavailable': 'L’instantané du profil utilisé n’est plus disponible pour un nouveau contrôle.',
        'profile_snapshot_mismatch': 'Le profil disponible diffère de celui utilisé pour cette réponse.',
        'no_evidence': 'Aucune source exploitable pour la vérification.',
        'no_claims': 'Aucune affirmation à vérifier.',
        'profile_unavailable': 'Le contexte du profil est indisponible.',
        'clarification': 'Une précision sur la demande est nécessaire.',
        'general_model_knowledge': 'Réponse générale du modèle — aucune validation documentaire.',
        'source_not_ready': 'Les sources sélectionnées ne sont pas encore disponibles pour la recherche.',
    }
    if verification.get('status') == 'error':
        st.error('La vérification a rencontré une erreur technique.')
        return
    if verification.get('status') == 'not_applicable':
        reason = verification.get('reason', '')
        st.info(reasons.get(reason, reason))
        return
    if verification.get('method') == 'api_field_binding':
        st.caption('Les valeurs affichées proviennent directement du contexte API du profil.')
    labels = {'supported': 'Validé', 'contradicted': 'Contredit',
              'insufficient': 'Preuves insuffisantes', 'indeterminate': 'Contrôle incomplet',
              'not_applicable': 'Champ indisponible'}
    for claim in verification.get('claims', []):
        st.write(labels.get(claim['verdict'], claim['verdict']) + ' — ' + claim['statement'])
        if claim.get('reason'):
            st.caption(claim['reason'])
        for proof in claim.get('evidence', []):
            if proof.get('source') == 'user_context':
                st.caption('Source — contexte API du profil.')
            elif 'citation' in proof:
                st.text(f"[{proof['citation']}] {proof.get('quote', '')}")
        if claim.get('warning'):
            st.caption('La preuve n’a pas pu être validée ; ce passage est écarté de la réponse.')
