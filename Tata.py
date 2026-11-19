import sys
import asyncio
import atexit
import json
import re
import traceback
import streamlit as st
import warnings

from urllib3.exceptions import InsecureRequestWarning
from app.config import load_env, Settings
from app.store import Store, js
from app.clients import API, Vectors
from app.data_api import DataAPI, clean_api_response
from app.security import Access
from app.domain import THEMES
from app.agent import ask, execute, verify_recorded
from app.evidence import source_link, document_catalog
from app.errors import error_details
from app.tracking import export_run, source_job_trace
from app.sharepoint_client import SharePointClient
from app.context_cache import get_context, invalidate_context
from app.routing import warm_router
from app.sources import get_skill_state, set_document_search, set_verification, select_source
from app.sync import enqueue_source_sync, get_source_job, Synchronizer

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

load_env()
s, store = Settings(), Store()
st.set_page_config(page_title='Assistant RH',layout='wide')


@st.cache_resource
def service_client():
    client = API(Settings())
    atexit.register(client.close)
    return client


def problem(exc):
    traceback.print_exception(exc)
    
    # Gestion spécifique des erreurs de protocole réseau (RemoteProtocolError)
    # qui peuvent arriver de manière aléatoire.
    exc_type = type(exc).__name__
    if 'RemoteProtocolError' in exc_type or 'httpx.RemoteProtocolError' in str(exc):
        st.error('Le serveur a interrompu la connexion prématurément. Veuillez réessayer.')
        with st.expander('Détails techniques'):
            st.code(traceback.format_exc(), language=None)
        return

    st.error('Opération interrompue.')
    for detail in error_details(exc):
        st.code(detail,language=None)
    with st.expander('Traceback complet'):
        st.code(traceback.format_exc(),language=None)


def user_selection_popup(data_api):

    st.markdown('### Veuillez sélectionner votre profil')
    try:
        with st.spinner('Chargement des utilisateurs...'):
            all_users = data_api.get('HR_EMPLOYEES_URL', {})
        
        if not all_users:
            st.warning('Aucun utilisateur trouvé.')
        else:
            # Recherche textuelle
            search = st.text_input('Rechercher un nom...', key='user_search')
            
            filtered_users = all_users
            if search:
                search = search.lower()
                filtered_users = [
                    u for u in all_users 
                    if search in ((u.get('legal_name_first_name') or '').lower() + ' ' + (u.get('legal_name_last_name') or '').lower())
                ]

            if not filtered_users:
                st.info('Aucun résultat pour cette recherche.')
            else:
                # Formatage pour l'affichage
                user_options = [
                    f"{u.get('legal_name_first_name', '')} {u.get('legal_name_last_name', '')} ({u.get('codenumber', 'N/A')})"
                    for u in filtered_users
                ]
                
                selected_label = st.selectbox('Utilisateurs', user_options)
                
                if st.button('Valider la sélection'):
                    idx = user_options.index(selected_label)
                    user_id = filtered_users[idx].get('codenumber')
                    
                    if user_id:
                        st.session_state.selected_user_id = user_id
                        st.session_state.is_guest = False
                        st.rerun()
                    else:
                        st.error('Identifiant utilisateur manquant.')

        st.divider()
        if st.button('Continuer en tant qu\'invité'):
            st.session_state.selected_user_id = None
            st.session_state.is_guest = True
            st.rerun()

    except Exception as exc:
        problem(exc)


def profile_card_view(profile_data):
    if not profile_data:
        return
    
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### {profile_data.get('legal_name_first_name', '')} {profile_data.get('legal_name_last_name', '')}")
        with col2:
            natco = profile_data.get('natco', 'N/A')
            st.markdown(f"**Natco :** `{natco}`")
        
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.caption('Date de naissance')
            st.text(profile_data.get('dateofbirth', 'N/A'))
        with c2:
            st.caption('Poste')
            st.text(f"{profile_data.get('position_title', 'N/A')} ({profile_data.get('position', 'N/A')})")



def render_answer(text):
    """Rendu de la réponse avec gestion des traductions <orig lang='...' text='...'>"""
    pattern = r'(.*?)(<orig\s+lang="([^"]+)"\s+text="([^"]+)">)'
    
    # On utilise une approche simplifiée : on remplace les tags par des marqueurs 
    # ou on traite le texte séquentiellement.
    # Streamlit ne supporte pas les widgets inline dans st.markdown.
    # On va donc utiliser st.markdown pour le texte et st.popover pour l'info.
    
    # On cherche tous les matches
    matches = list(re.finditer(r'<orig\s+lang="([^"]+)"\s+text="([^"]+)">', text))
    if not matches:
        st.markdown(text)
        return

    last_pos = 0
    for match in matches:
        # Texte avant le tag
        before = text[last_pos:match.start()]
        if before:
            st.markdown(before, unsafe_allow_html=False)
        
        lang = match.group(1)
        original = match.group(2)
        
        # On affiche l'icône d'info via un popover
        with st.popover("ℹ️"):
            st.caption(f"**Langue originale : {lang}**")
            st.text(original)
        
        last_pos = match.end()
    
    # Texte final
    after = text[last_pos:]
    if after:
        st.markdown(after, unsafe_allow_html=False)

def source_view(evidence):

    seen, items = set(), []
    for item in evidence:
        if item['doc_id'] not in seen:
            seen.add(item['doc_id'])
            items.append(item)
    if items:
        st.markdown('**Sources**')
    for item in items:
        current = store.document(item['doc_id'])
        url = source_link(current or item)
        title = re.sub(r'([\\`*_[\]<>!])',r'\\\1',item['title'])
        if url:
            st.link_button(title,url)
        else:
            st.text(item['title'])


