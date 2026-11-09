# Remplacer _trace() dans app/tracking.py. Les imports existants datetime et
# MLflow, ainsi que export_run(), restent dans le fichier.
def _trace(mlflow, run, result, experiment_id):
    started = int(datetime.fromisoformat(run['started_at']).timestamp() * 1_000_000_000)
    ended = started + max(1, int(float(run['duration'] or 0) * 1_000_000_000))
    routing = result.get('routing', {})
    tags = {'poc_run_id': run['run_id'], 'mode': run['mode'],
            'prompt_variant': run['prompt_variant'], 'status': run['status']}
    tags.update({f'routing.{key}': str(routing[key]) for key in
                 ('route', 'method', 'framework_version', 'config_hash') if routing.get(key) is not None})
    root = mlflow.start_span_no_context('Assistant', span_type='AGENT', experiment_id=experiment_id,
        start_time_ns=started,
        inputs={'question': run['question'], 'mode': run['mode'], 'selected': run['selected']},
        tags=tags)
    for key in ('route', 'active_skills', 'retrieval_status', 'answer_scope', 'fallback_reason',
                'source_ids', 'source_revision'):
        if result.get(key) is not None:
            root.set_attribute(key, result[key])
    spans = {}
    try:
        for step in result.get('steps', []):
            start = max(started, int(step.get('started_at_ns', started)))
            end = start + max(1, int(float(step.get('duration_s', 0)) * 1_000_000_000))
            ended = max(ended, end)
            span_type = {'llm': 'LLM', 'mcp': 'TOOL', 'tool': 'TOOL',
                         'retrieval': 'RETRIEVER', 'verification': 'CHAIN',
                         'routing': 'CHAIN', 'context': 'TOOL', 'embedding': 'EMBEDDING'}.get(step.get('kind'))
            if span_type is None:
                span_type = 'TOOL' if step['name'].startswith('MCP ') else 'CHAIN'
            child = mlflow.start_span_no_context(step['name'], span_type=span_type,
                parent_span=spans.get(step.get('parent_step_id'), root),
                start_time_ns=start, inputs=step.get('inputs'))
            if step.get('step_id'):
                spans[step['step_id']] = child
            model = step.get('details', {}).get('embedding_model') if step.get('kind') == 'embedding' else (
                result.get('model') if step.get('kind') == 'llm' else None)
            if model:
                child.set_attribute('mlflow.llm.model', model)
            usage = step.get('usage') or {}
            prompt, completion, total = (usage.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
            if (step.get('kind') == 'embedding' and type(prompt) is int and type(total) is int
                    and completion is None and total >= prompt):
                completion = total - prompt
            if (all(type(value) is int and value >= 0 for value in (prompt, completion, total))
                    and prompt + completion == total):
                child.set_attribute('mlflow.chat.tokenUsage', {
                    'input_tokens': prompt, 'output_tokens': completion, 'total_tokens': total})
            child.end(outputs={key: step[key] for key in
                ('outputs', 'usage', 'details', 'warning', 'error') if key in step},
                status='ERROR' if step.get('error') else 'OK', end_time_ns=end)
        retrieved = list({d['doc_id']: {'doc_id': d['doc_id'], 'title': d['title']}
                          for d in result.get('evidence', [])}.values())
        verification = result.get('verification', {})
        root.end(outputs={'answer': result.get('answer', ''), 'status': run['status'],
            'error': result.get('error', ''), 'sources': retrieved,
            'cited_sources': result.get('sources', []), 'checks': result.get('checks', {}),
            'routing': result.get('routing', {}), 'answer_status': result.get('answer_status', ''),
            'route': result.get('route'), 'active_skills': result.get('active_skills', []),
            'retrieval_status': result.get('retrieval_status'), 'answer_scope': result.get('answer_scope'),
            'fallback_reason': result.get('fallback_reason'), 'source_ids': result.get('source_ids', []),
            'verification': {key: verification.get(key) for key in ('status', 'scope', 'method', 'counts', 'reason')}},
            status='ERROR' if run['status'] == 'error' else 'OK', end_time_ns=ended)
    except Exception:
        root.end(status='ERROR')
        raise
    if not mlflow.get_trace(root.trace_id):
        raise RuntimeError('Trace MLflow non enregistrée.')
    return root.trace_id


def source_job_trace(mlflow, job, experiment_id):
    """Trace indépendante de la demande de chat ; aucune URL source exportée."""
    started = job['started_at_ns']
    ended = started + max(1, int(job['duration_s'] * 1_000_000_000))
    root = mlflow.start_span_no_context('Indexation documentaire', span_type='CHAIN',
        experiment_id=experiment_id, start_time_ns=started,
        inputs={'job_id': job['job_id'], 'source_id': job['source_id']},
        tags={'job_id': job['job_id'], 'source_id': job['source_id'], 'status': job['status']})
    try:
        for step in job.get('steps', []):
            child = mlflow.start_span_no_context(step['name'], span_type='EMBEDDING', parent_span=root,
                start_time_ns=step['started_at_ns'], inputs=step.get('inputs'))
            child.set_attribute('mlflow.llm.model', step['details']['embedding_model'])
            usage = step.get('usage', {})
            prompt, total = usage.get('prompt_tokens'), usage.get('total_tokens')
            if type(prompt) is int and type(total) is int and total == prompt:
                child.set_attribute('mlflow.chat.tokenUsage', {
                    'input_tokens': prompt, 'output_tokens': 0, 'total_tokens': total})
            end = step['started_at_ns'] + max(1, int(step['duration_s'] * 1_000_000_000))
            child.end(outputs={key: step[key] for key in ('usage', 'details', 'error') if key in step},
                      status='ERROR' if step.get('error') else 'OK', end_time_ns=end)
        root.end(outputs={key: job[key] for key in ('status', 'documents_indexed', 'documents_completed',
            'documents_total', 'error') if key in job}, status='ERROR' if job['status'] == 'failed' else 'OK',
            end_time_ns=ended)
    except Exception:
        root.end(status='ERROR')
        raise
    if not mlflow.get_trace(root.trace_id):
        raise RuntimeError('Trace d’indexation non enregistrée.')
    return root.trace_id
