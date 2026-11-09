"""Observation par contexte d'exécution, sans nouvel appel au modèle."""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

_current = ContextVar('embedding_observer', default=None)


@contextmanager
def observe_embeddings(steps, *, purpose):
    token = _current.set((steps, purpose))
    try:
        yield
    finally:
        _current.reset(token)


def record_embedding_batch(event, model):
    observation = _current.get()
    if observation is None:
        return
    steps, purpose = observation
    step = {'name': 'Embedding', 'kind': 'embedding', 'step_id': uuid.uuid4().hex,
            'started_at_ns': event['started_at_ns'], 'duration_s': event['duration_s'],
            'inputs': {'batch_size': event['batch_size']}, 'usage': event['usage'],
            'details': {'embedding_model': model, 'batch_index': event['batch_index'], 'purpose': purpose}}
    if event.get('error'):
        step['error'] = event['error']
    steps.append(step)
