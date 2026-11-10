# Ajouter cette méthode à Synchronizer, avec l’indentation de la classe.
# Les modifications de once() décrites dans MODIFICATIONS.md sont obligatoires.
def index_from_chat(self, user_id, url, report):
    from app.sources import manual_sharepoint_sources
    self.store.user(user_id)
    report('Synchronisation de la source sélectionnée')
    outcome = self.once(selected_urls=[url], request_user_id=user_id)
    if outcome['failures']:
        raise RuntimeError('La synchronisation ciblée a échoué.')
    source_ids = {source['id'] for source in manual_sharepoint_sources([url])}
    documents = self.store.active_docs_for_user(user_id)
    return {'document_ids': [doc['doc_id'] for doc in documents
                            if doc['source_id'] in source_ids], 'complete': True}