def feedback_view(uid, rid, key=''):
    saved = store.feedback(uid,rid)
    with st.popover('Évaluer la réponse'):
        with st.form('feedback_'+key+rid):
            index = (0 if saved['helpful'] else 1) if saved else None
            verdict = st.radio('Résultat', ['Satisfaisant','À corriger'],index=index,horizontal=True)
            options = ['','Information fausse','Information manquante','Mauvaise source','Lien inutilisable','Autre']
            reason = st.selectbox('Motif',options,index=options.index(saved['reason']) if saved and saved['reason'] in options else 0)
            comment = st.text_area('Commentaire / correction',value=saved['comment'] if saved else '')
            submitted = st.form_submit_button('Enregistrer')
        if submitted:
            if verdict is None:
                st.warning('Un résultat doit être sélectionné.')
            else:
                store.save_feedback(uid,rid,verdict=='Satisfaisant',reason,comment)
                warning = export_run(store,uid,rid)
                if warning:
                    st.warning('Retour enregistré localement. MLflow : '+warning)
                else:
                    st.success('Retour enregistré.')


@st.dialog('Reprendre un sujet')
def suggestions_popup(items):
    for item in items[:3]:
        st.markdown('**'+item['title']+'**')
        st.caption(THEMES[item['theme_key']][1])
        if st.button('Actualiser — '+item['title'],key='resume_'+item['theme_key']):
            st.session_state.cid = item['conversation_id']
            st.session_state.pending = ('Rechercher les informations actuelles pour cette demande antérieure : '
                +item['last_query']+'. Indiquer les modifications documentées depuis '+str(item['last_used'])
                +', sans supposer que des nouveautés existent.')
            st.rerun()
    if st.button('Fermer'):
        st.rerun()

def document_skill_view(api, user_id, cid, *, index_existing, allowed_roots, export_job):
    state = get_skill_state(api, user_id, cid)
    with st.popover('Recherche documentaire', icon=':material/folder_open:'):
        enabled = st.toggle('Activer la recherche documentaire', value=state['document_search'], key=f"document_skill_{cid}_{state['revision']}")
        set_document_search(api, user_id, cid, enabled)
        
        verify = st.toggle('Vérifier la fidélité', value=state.get('verification', False), key=f"verify_skill_{cid}_{state['revision']}")
        set_verification(api, user_id, cid, verify)
        
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
                with st.expander('Détails de l\'erreur'):
                    st.code(traceback.format_exc())
        state = get_skill_state(api, user_id, cid)
        for source in state['sources']:
            selected = st.checkbox(source['url'], value=source['selected'], key=f"source_{cid}_{source['source_id']}")
            select_source(api, user_id, cid, source['source_id'], selected)

        @st.fragment(run_every='1s')
        def progress_view():
            state = get_skill_state(api, user_id, cid)
            for source in state['sources']:
                try:
                    job = get_source_job(api, user_id, cid, source['job_id'])
                    if job['status'] == 'running':
                        st.caption(job['progress'])
                        if job.get('documents_total'):
                            st.progress(min(1.0, job.get('documents_completed', 0) / job['documents_total']))
                    elif job['status'] == 'completed':
                        st.success(f"✓ {job['documents_indexed']} documents indexés")
                    elif job['status'] == 'failed':
                        st.error(f"✗ {job.get('error', 'Erreur inconnue')}")
                    elif job['status'] == 'queued':
                        st.caption("⏳ En attente...")
                except PermissionError:
                    st.caption(source['status'])
        progress_view()

def chat_view(uid,client):
    # --- Gestion de la sélection utilisateur ---
    data_api = DataAPI(client)
    
    # On force l'utilisation de l'ID par défaut si configuré dans Settings
    # pour éviter la popup de sélection et l'appel API massif.
    if 'selected_user_id' not in st.session_state and 'is_guest' not in st.session_state:
        st.session_state.selected_user_id = uid
        st.session_state.is_guest = False

    st.title('Assistant RH')
    access = Access(s, store, client)
    if not st.session_state.get('is_guest', False):
        get_context(client, uid, lambda: access.user_context(uid))
    with st.sidebar:
        if st.button('Nouvelle discussion'):
            st.session_state.cid = store.new_conversation(uid)
            st.rerun()
        with st.expander('Historique'):
            for c in store.conversations(uid):
                if st.button(c['title'],key=c['conversation_id']):
                    st.session_state.cid=c['conversation_id']
                    st.rerun()
        with st.expander('Mémoire'):
            st.caption('Les traces d’évaluation et MLflow sont conservées séparément.')
            confirm=st.checkbox('Confirmer l’effacement des conversations et thèmes')
            if st.button('Effacer les échanges',disabled=not confirm):
                store.forget(uid)
                st.session_state.cid=store.new_conversation(uid)
                st.rerun()
    if st.session_state.pop('offer_resume',False):
        items=access.suggestions(uid)
        if items:
            suggestions_popup(items)
    for message in access.visible_messages(uid,st.session_state.cid):
        with st.chat_message(message['role']):
            if message['role']=='user':
                st.text(message['content'])
            else:
                render_answer(message['content'])
                source_view(message['evidence'])
                run=store.run_for_message(uid,message['message_id'])
                if run:
                    feedback_view(uid,run['run_id'],'chat_')
                    if run['tracking_error']:
                        st.warning('Réponse enregistrée localement. MLflow : '+run['tracking_error'])
    synchronizer = Synchronizer(s, store, client, Vectors(s))
    document_skill_view(
        client, uid, st.session_state.cid,
        index_existing=synchronizer.index_from_chat,
        allowed_roots=s.sharepoint_allowed_roots,
        export_job=lambda job: source_job_trace(mlflow, job, experiment_id),
    )
    submitted = st.chat_input('Question ou précision')
    question=st.session_state.pop('pending',None) or submitted
    if question:
        if len(question)>8000:
            st.error('Question supérieure à 8 000 caractères.')
        else:
            with st.chat_message('user'):
                st.text(question)
            try:
                with st.status('Traitement de la demande', expanded=True) as status_box:
                    def progress(label):
                        status_box.update(label=label)
                        status_box.write(label)
                    
                    # On lance l'exécution de l'agent
                    result = asyncio.run(ask(
                        s, store, client, uid, st.session_state.cid, question,
                        profile_enabled=not st.session_state.get('is_guest', False),
                        on_progress=progress,
                    ))
                    status_box.update(label='Traitement terminé', state='complete', expanded=False)
            except Exception as exc:
                problem(exc)
            else:
                st.rerun()


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


