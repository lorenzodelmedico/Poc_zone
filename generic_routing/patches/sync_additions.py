# Ajouter au module existant.
"""Exécuter l'indexeur existant ; aucune nouvelle logique d'ingestion SharePoint."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
import posixpath
import time
from urllib.parse import unquote, urlsplit, urlunsplit, parse_qs, urljoin
import uuid
from app.sources import queue_source, update_source
from app.tracking import observe_embeddings
_source_jobs_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='source-index')
_source_jobs_lock = RLock()
_source_jobs_jobs = {}
_source_jobs_MAX_PENDING = 16

def _source_jobs_parts(url):
    parsed = urlsplit(url.strip())
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('URL SharePoint HTTPS requise, sans identifiants intégrés.')
    path = parsed.path
    for _source_jobs_ in range(4):
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    if '%' in path or '\\' in path or any((ord(c) < 32 for c in url)):
        raise ValueError('Chemin de source invalide.')
    path = posixpath.normpath('/' + path.lstrip('/')).casefold()
    return (parsed, path)

def validate_source_url(url, allowed_roots):
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError('URL de source invalide.')
    if not allowed_roots:
        raise ValueError('Racines SharePoint autorisées non configurées.')
    parsed, path = _source_jobs_parts(url)
    parameters = parse_qs(parsed.query)
    target = (parameters.get('id') or parameters.get('RootFolder') or [None])[0]
    target_parsed, target_path = _source_jobs_parts(urljoin(url, target)) if target else (parsed, path)
    permitted = False
    for root in allowed_roots:
        base, prefix = _source_jobs_parts(root)
        if (parsed.hostname.casefold(), parsed.port or 443) == (base.hostname.casefold(), base.port or 443):
            inside = lambda p: prefix == '/' or p == prefix or p.startswith(prefix.rstrip('/') + '/')
            if (target_parsed.hostname.casefold(), target_parsed.port or 443) == (base.hostname.casefold(), base.port or 443) and inside(path) and inside(target_path):
                permitted = True
                break
    if not permitted:
        raise PermissionError('La source ne fait pas partie des racines autorisées.')
    return urlunsplit(('https', parsed.netloc.lower(), parsed.path or '/', parsed.query, ''))

def get_source_job(api, user_id, cid, job_id):
    with _source_jobs_lock:
        job = _source_jobs_jobs.get(job_id)
        if not job or job['_owner'] != (api, str(user_id), str(cid)):
            raise PermissionError('Travail inconnu dans cette conversation.')
        return deepcopy({k: v for k, v in job.items() if not k.startswith('_')})

def _source_jobs_public(job):
    return deepcopy({k: v for k, v in job.items() if not k.startswith('_')})

def _source_jobs_run(api, user_id, cid, source_id, job_id, url, index_existing, export_job):
    start = time.perf_counter()
    with _source_jobs_lock:
        job = _source_jobs_jobs[job_id]
        job['status'] = 'running'

    def report(label, completed=None, total=None):
        with _source_jobs_lock:
            job['progress'] = str(label)[:300]
            if type(completed) is int and completed >= 0:
                job['documents_completed'] = completed
            if type(total) is int and total >= 0:
                job['documents_total'] = total
    try:
        update_source(api, user_id, cid, source_id, status='running')
        with observe_embeddings(job['steps'], purpose='source_indexing'):
            result = index_existing(user_id, url, report)
        ids = result.get('document_ids') if isinstance(result, dict) else None
        if not isinstance(ids, list) or any((not isinstance(x, str) or not x for x in ids)):
            raise ValueError('L’indexeur doit retourner document_ids, liste des documents indexés.')
        if result.get('complete') is False:
            raise RuntimeError('Indexation incomplète ; la source reste indisponible.')
        ids = list(dict.fromkeys(ids))
        update_source(api, user_id, cid, source_id, status='completed', document_ids=ids)
        with _source_jobs_lock:
            job.update(status='completed', documents_indexed=len(ids), progress='Indexation terminée')
    except Exception as exc:
        with _source_jobs_lock:
            job.update(status='failed', error=type(exc).__name__, progress='Échec de l’indexation')
        try:
            update_source(api, user_id, cid, source_id, status='failed', error=type(exc).__name__)
        except PermissionError:
            pass
    finally:
        with _source_jobs_lock:
            job['duration_s'] = time.perf_counter() - start
            snapshot = _source_jobs_public(job)
        if export_job is not None:
            try:
                trace_id = export_job(snapshot)
                with _source_jobs_lock:
                    job['trace_id'] = trace_id
            except Exception as exc:
                with _source_jobs_lock:
                    job['tracking_error'] = type(exc).__name__

def enqueue_source_sync(api, user_id, cid, url, *, index_existing, allowed_roots, export_job=None):
    if not callable(index_existing):
        raise TypeError('La fonction d’indexation existante doit être raccordée.')
    url = validate_source_url(url, allowed_roots)
    with _source_jobs_lock:
        active = sum((j['status'] in {'queued', 'running'} for j in _source_jobs_jobs.values()))
        if len(_source_jobs_jobs) >= 256:
            for key in list(_source_jobs_jobs):
                if _source_jobs_jobs[key]['status'] not in {'queued', 'running'}:
                    del _source_jobs_jobs[key]
                    if len(_source_jobs_jobs) < 192:
                        break
        job_id = uuid.uuid4().hex
        if active >= _source_jobs_MAX_PENDING:
            raise RuntimeError('File d’indexation occupée ; nouvel essai nécessaire.')
        source_id, existing_id, created = queue_source(api, user_id, cid, url, job_id)
        if not created:
            return existing_id
        _source_jobs_jobs[job_id] = {'_owner': (api, str(user_id), str(cid)), 'job_id': job_id, 'source_id': source_id, 'status': 'queued', 'started_at': datetime.now(timezone.utc).isoformat(), 'started_at_ns': time.time_ns(), 'duration_s': 0.0, 'progress': 'Indexation en attente', 'documents_indexed': 0, 'steps': []}
        try:
            _source_jobs_pool.submit(_source_jobs_run, api, user_id, cid, source_id, job_id, url, index_existing, export_job)
        except Exception:
            _source_jobs_jobs[job_id]['status'] = 'failed'
            update_source(api, user_id, cid, source_id, status='failed', error='SubmissionError')
            raise
        return job_id
