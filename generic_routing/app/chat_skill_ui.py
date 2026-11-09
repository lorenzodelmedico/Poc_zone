"""Panneau Streamlit ; le contexte et les travaux restent dans le backend."""
from app.skills import get_skill_state, set_document_search, select_source
from app.source_jobs import enqueue_source_sync, get_source_job


def document_skill_view(api, user_id, cid, *, index_existing, allowed_roots, export_job):
    import streamlit as st
    state = get_skill_state(api, user_id, cid)
    with st.popover('Recherche documentaire', icon=':material/folder_open:'):
        enabled = st.toggle('Activer la recherche documentaire', value=state['document_search'],
                            key=f'document_skill_{cid}_{state["revision"]}')
        set_document_search(api, user_id, cid, enabled)
        st.caption('Sans source sélectionnée, la recherche utilise le périmètre autorisé déjà indexé.')
        with st.form(f'add_source_{cid}', clear_on_submit=True):
            url = st.text_input('URL du site, de la bibliothèque ou du dossier SharePoint')
            submitted = st.form_submit_button('Ajouter et indexer')
        if submitted:
            try:
                enqueue_source_sync(api, user_id, cid, url, index_existing=index_existing,
                                    allowed_roots=allowed_roots, export_job=export_job)
                # La création d'une source active le skill dans le backend.
                st.rerun()
            except Exception as exc:
                st.error(f'Ajout de la source impossible : {type(exc).__name__}')
        state = get_skill_state(api, user_id, cid)
        for source in state['sources']:
            selected = st.checkbox(source['url'], value=source['selected'],
                                   key=f'source_{cid}_{source["source_id"]}')
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
                        st.caption(f'{job["documents_indexed"]} documents indexés')
                    if job.get('tracking_error'):
                        st.warning('Indexation enregistrée ; export de la trace indisponible.')
                except PermissionError:
                    st.caption(source['status'])
        progress_view()