def run_view(uid,run,*,detailed=True,key=''):
    result=run['result']
    active={d['doc_id'] for d in store.active_docs()}
    if any(d['doc_id'] not in active for d in result.get('evidence',[])):
        st.warning('Une source de cet essai a été retirée du périmètre actif.')
        return
    st.caption(run['mode']+' · '+run['prompt_variant']+' · '+run['status']
               +' · '+f"{run['duration'] or 0:.2f} s")
    st.text(run['question'])
    if result.get('answer'):
        render_answer(result['answer'])
        source_view(result.get('sources',[]))
    if result.get('error'):
        st.error(result['error'])
    feedback_view(uid,run['run_id'],key)
    if not detailed:
        return
    with st.expander('Contexte et contrôles'):
        st.json(result.get('checks',{}))
        for item in result.get('evidence',[]):
            st.markdown('**['+str(item['citation'])+'] '+item['title']+'**')
            st.text(item['text'])
        st.caption('Contenu effectivement fourni à ce tour ; aucune réponse attendue injectée.')
    if st.button('Vérifier la fidélité',key='verify_'+run['run_id'],
                 disabled=run['status'] not in {'completed','needs_review'}):
        try:
            with st.spinner('Vérification des affirmations…'):
                asyncio.run(verify_recorded(s,store,uid,run['run_id']))
            st.rerun()
        except Exception as exc:
            problem(exc)
    verification=result.get('verification')
    if verification:
        with st.expander('Vérification',expanded=True):
            show_review(verification)
    with st.expander('Trace de l’essai'):
        st.write('Identifiant : '+run['run_id'])
        st.json(result.get('steps',[]))
        if run['trace_id']:
            st.success("Enregistré automatiquement dans MLFLow.")
            st.write('Trace MLflow : '+run['trace_id'])
        if run['tracking_error']:
            st.warning("Echec de l'enregistrement automatique dans MLflow")
            st.code(run['tracking_error'], language=None)
        if st.button("Ressayer l'enregistrement dans MLflow",key='track_'+run['run_id']):
            warning=export_run(store,uid,run['run_id'])
            if warning:
                st.error(warning)
            else:
                st.rerun()
        st.download_button('Exporter l’essai JSON',js(run),file_name='essai_'+run['run_id']+'.json',
                           mime='application/json',key='download_'+run['run_id'])


def sharepoint_browser_view(uid, client):
    st.title('📁 Explorateur SharePoint')
    
    # Configuration de la racine du site
    SITE_ROOT = '/sites/a457'
    
    # Initialize state
    if 'sp_current_path' not in st.session_state:
        st.session_state.sp_current_path = SITE_ROOT
    if 'sp_selected_items' not in st.session_state:
        st.session_state.sp_selected_items = set()

    sp_client = SharePointClient(api_client=client)
    
    # Set site context LIGHTLY without calling the heavy resolver
    # We extract the site root from the current path
    path = st.session_state.sp_current_path
    parts = path.strip('/').split('/')
    site_root = "/"
    if len(parts) >= 2 and parts[0] in ('sites', 'teams'):
        site_root = f"/{parts[0]}/{parts[1]}"
    sp_client.set_site_context(site_root)
    
    # Connection Status in sidebar
    try:
        sp_client.get_folder_contents(st.session_state.sp_current_path)
        st.sidebar.success('SharePoint: Connecté')
    except Exception as e:
        st.sidebar.error(f'SharePoint: Déconnecté ({type(e).__name__})')

    # --- Navigation Bar ---
    nav_col1, nav_col2 = st.columns([0.1, 0.9])
    
    # Bouton Retour
    with nav_col1:
        if st.session_state.sp_current_path != SITE_ROOT:
            if st.button('⬅️', help='Remonter d\'un niveau'):
                # Calcul du chemin parent
                parts = st.session_state.sp_current_path.rstrip('/').split('/')
                parent_path = '/'.join(parts[:-1])
                if not parent_path.startswith(SITE_ROOT):
                    parent_path = SITE_ROOT
                st.session_state.sp_current_path = parent_path
                st.rerun()
        else:
            st.write('') # Spacer

    # Fil d'Ariane (Breadcrumbs)
    with nav_col2:
        path_parts = st.session_state.sp_current_path.split('/')
        filtered_parts = [p for p in path_parts if p]
        
        current_acc = ""
        part_idx = 0
        # On utilise des colonnes pour aligner les segments du fil d'Ariane
        bc_cols = st.columns(len(filtered_parts) * 2) 
        
        for i, part in enumerate(path_parts):
            if not part: continue
            current_acc += f"/{part}"
            
            if bc_cols[part_idx * 2].button(part, key=f"bc_{part_idx}"):
                if current_acc.startswith(SITE_ROOT):
                    st.session_state.sp_current_path = current_acc
                    st.rerun()
            
            if part_idx < len(filtered_parts) - 1:
                bc_cols[part_idx * 2 + 1].markdown(" › ")
            
            part_idx += 1

    st.divider()

    # --- File Browser ---
    try:
        items = sp_client.get_folder_contents(st.session_state.sp_current_path)
        
        folders = [i for i in items if i['type'] == 'folder']
        files = [i for i in items if i['type'] == 'file']
        
        if folders:
            st.markdown('#### 📁 Dossiers')
            for folder in folders:
                col1, col2 = st.columns([0.05, 0.95])
                is_selected = folder['relative_url'] in st.session_state.sp_selected_items
                if col1.checkbox('Sélectionner', value=is_selected, label_visibility="collapsed", key=f"sel_{folder['id']}"):
                    st.session_state.sp_selected_items.add(folder['relative_url'])
                else:
                    st.session_state.sp_selected_items.discard(folder['relative_url'])
                if col2.button(f"📁 {folder['name']}", key=f"btn_{folder['id']}", use_container_width=True):
                    st.session_state.sp_current_path = folder['relative_url']
                    st.rerun()
        
        st.markdown('---')
        
        if files:
            st.markdown('#### 📄 Fichiers')
            for file in files:
                col1, col2 = st.columns([0.05, 0.95])
                is_selected = file['relative_url'] in st.session_state.sp_selected_items
                if col1.checkbox('Sélectionner', value=is_selected, label_visibility="collapsed", key=f"sel_{file['id']}"):
                    st.session_state.sp_selected_items.add(file['relative_url'])
                else:
                    st.session_state.sp_selected_items.discard(file['relative_url'])
                col2.text(f"📄 {file['name']}")
        
        if not folders and not files:
            st.info('Ce dossier est vide.')
                
    except Exception as e:
        st.error(f"Erreur de chargement du dossier : {e}")

    st.divider()
    
    # --- Ingestion Queue ---
    st.subheader('📥 File d\'attente d\'indexation')
    if st.session_state.sp_selected_items:
        selected_list = list(st.session_state.sp_selected_items)
        for item_url in selected_list:
            st.caption(f"✓ {item_url}")
        
        # --- Permission Refresh Warning Logic ---
        if st.session_state.get('pending_indexing'):
            try:
                
                sync = Synchronizer(s, store, client, Vectors(s))
                
                # Check if content has changed for any of the selected items
                all_unchanged = True
                for url in selected_list:
                    doc = store.document(url)
                    if not doc:
                        all_unchanged = False
                        break
                
                if all_unchanged:
                    st.warning('⚠️ Le contenu des documents n\'a pas changé depuis la dernière indexation. Si vous souhaitez continuer, seule l\'autorisation sera mise à jour.')
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button('Oui, mettre à jour les autorisations', type='primary'):
                            st.session_state.pending_indexing = False
                            st.session_state.confirm_refresh = True
                            st.rerun()
                    with col_confirm2:
                        if st.button('Annuler'):
                            st.session_state.pending_indexing = False
                            st.rerun()
                else:
                    st.session_state.pending_indexing = False
                    st.session_state.confirm_refresh = True
                    st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la vérification : {e}")
                st.session_state.pending_indexing = False

        if st.session_state.get('confirm_refresh'):
            try:
                with st.status('Indexation en cours...', expanded=True) as status:
                    
                    sync = Synchronizer(s, store, client, Vectors(s))
                    report = sync.once(selected_urls=list(st.session_state.sp_selected_items), extra_user_ids=[uid], force=True)
                    
                    st.write(f"✅ Terminé : {report['changed']} modifiés, {report['unchanged']} inchangés.")
                    if report['failures']:
                        st.warning(f"⚠️ {len(report['failures'])} erreurs rencontrées.")
                    
                    status.update(label='Terminé', state='complete')
                st.session_state.confirm_refresh = False
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de l'indexation : {e}")
                st.session_state.confirm_refresh = False

        if not st.session_state.get('pending_indexing') and not st.session_state.get('confirm_refresh'):
            c1, c2 = st.columns(2)
            with c1:
                if st.button('🗑️ Vider la sélection', use_container_width=True):
                    st.session_state.sp_selected_items.clear()
                    st.rerun()
            with c2:
                if st.button('🚀 Lancer l\'indexation', type='primary', use_container_width=True):
                    st.session_state.pending_indexing = True
                    st.rerun()
    else:
        st.info('Aucun élément sélectionné pour l\'indexation.')

    sp_client.close()

