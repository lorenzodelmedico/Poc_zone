# Ajouter au module existant.
"""Sélection documentaire temporaire dans le processus backend principal."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic
import uuid
_skills_lock = RLock()
_skills_states = OrderedDict()
_skills_TTL = 8 * 3600
_skills_LIMIT = 256

def _skills_key(api, user_id, cid):
    if not user_id or not cid:
        raise ValueError('Identité et conversation requises.')
    return (api, str(user_id), str(cid))

def _skills_state(key):
    now = monotonic()
    for old in list(_skills_states):
        state = _skills_states[old]
        busy = any((s['status'] in {'queued', 'running'} for s in state['sources']))
        if now - state['touched'] > _skills_TTL and (not busy):
            del _skills_states[old]
    if key not in _skills_states:
        if len(_skills_states) >= _skills_LIMIT:
            removable = next((k for k, v in _skills_states.items() if not any((s['status'] in {'queued', 'running'} for s in v['sources']))), None)
            if removable is None:
                raise RuntimeError('Capacité du registre de conversations atteinte.')
            del _skills_states[removable]
        _skills_states[key] = {'enabled': False, 'revision': 0, 'sources': [], 'touched': now}
    state = _skills_states[key]
    state['touched'] = now
    _skills_states.move_to_end(key)
    return state

def get_skill_state(api, user_id, cid):
    with _skills_lock:
        state = _skills_state(_skills_key(api, user_id, cid))
        sources = deepcopy(state['sources'])
        return {'document_search': state['enabled'], 'revision': state['revision'], 'source_ids': [s['source_id'] for s in sources if s['selected']], 'sources': sources}

def set_document_search(api, user_id, cid, enabled):
    if type(enabled) is not bool:
        raise ValueError('Activation booléenne requise.')
    with _skills_lock:
        state = _skills_state(_skills_key(api, user_id, cid))
        if state['enabled'] != enabled:
            state['enabled'] = enabled
            state['revision'] += 1

def select_source(api, user_id, cid, source_id, selected):
    if type(selected) is not bool:
        raise ValueError('Sélection booléenne requise.')
    with _skills_lock:
        state = _skills_state(_skills_key(api, user_id, cid))
        source = next((s for s in state['sources'] if s['source_id'] == source_id), None)
        if source is None:
            raise PermissionError('Source étrangère à la conversation.')
        if source['selected'] != selected:
            source['selected'] = selected
            state['revision'] += 1

def queue_source(api, user_id, cid, url, job_id):
    with _skills_lock:
        state = _skills_state(_skills_key(api, user_id, cid))
        source = next((s for s in state['sources'] if s['url'] == url), None)
        if source and source['status'] in {'queued', 'running'}:
            return (source['source_id'], source['job_id'], False)
        if source is None:
            if len(state['sources']) >= 32:
                raise ValueError('Nombre maximal de sources atteint.')
            source = {'source_id': uuid.uuid4().hex, 'url': url, 'document_ids': []}
            state['sources'].append(source)
        source.update(selected=True, status='queued', job_id=job_id, error=None)
        state.update(enabled=True, revision=state['revision'] + 1)
        return (source['source_id'], job_id, True)

def update_source(api, user_id, cid, source_id, *, status, document_ids=None, error=None):
    with _skills_lock:
        state = _skills_states.get(_skills_key(api, user_id, cid))
        source = next((s for s in state['sources'] if s['source_id'] == source_id), None) if state else None
        if source is None:
            raise PermissionError('Source indisponible dans la conversation.')
        source.update(status=status, error=error)
        if document_ids is not None:
            source['document_ids'] = list(document_ids)
        state['revision'] += 1

def document_scope(api, user_id, cid):
    state = get_skill_state(api, user_id, cid)
    selected = [s for s in state['sources'] if s['selected']]
    ready = not selected or all((s['status'] == 'completed' for s in selected))
    ids = list(dict.fromkeys((d for s in selected for d in s['document_ids'])))
    return {'enabled': state['document_search'], 'revision': state['revision'], 'source_ids': state['source_ids'], 'document_ids': ids, 'restricted': bool(selected), 'ready': ready}

def clear_skills(api, user_id, cid=None):
    with _skills_lock:
        for key in list(_skills_states):
            if key[0] is api and key[1] == str(user_id) and (cid is None or key[2] == str(cid)):
                del _skills_states[key]


def manual_sharepoint_sources(urls):
    from urllib.parse import urlsplit, urlunsplit
    from app.domain import stable_id
    sources = []
    seen = set()
    for url in urls:
        parts = urlsplit(url.strip())
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            raise ValueError('URL SharePoint invalide.')
        canonical = urlunsplit(('https', parts.netloc.lower(), parts.path, parts.query, ''))
        if canonical not in seen:
            sources.append({'id': 'chat:' + stable_id('sharepoint_manual', canonical),
                            'kind': 'sharepoint', 'urls': [canonical]})
            seen.add(canonical)
    return sources
