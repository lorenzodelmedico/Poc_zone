"""Panneau Streamlit ; le contexte et les travaux restent dans le backend."""
from app.sources import get_skill_state, set_document_search, select_source
from app.sync import enqueue_source_sync, get_source_job

def document_skill_view(api, user_id, cid, *, index_existing, allowed_roots, export_job):
    import streamlit as st
    state = get_skill_state(api, user_id, cid)
    with st.popover('Recherche documentaire', icon=':material/folder_open:'):
        enabled = st.toggle('Activer la recherche documentaire', value=state['document_search'], key=f"document_skill_{cid}_{state['revision']}")
        set_document_search(api, user_id, cid, enabled)
        st.caption('Sans source sélectionnée, la recherche utilise le périmètre autorisé déjà indexé.')
        with st.form(f'add_source_{cid}', clear_on_submit=True):
            url = st.text_input('URL du site, de la bibliothèque ou du dossier SharePoint')
            submitted = st.form_submit_button('Ajouter et indexer')
        if submitted:
            try:
                enqueue_source_sync(api, user_id, cid, url, index_existing=index_existing, allowed_roots=allowed_roots, export_job=export_job)
                st.rerun()
            except Exception as exc:
                st.error(f'Ajout de la source impossible : {type(exc).__name__}')
        state = get_skill_state(api, user_id, cid)
        for source in state['sources']:
            selected = st.checkbox(source['url'], value=source['selected'], key=f"source_{cid}_{source['source_id']}")
            select_source(api, user_id, cid, source['source_id'], selected)

        @st.fragment(run_every='1s')
        def progress_view():
            for source in get_skill_state(api, user_id, cid)['sources']:
                try:
                    job = get_source_job(api, user_id, cid, source['job_id'])
                    st.caption(job['progress'])
                    if job.get('documents_total'):
                        st.progress(min(1.0, job.get('documents_completed', 0) / job['documents_total']))
                    if job['status'] == 'completed':
                        st.caption(f"{job['documents_indexed']} documents indexés")
                    if job.get('tracking_error'):
                        st.warning('Indexation enregistrée ; export de la trace indisponible.')
                except PermissionError:
                    st.caption(source['status'])
        progress_view()

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
