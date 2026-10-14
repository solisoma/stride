import math
from typing import Optional, Callable, Generator, Sequence
from pipeline.utils.parsers.page_types import SourcePage
from pipeline.utils.common.base_parser import BaseStatefulParser
from pipeline.ingestion_models import Branch
from pipeline.utils.core.helper_fns import deserialize_branch

class StatefulDocumentParser(BaseStatefulParser):
    """Parses a document logically chunk-by-chunk with stateful checkpointing."""

    def __init__(self, document_id: str, file_path: str, cancel_event=None, tree_builder=None, storage=None):
        super().__init__(document_id, file_path, cancel_event=cancel_event, tree_builder=tree_builder, storage=storage)

    def process_document_statefully(self, extractor_func: Callable[[str], Sequence[str | SourcePage]], n_value: Optional[int] = None) -> Generator[str, None, Branch]:
        """Main loop for stateful document parsing with progress streaming."""
        yield "Extracting text from document..."
        checkpoint = self._load_checkpoint()
        pages = extractor_func(self.file_path)
        total_pages = len(pages)
        if not pages:
            raise ValueError("No readable source content")

        master_document_branch = Branch(
            header=f"Document: {self.document_id}",
            summary="",
            content=None,
            children=[],
            page_number=1,
            document_id=self.document_id
        )

        if checkpoint:
            resume_from = checkpoint["completed_pages"]
            current_active_header = checkpoint["last_header"]
            if checkpoint.get('root'):
                master_document_branch = deserialize_branch(checkpoint['root'])
            else:
                restored = [deserialize_branch(b) for b in checkpoint['branches']]
                master_document_branch.children.extend(restored)
            yield f"Resuming ingestion from page {resume_from + 1}..."
        else:
            resume_from = 0
            current_active_header = "Introduction"

        for page_num, page_text in enumerate(pages, start=1):
            if page_num <= resume_from:
                continue

            if self._cancel_event.is_set():
                yield "cancelled"
                return

            yield f"Parsing segment {page_num} of {total_pages}..."
            page_branches = self.tree_builder.build_branch_recursive(
                text=page_text['text'] if isinstance(page_text, dict) else page_text,
                current_page=page_text['page'] if isinstance(page_text, dict) and isinstance(page_text['page'], int) else page_num,
                previous_context=current_active_header,
                metadata={k: v for k, v in page_text.items() if k != 'text'} if isinstance(page_text, dict) else {}
            )
            master_document_branch.children.extend(page_branches)
            last_leaf = self._get_last_leaf_node(page_branches[-1]) if page_branches else None
            if last_leaf:
                current_active_header = last_leaf.header

            self._save_checkpoint(
                completed_pages=page_num,
                branches=master_document_branch.children,
                last_header=current_active_header
            )

        if self._cancel_event.is_set():
            yield "cancelled"
            return

        phase = checkpoint.get('phase', 'splitting') if checkpoint else 'splitting'
        def save_phase(name):
            from pipeline.utils.core.helper_fns import serialize_branch
            self.storage.save_checkpoint(self.document_id, {
                'completed_pages': total_pages, 'last_header': current_active_header,
                'branches': [], 'root': serialize_branch(master_document_branch),
                'phase': name, 'n_value': n_value,
            }, self.checkpoint_suffix)
        if phase not in {'summarized', 'complete'}:
            yield "Generating segment summaries..."
            self.tree_builder.summarize_tree_recursive(master_document_branch)
            save_phase('summarized')

        if self._cancel_event.is_set():
            yield "cancelled"
            return

        if n_value is not None:
            N = n_value
            yield f"Clustering knowledge tree (N={N})..."
        else:
            N = max(3, min(8, math.ceil(total_pages / 10)))
            yield f"Auto-tuning knowledge hierarchy (N={N})..."

        if phase != 'complete' or checkpoint.get('n_value') != n_value:
            self.tree_builder.cluster_tree_recursive(master_document_branch, N=N)
            save_phase('complete')

        yield "Finalizing ingestion..."
        self._clear_checkpoint()
        return master_document_branch
