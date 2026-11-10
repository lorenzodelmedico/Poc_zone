# Remplacer API.embed() dans app/clients.py et ajouter import time si absent.
# Contrat unique : tous les consommateurs extraient result['vectors'].
def embed(self, texts, *, on_batch=None):
    from app.tracking import record_embedding_batch
    vectors, batches, usage_totals = [], [], {}
    for i in range(0, len(texts), 16):
        batch = texts[i:i + 16]
        event = {'started_at_ns': time.time_ns(), 'batch_size': len(batch),
                 'batch_index': i // 16, 'usage': {}}
        started = time.perf_counter()
        try:
            data = self.call('POST', endpoint('EMBEDDING_URL'), auth='model', json={
                'model': os.getenv('EMBEDDING_MODEL'), 'input': batch, 'encoding_format': 'float'})
            if isinstance(data.get('usage'), dict):
                event['usage'] = {key: value for key, value in data['usage'].items()
                                  if key in {'prompt_tokens', 'total_tokens', 'completion_tokens'}
                                  and type(value) is int and value >= 0}
            for key, value in event['usage'].items():
                usage_totals[key] = usage_totals.get(key, 0) + value
            rows = sorted(data['data'], key=lambda row: row['index'])
            if [row['index'] for row in rows] != list(range(len(batch))):
                raise ValueError('Réponse embeddings incomplète ou indices invalides.')
            for row in rows:
                vector = row['embedding']
                if (not isinstance(vector, list) or not vector
                        or not all(math.isfinite(float(x)) for x in vector)):
                    raise ValueError('Embedding invalide.')
                vectors.append([float(x) for x in vector])
        except Exception as exc:
            event['error'] = type(exc).__name__
            raise
        finally:
            event['duration_s'] = time.perf_counter() - started
            batches.append(event)
            record_embedding_batch(event, os.getenv('EMBEDDING_MODEL', ''))
            if on_batch is not None:
                on_batch(dict(event))
    return {'vectors': vectors, 'model': os.getenv('EMBEDDING_MODEL', ''),
            'usage': usage_totals,
            'usage_batches': sum(bool(x['usage']) for x in batches), 'batches': batches}
