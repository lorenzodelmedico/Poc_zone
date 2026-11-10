# Remplacer Store.observed(). Imports js et utcnow déjà présents dans store.py.
def observed(self, doc_id, doc=None):
    with self.connect() as c:
        if doc is not None:
            c.execute('UPDATE documents SET title=?,source_url=?,modified_at=?,metadata=?,'
                      'allowed_user_codes=?,user_roles=? WHERE doc_id=?',
                      (doc.title, doc.url, doc.modified_at, js(doc.metadata),
                       js(doc.allowed_user_codes), js(doc.user_roles), doc_id))
        c.execute('UPDATE documents SET active=1,observed_at=? WHERE doc_id=?',
                  (utcnow(), doc_id))


# Remplacer également Store.disable_other_sources : une synchronisation globale
# ne retire pas implicitement les sources ajoutées depuis le chat.
def disable_other_sources(self, source_ids):
    if source_ids:
        self.query(f"UPDATE documents SET active=0 WHERE source_id NOT IN ({placeholders(source_ids)}) "
                   "AND source_id NOT LIKE 'chat:%'", source_ids)
    else:
        self.query("UPDATE documents SET active=0 WHERE source_id NOT LIKE 'chat:%'")