def evaluation_view(uid,client):
    st.title('Évaluation')
    st.caption('Essais sur la documentation disponible. Aucun jeu de réponses attendu requis.')
    pending = st.session_state.pop('pending_eval',None)
    if pending:
        st.session_state.eval_question = pending['question']
        st.session_state.eval_mode = 'Documents choisis' if pending['mode']=='selected' else 'Parcours complet'
        st.session_state.eval_prompt = 'Actuel' if pending['prompt_variant']=='actuel' else 'Renforcé'
        st.session_state.eval_docs = pending['selected'].get('document_ids',[])
        for did,items in pending['selected'].get('sections',{}).items():
            st.session_state['sections_'+did] = items
    catalog=document_catalog(s,store,client)
    by_id={item['doc_id']:item for item in catalog}
    if 'eval_docs' in st.session_state:
        st.session_state.eval_docs=[d for d in st.session_state.eval_docs if d in by_id]
    mode=st.radio('Mode',['Parcours complet','Documents choisis'],horizontal=True,key='eval_mode')
    sections, selected={},[]
    if mode=='Documents choisis':
        st.caption('Le contenu sélectionné est lu directement : ni recherche vectorielle ni reranking. '
                   'La réponse attendue n’est pas fournie.')
        selected=st.multiselect('Documents',list(by_id),format_func=lambda did:by_id[did]['title'],key='eval_docs')
        for did in selected:
            section_key='sections_'+did
            if section_key in st.session_state:
                st.session_state[section_key]=[v for v in st.session_state[section_key] if v in by_id[did]['sections']]
            with st.expander(by_id[did]['title']+' — sections facultatives'):
                sections[did]=st.multiselect('Sections ; vide = document entier',by_id[did]['sections'],
                    format_func=lambda label:label or 'Sans titre',key='sections_'+did)
    else:
        st.caption('Reformulation, recherche et reranking habituels, puis génération. '
                   'Le profil RH et la mémoire des conversations ne sont pas chargés dans cet espace.')
    variant=st.radio('Prompt',['Actuel','Renforcé'],horizontal=True,key='eval_prompt')
    with st.form('evaluation'):
        question=st.text_area('Question',key='eval_question')
        submit=st.form_submit_button('Lancer l’essai')
    if submit:
        try:
            if mode=='Documents choisis' and not selected:
                raise ValueError('Au moins un document doit être sélectionné.')
            with st.spinner('Exécution de l’essai…'):
                result=asyncio.run(execute(s,store,client,uid,question,
                    mode='selected' if mode=='Documents choisis' else 'full',
                    prompt_variant='actuel' if variant=='Actuel' else 'renforce',
                    document_ids=selected,sections=sections))
            st.session_state.latest_run=result['run_id']
        except Exception as exc:
            problem(exc)
    runs=store.answer_runs(uid,'evaluation')
    if not runs:
        st.info('Aucun essai enregistré.')
        return
    by_run={r['run_id']:r for r in runs}
    rows=[]
    for r in runs:
        fb=store.feedback(uid,r['run_id'])
        rows.append({'Date':r['started_at'][:19],'Question':r['question'],'Mode':r['mode'],
            'Prompt':r['prompt_variant'],'Statut':r['status'],'Durée (s)':round(r['duration'] or 0,2),
            'Retour':('Satisfaisant' if fb['helpful'] else 'À corriger') if fb else '',
            'Vérification':r['result'].get('verification',{}).get('status','')})
    st.subheader('Essais enregistrés')
    st.dataframe(rows,width=True,hide_index=True)
    label=lambda rid:by_run[rid]['started_at'][:19]+' · '+by_run[rid]['mode']+' · '+by_run[rid]['prompt_variant']+' · '+by_run[rid]['question'][:100]
    chosen=st.selectbox('Essai affiché',list(by_run),format_func=label)
    if st.button('Reprendre cet essai'):
        st.session_state.pending_eval=by_run[chosen]
        st.rerun()
    run_view(uid,by_run[chosen],key='detail_')
    comparison=st.multiselect('Comparer deux essais',list(by_run),max_selections=2,format_func=label)
    if len(comparison)==2:
        left,right=[by_run[rid] for rid in comparison]
        if left['question']!=right['question']:
            st.warning('Les questions diffèrent ; comparaison non contrôlée.')
        if left['result'].get('model')!=right['result'].get('model'):
            st.warning('Les modèles diffèrent.')
        left_docs={d['doc_id']:d['raw_hash'] for d in left['result'].get('evidence',[])}
        right_docs={d['doc_id']:d['raw_hash'] for d in right['result'].get('evidence',[])}
        if any(left_docs[d]!=right_docs[d] for d in left_docs.keys() & right_docs.keys()):
            st.warning('Une source a changé entre ces essais.')
        if left['prompt_variant']==right['prompt_variant'] and left['mode']==right['mode']:
            st.caption('Même configuration : comparaison de répétabilité.')
        for column,r in zip(st.columns(2),(left,right)):
            with column:
                run_view(uid,r,detailed=False,key='compare_')


