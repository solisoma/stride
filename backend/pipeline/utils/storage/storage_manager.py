from db.models import DocumentTree, IngestionCheckpoint


class StorageManager:
    """Original persistence operations scoped to Stride's injected session."""
    def __init__(self, db, defer_cleanup=False):
        self.db = db
        self.defer_cleanup = defer_cleanup

    def save_checkpoint(self, document_id, state_data, suffix=''):
        key = f'{document_id}{suffix}'
        row = self.db.get(IngestionCheckpoint, key)
        if row is None:
            row = IngestionCheckpoint(key=key, state_data=state_data)
            self.db.add(row)
        else:
            row.state_data = state_data
        self.db.commit()

    def load_checkpoint(self, document_id, suffix=''):
        row = self.db.get(IngestionCheckpoint, f'{document_id}{suffix}')
        return row.state_data if row else None

    def delete_checkpoint(self, document_id, suffix=''):
        self.db.query(IngestionCheckpoint).filter_by(key=f'{document_id}{suffix}').delete()
        self.db.commit()

    def save_document_tree(self, document_id, tree_data, n_value=5):
        row = self.db.get(DocumentTree, int(document_id))
        if row is None:
            self.db.add(DocumentTree(document_id=int(document_id), tree_data=tree_data, n_value=n_value))
        else:
            row.tree_data, row.n_value = tree_data, n_value
        self.db.flush()

    def load_document_tree(self, document_id):
        row = self.db.get(DocumentTree, int(document_id))
        return row.tree_data if row else None

    def load_document_tree_with_n(self, document_id):
        row = self.db.get(DocumentTree, int(document_id))
        return (row.tree_data, row.n_value) if row else None
