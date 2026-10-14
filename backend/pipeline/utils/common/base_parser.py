import threading
from typing import List, Optional
from pipeline.ingestion_models import Branch
from pipeline.tree_builder import TreeBuilder
from pipeline.utils.core.helper_fns import serialize_branch

class BaseStatefulParser:
    """Base class for parsers that maintain state and checkpoints during processing."""

    def __init__(self, document_id: str, file_path: str, checkpoint_suffix: str = "", cancel_event: threading.Event = None, tree_builder=None, storage=None):
        self.document_id = document_id
        self.file_path = file_path
        self.checkpoint_suffix = checkpoint_suffix
        self.tree_builder = tree_builder or TreeBuilder(document_id=document_id)
        if storage is None:
            raise ValueError("Stride storage must be injected")
        self.storage = storage
        self._cancel_event: threading.Event = cancel_event or threading.Event()

    def _save_checkpoint(self, completed_pages: int, branches: List[Branch], last_header: str):
        """Persist parsed branches after each page so we can resume on crash."""
        data = {
            "completed_pages": completed_pages,
            "last_header": last_header,
            "branches": [serialize_branch(b) for b in branches],
        }
        self.storage.save_checkpoint(self.document_id, data, self.checkpoint_suffix)

    def _load_checkpoint(self) -> Optional[dict]:
        """Return checkpoint data if a previous run was interrupted, else None."""
        return self.storage.load_checkpoint(self.document_id, self.checkpoint_suffix)

    def _clear_checkpoint(self):
        """Remove the checkpoint record after successful completion."""
        if not getattr(self.storage, 'defer_cleanup', False):
            self.storage.delete_checkpoint(self.document_id, self.checkpoint_suffix)

    def _get_last_leaf_node(self, node: Branch) -> Branch:
        """Helper function to find the very last active section on a page/segment."""
        if not node.children:
            return node
        return self._get_last_leaf_node(node.children[-1])