try:
    uid=s.user_id
    store.init(uid)
    client=service_client()
    if 'user_id' not in st.session_state:
        st.session_state.user_id=uid
        st.session_state.cid=store.new_conversation(uid)
        st.session_state.offer_resume=True
    elif st.session_state.user_id!=uid:
        st.session_state.clear()
        st.rerun()
    with st.sidebar:
        st.caption('POC local · droits documentaires réels non raccordés')
        view=st.radio('Espace',['Chat','Évaluation','SharePoint'], index=0)
        st.caption('Utilisateur : '+uid)
        st.link_button('MLflow local','http://127.0.0.1:5000')
    if view=='Chat':
        chat_view(uid,client)
    elif view=='Évaluation':
        evaluation_view(uid,client)
    elif view=='SharePoint':
        sharepoint_browser_view(uid, client)
except Exception as exc:
    problem(exc)





























----------


C'est noté. Je rectifie le tir : l'objectif est une transposition visuelle et ergonomique (le "Look & Feel" et l'agencement) et non une migration de la logique métier ou du moteur de rendu Angular.

On garde la logique Streamlit actuelle, mais on change la structure de l'interface pour qu'elle ressemble à l'expérience utilisateur d'Angular.

1. Analyse Visuelle (Source Angular)
L'interface Angular n'est pas un simple chat, c'est un Dashboard de rédaction organisé en trois zones :

Zone Gauche (Sidebar) : Navigation entre les sessions, bouton "Nouveau" et sélecteur de langue.
Zone Centrale (Main) :
État Initial : Écran d'accueil avec cartes de choix de mode.
État Actif : Flux de messages $\rightarrow$ Boutons d'actions rapides $\rightarrow$ Zone de saisie.
Zone Droite (Draft Pane) : Panneau dédié à l'affichage du document en cours de rédaction (le brouillon), avec versioning et bouton de copie.
2. Plan Technique de Refonte UI (Streamlit)
A. Structure de la Page (Layout)
Remplacer la vue linéaire par un layout multi-colonnes :

st.sidebar :
Titre de l'application.
Bouton "Nouvelle conversation".
Liste des sessions (historique).
Sélecteur de langue (en bas de sidebar).
st.columns([3, 1]) (ou ratio similaire) :
Colonne 1 (Chat) : Le flux de conversation et la saisie.
Colonne 2 (Document) : Le panneau de visualisation du brouillon.
B. Détail des composants visuels à implémenter
| Élément Visuel | Implémentation Streamlit | Objectif UX | | :--- | :--- | :--- | | Cartes de Mode | st.columns + st.button avec icônes | Remplacer le menu déroulant ou le texte simple par des "cartes" cliquables à l'accueil. | | Boutons d'Actions | st.columns (petites colonnes) ou st.button successifs | Afficher les suggestions de l'assistant sous forme de boutons horizontaux plutôt que de texte. | | Panneau Brouillon | st.container avec bordure ou st.expander dans la colonne de droite | Isoler le texte généré du flux de chat pour permettre une lecture stable pendant que le chat continue. | | Indicateur de Version | st.caption au-dessus du brouillon | Afficher "v1", "v2", etc., pour marquer l'évolution du document. | | Bulles de Chat | Utilisation de st.chat_message | Conserver le standard Streamlit mais s'assurer de la distinction visuelle Utilisateur/Assistant. |

C. Modifications dans app/ui.py
1. À supprimer :

L'affichage séquentiel simple où tout est empilé verticalement.
L'absence de zone dédiée au document (si le draft est actuellement injecté comme un message de chat).
2. À ajouter/modifier :

Initialisation du Layout : Encapsuler chat_view dans une structure st.sidebar et st.columns.
Logique d'affichage conditionnel :
SI aucune session active $\rightarrow$ Afficher les Cartes de Mode (Accueil).
SINON $\rightarrow$ Afficher le Flux de Chat (Gauche) et le Brouillon (Droite).
Zone de saisie : Maintenir st.chat_input en bas de page.
3. Synthèse du flux visuel cible
Accueil $\rightarrow$ [ Carte : Créer de zéro ] [ Carte : Compléter existant ]

Session Active $\rightarrow$

Sidebar : [ + Nouveau ] $\rightarrow$ [ Liste des anciens jobs ] $\rightarrow$ [ Langue $\vee$ ]
Centre :
[ Bulles de messages ]
[ Bouton Action 1 ] [ Bouton Action 2 ]
[ Zone de saisie ]
Droite :
### Brouillon (vX)
[ Zone de texte du document ]
[ Bouton Copier ]
Sources visuelles justifiant ce plan :

frontend/src/app/components/job-history-chat/job-history-chat.component.html : lignes 2-35 (Sidebar), 49-57 (Accueil/Cartes), 81-90 (Draft Pane).



<div class="app-shell" [class.draft-expanded]="draftExpanded && draftOpen">
  <aside class="sidebar" [class.sidebar-hidden]="!sidebarOpen">
    <div class="brand"><div class="brand-icon">JWA</div><div><strong>Job Writing Assistant</strong><span></span></div></div>
    <div class="workflow-buttons">
      <button class="new-button" (click)="showWelcome()" [disabled]="loading">
        <span aria-hidden="true">＋</span> {{ t('new') }}
      </button>
    </div>
    <div class="section-label">{{ t('history') }}</div>
    <div class="conversation-list">
      <div *ngFor="let item of sidebarItems" class="thread-row"
        [class.selected]="(item.assistant_job_id && item.assistant_job_id === activeWorkId) || item.key === ('session:' + activeId)">
        <button type="button" class="thread" (click)="openItem(item)"
          [disabled]="loading || !!deletingWorkId">
          <span class="thread-icon">▤</span>
          <span class="thread-content"><span class="thread-name">{{ item.job_title }}</span>
            <span class="thread-status">{{ statusLabel(item.status) }}</span></span>
        </button>
        <div class="thread-more" *ngIf="item.assistant_job_id && item.can_resume">
          <button type="button" class="thread-menu-button" (click)="toggleWorkMenu(item.assistant_job_id!, $event)"
            [attr.aria-label]="t('delete') + ' ' + item.job_title"
            [attr.aria-expanded]="openWorkMenuId === item.assistant_job_id"
            [disabled]="loading || !!deletingWorkId" title="Options">⋯</button>
          <div *ngIf="openWorkMenuId === item.assistant_job_id" class="thread-menu" role="menu">
            <button type="button" role="menuitem" class="thread-delete"
              (click)="deleteWork(item, $event)" [disabled]="loading || !!deletingWorkId">
              {{ t('delete') }}
            </button>
          </div>
        </div>
      </div>
      <p class="empty-history" *ngIf="sidebarItems.length === 0">{{ t('empty') }}</p>
    </div>
    <div class="sidebar-footer"><span class="status-dot"></span>{{ t('local') }}</div>
  </aside>

  <main class="main">
    <header class="topbar">
      <div class="topbar-left"><button class="icon-button" (click)="sidebarOpen = !sidebarOpen" aria-label="Toggle sidebar">☰</button><span class="heading">Job Writing Assistant</span></div>
      <div class="topbar-right">
        <label class="language-label" for="lang">{{ t('language') }}</label>
        <select id="lang" class="language-select" [ngModel]="language" (ngModelChange)="changeLanguage($event)" [disabled]="loading">
          <option value="fr">Français</option><option value="en">English</option>
        </select>
        <button *ngIf="state?.draft_text && !draftOpen" class="small-button" (click)="draftOpen = true">{{ t('open') }}</button>
      </div>
    </header>
    <div *ngIf="errorMessage" class="api-error" role="alert">{{ errorMessage }}</div>
    <section class="content" *ngIf="!activeThread">
      <div class="welcome"><div class="welcome-icon">✦</div><h1>{{ t('welcome') }}</h1>
        <p>{{ t('description') }}</p>
        <div class="mode-cards">
          <button class="mode-card" (click)="newConversation('create_from_scratch')" [disabled]="loading"><span class="mode-icon">＋</span><strong>{{ t('scratch') }}</strong><span>{{ t('scratchInfo') }}</span></button>
          <button class="mode-card" (click)="newConversation('complete_existing')" [disabled]="loading"><span class="mode-icon">▤</span><strong>{{ t('existing') }}</strong><span>{{ t('existingInfo') }}</span></button>
        </div>
      </div>
    </section>
    <section class="conversation" #messageScroll (scroll)="onScroll($event)" *ngIf="activeThread">
      <div class="conversation-meta"><span class="pill">{{ modeLabel }}</span><span>{{ statusLabel(state?.finalized ? 'finalized' : 'in_progress') }}</span></div>
      <div class="message-list" role="log" aria-live="polite">
        <div *ngFor="let message of messages" class="message" [class.message-user]="message.role === 'user'">
          <div class="avatar" *ngIf="message.role === 'assistant'">✦</div><div class="message-text">{{ message.content }}</div>
        </div>
      </div>
      <!-- Generic profile and candidate jobs are presented in the conversation only. -->
      <div class="action-row" *ngIf="actions.length">
        <button *ngFor="let item of actions" class="action-button" [disabled]="loading" (click)="runAction(item.action)">{{ item.label }}</button>
      </div>
      <div *ngIf="loading" class="working" role="status" aria-live="polite">
        <span class="typing-dots" aria-hidden="true"><i></i><i></i><i></i></span>{{ t('thinking') }}…
      </div>
    </section>
    <div class="composer-wrap" *ngIf="activeThread">
      <div class="composer"><textarea [(ngModel)]="userInput" (keydown)="onComposerKeydown($event)"
        [placeholder]="t('placeholder')" rows="2" [attr.aria-label]="t('placeholder')" [disabled]="loading"></textarea>
        <button (click)="sendMessage()" [disabled]="loading || !userInput.trim()" [attr.aria-label]="t('send')">➤</button></div>
      <div class="composer-hint">{{ t('hint') }}</div>
    </div>
  </main>

  <aside class="draft-pane" *ngIf="draftOpen && !!state?.draft_text" [class.expanded]="draftExpanded">
    <div class="draft-header"><strong>{{ t('draft') }} <span *ngIf="state?.draft_version">v{{ state?.draft_version }}</span></strong>
      <div class="draft-controls">
        <button class="icon-button" (click)="draftExpanded = !draftExpanded" [attr.aria-label]="t(draftExpanded ? 'collapse' : 'expand')" [title]="t(draftExpanded ? 'collapse' : 'expand')">{{ draftExpanded ? '↙' : '⤢' }}</button>
        <button class="icon-button" (click)="draftOpen = false; draftExpanded = false" [attr.aria-label]="t('close')" [title]="t('close')">✕</button>
      </div>
    </div>
    <div class="draft-body">{{ draft }}</div>
    <div class="draft-footer"><button class="copy-button" (click)="copyDraft()">{{ copied ? t('copied') : t('copy') }}</button></div>
  </aside>
</div>






-------------




:host { display:block; height:100vh; font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif; color:#1c2637; }
* { box-sizing:border-box; }
button, textarea { font:inherit; }
button { cursor:pointer; }
.app-shell { display:flex; height:100vh; min-height:500px; background:#fff; }
.sidebar { display:flex; flex-direction:column; flex:0 0 265px; padding:22px 14px 15px; background:#f5f7fa; border-right:1px solid #e5e9ef; transition:flex-basis .2s,padding .2s; overflow:hidden; }
.sidebar-hidden { flex-basis:0; padding-left:0; padding-right:0; border:0; }
.brand { display:flex; align-items:center; gap:11px; padding:3px 9px 26px; white-space:nowrap; }
.brand-icon { display:grid; place-items:center; flex:0 0 36px; width:36px; height:36px; box-sizing:border-box; padding:0 2px; border-radius:10px; background:#233e69; color:white; font-weight:800; font-size:12px; letter-spacing:-0.4px; line-height:1; white-space:nowrap; }
.brand strong,.brand span { display:block; }
.brand strong { font-size:15px; }
.brand span { font-size:11px; color:#7c8595; margin-top:2px; }
.new-button { background:#243f69; color:#fff; border:0; border-radius:10px; padding:12px; text-align:left; font-size:13px; font-weight:650; white-space:nowrap; }
.new-button span { font-size:19px; margin-right:8px; vertical-align:-1px; }
.section-label { font-size:10px; font-weight:750; color:#98a1ae; letter-spacing:1.3px; margin:31px 10px 12px; }
.conversation-list { flex:1; overflow:auto; min-width:0; }
.thread { width:100%; display:flex; align-items:center; gap:10px; padding:12px 10px; text-align:left; border:0; border-radius:9px; background:transparent; color:#4a5568; }
.thread.selected,.thread:hover { background:#e6ebf4; color:#243f69; }
.thread-icon { font-size:17px; }.thread-name { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px; }
.empty-history { color:#9aa2ad; font-size:12px; padding:5px 10px; }
.sidebar-footer { border-top:1px solid #e1e5eb; padding:18px 9px 3px; color:#566173; font-size:12px; white-space:nowrap; }
.sidebar-footer small { display:block; color:#a0a7b2; margin:5px 0 0 17px; font-size:10px; }
.status-dot { display:inline-block; width:8px; height:8px; margin-right:7px; border-radius:50%; background:#d9a548; }
.main { flex:1; min-width:0; display:flex; flex-direction:column; }
.topbar { height:67px; flex:none; border-bottom:1px solid #ecedf0; display:flex; align-items:center; justify-content:space-between; padding:0 30px 0 20px; }
.topbar-left { display:flex; align-items:center; gap:13px; }.heading { font-size:15px; font-weight:700; }
.icon-button { border:0; padding:7px 10px; border-radius:7px; background:transparent; color:#596579; font-size:18px; }.icon-button:hover { background:#f2f4f8; }
.environment { font-size:9px; font-weight:800; letter-spacing:1.1px; color:#8c9cb0; background:#f2f5f9; border-radius:6px; padding:7px 9px; }
.content { display:flex; flex:1; align-items:center; justify-content:center; padding:24px; }
.welcome { text-align:center; max-width:690px; }.welcome-icon { display:grid; place-items:center; width:53px; height:53px; margin:0 auto 20px; border-radius:16px; color:white; background:#243f69; font-size:27px; }
h1 { font-size:27px; letter-spacing:-.7px; margin:0 0 11px; } .welcome p { color:#7c8798; font-size:14px; line-height:1.6; margin:0 0 34px; }
.mode-cards { display:grid; grid-template-columns:1fr 1fr; gap:15px; }.mode-card { display:flex; flex-direction:column; gap:9px; text-align:left; border:1px solid #e4e9ef; border-radius:13px; background:#fff; padding:21px; min-height:145px; }.mode-card:hover { border-color:#8aa2c6; box-shadow:0 8px 24px #233e6910; }.mode-icon { color:#345783; font-size:23px; }.mode-card strong { font-size:14px; }.mode-card > span:last-child { font-size:12px; color:#8792a0; }
.conversation { flex:1; overflow-y:auto; width:100%; padding:28px max(30px,calc((100% - 780px)/2)) 24px; }.conversation-meta { display:flex; align-items:center; gap:12px; color:#9ba3ae; font-size:11px; border-bottom:1px solid #edf0f4; padding-bottom:20px; }.pill { background:#edf2f9; color:#395778; border-radius:30px; padding:6px 10px; font-size:11px; font-weight:700; }
.message-list { padding-top:27px; display:flex; flex-direction:column; gap:24px; }.message { display:flex; align-items:flex-start; gap:13px; line-height:1.65; font-size:14px; white-space:pre-wrap; }.avatar { width:30px; height:30px; border-radius:9px; background:#e8eef7; color:#314e77; flex:none; display:grid; place-items:center; }.message-text { padding-top:3px; max-width:100%; }.message-user { justify-content:flex-end; }.message-user .message-text { background:#f1f3f6; border-radius:14px; padding:12px 17px; max-width:82%; }
.composer-wrap { width:100%; padding:12px max(30px,calc((100% - 780px)/2)) 22px; }.composer { border:1px solid #dce2ea; display:flex; align-items:flex-end; gap:10px; border-radius:15px; padding:12px; box-shadow:0 3px 15px #263d6310; }.composer:focus-within { border-color:#90a5c4; }.composer textarea { resize:none; border:0; outline:0; width:100%; min-height:45px; max-height:160px; color:#283445; background:transparent; }.composer button { flex:none; border:0; border-radius:9px; width:34px; height:34px; background:#243f69; color:white; font-size:16px; }.composer button:disabled { opacity:.4; cursor:default; }.composer-hint { text-align:center; color:#a2aab5; font-size:10px; padding-top:12px; }
@media(max-width:720px){ .sidebar{flex-basis:205px;} .topbar{padding-right:14px;} .environment{display:none;} .mode-cards{grid-template-columns:1fr;} h1{font-size:23px;} .conversation{padding-left:20px;padding-right:20px;} .composer-wrap{padding-left:16px;padding-right:16px;} }
.api-error { background:#fff1f0; color:#a02e2e; padding:12px 24px; border-bottom:1px solid #f3c1bf; font-size:13px; }
.context-panel { margin-top:22px; border:1px solid #e1e6ee; border-radius:12px; padding:18px; background:#fafbfc; white-space:pre-wrap; font-size:13px; line-height:1.6; }
.context-panel h3 { margin:10px 0 5px; }
.context-panel p { margin:7px 0; }
.draft-text { white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; }
.action-row { display:flex; flex-wrap:wrap; gap:9px; margin-top:19px; }
.action-button, .copy-button { background:#eaf0f9; color:#243f69; border:1px solid #cbd7ea; padding:9px 13px; border-radius:8px; font-size:12px; }
.action-button:hover, .copy-button:hover { background:#dbe7f7; }
.action-button:disabled { opacity:.5; cursor:default; }
.working { font-size:12px; color:#65758c; margin:18px 0; }
/* Unified work list and document split-view */
.thread-content { display:flex; flex:1; min-width:0; flex-direction:column; gap:3px; }
.thread-status { font-size:10px; color:#8a94a4; }
.topbar-right { display:flex; align-items:center; gap:12px; }
.language-label { color:#7c8798; font-size:12px; }
.language-select { background:white; border:1px solid #dce2ea; padding:7px; border-radius:8px; color:#34445a; }
.small-button { border:1px solid #dce2ea; background:white; border-radius:8px; padding:7px 11px; color:#314e77; }
.draft-pane { width:clamp(295px, 30vw, 570px); flex:none; min-width:0; display:flex; flex-direction:column; border-left:1px solid #e1e6ee; background:#fcfdff; }
.draft-pane.expanded { width:min(65vw, 1000px); }
.draft-header { display:flex; justify-content:space-between; align-items:center; padding:16px 18px; border-bottom:1px solid #e4e8ef; }
.draft-header strong { font-size:14px; } .draft-header strong span {font-size:11px; color:#9ca6b4;}
.draft-controls { display:flex; align-items:center; gap:5px; }
.draft-body { flex:1; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; padding:24px; line-height:1.75; font-size:14px; color:#334257; }
.draft-footer { padding:14px 18px; border-top:1px solid #e4e8ef; }
.copy-button { width:100%; }
.conversation { padding:28px max(22px,calc((100% - 770px)/2)) 24px; min-height:0; }
.composer-wrap { padding:12px max(22px,calc((100% - 770px)/2)) 22px; }
.typing-dots { display:inline-flex; gap:4px; margin-right:9px; align-items:center; }
.typing-dots i { display:block; width:6px; height:6px; border-radius:50%; background:#4e6b99; animation:dot-pulse 1.1s infinite ease-in-out; }
.typing-dots i:nth-child(2) { animation-delay:.15s; }
.typing-dots i:nth-child(3) { animation-delay:.3s; }
@keyframes dot-pulse { 0%,70%,100% {opacity:.25; transform:translateY(0)} 35% {opacity:1; transform:translateY(-4px)} }
.working { display:flex; align-items:center; padding:15px 0 7px; }
@media(max-width:1050px) {
  .draft-pane { position:absolute; right:0; top:67px; bottom:0; width:min(520px,90vw); z-index:4; box-shadow:-5px 0 24px #233e691a; }
  .draft-pane.expanded { width:min(850px,96vw); }
}

/* Workflow entry points are separate from the saved-work list. */
.workflow-buttons { display:flex; flex-direction:column; gap:9px; }
.workflow-buttons .new-button { width:100%; }
.existing-button { background:#fff; color:#243f69; border:1px solid #cbd7ea; border-radius:10px; padding:12px; text-align:left; font-size:13px; font-weight:650; white-space:nowrap; }
.existing-button:hover:not(:disabled) { background:#eaf0f9; }
.existing-button:disabled, .new-button:disabled { opacity:.55; cursor:default; }
.existing-button span { font-size:17px; margin-right:8px; vertical-align:-1px; }

/* Actions on saved work; keep the existing sidebar layout. */
.thread-row { position:relative; display:flex; align-items:center; border-radius:9px; }
.thread-row:hover, .thread-row.selected { background:#e6ebf4; }
.thread-row .thread { flex:1; width:auto; min-width:0; padding-right:4px; }
.thread-row .thread:hover, .thread-row .thread.selected { background:transparent; }
.thread-more { position:relative; flex:none; padding-right:5px; }
.thread-menu-button { width:29px; height:30px; border:0; border-radius:7px; background:transparent;
  color:#65758c; font-size:21px; line-height:1; opacity:0; }
.thread-row:hover .thread-menu-button, .thread-menu-button:focus-visible,
.thread-menu-button[aria-expanded="true"] { opacity:1; }
.thread-menu-button:hover { background:#d8e2f0; }
.thread-menu { position:absolute; top:31px; right:3px; z-index:10; min-width:130px;
  padding:5px; background:#fff; border:1px solid #dce2ea; border-radius:9px;
  box-shadow:0 7px 22px #233e6926; }
.thread-delete { width:100%; border:0; border-radius:6px; background:transparent;
  color:#b42318; padding:9px 12px; font-size:12px; text-align:left; }
.thread-delete:hover { background:#fff1f0; }
.thread-delete:disabled, .thread-menu-button:disabled { opacity:.35; cursor:default; }
@media (hover:none) { .thread-menu-button { opacity:1; } }




