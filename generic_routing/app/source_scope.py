"""Filtre à appliquer au catalogue autorisé AVANT la recherche existante."""


def restrict_document_catalog(authorized_documents, document_ids=None):
    if document_ids is None:
        return authorized_documents
    if not isinstance(document_ids, list) or any(not isinstance(x, str) or not x for x in document_ids):
        raise ValueError('Périmètre documentaire invalide.')
    allowed = set(document_ids)
    # [] signifie un périmètre vide, jamais une recherche globale.
    return [doc for doc in authorized_documents if doc['doc_id'] in allowed]
