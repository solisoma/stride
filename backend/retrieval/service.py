from pipeline.tree_builder import TreeBuilder
from pipeline.ingestion_models import Branch
from pipeline.utils.core.helper_fns import serialize_branch
from pipeline.utils.storage.storage_manager import StorageManager
from providers.pipeline_client import create_pipeline_client
from retrieval.retriever import DocumentRetriever


def index_existing(document, storage, client, settings):
    """Reindex earlier uploads without renumbering their established citations."""
    if storage.load_document_tree(document.id):
        return
    builder = TreeBuilder(str(document.id), client=client, settings=settings)
    children = []
    for index, passage in enumerate(document.passages):
        metadata = {**{k: v for k, v in passage.items() if k != 'text'}, 'passage_index': index}
        children.extend(builder.build_branch_recursive(passage['text'], passage['page'] if isinstance(passage['page'], int) else index + 1, metadata=metadata))
    root = Branch(header=document.name, summary='', children=children, document_id=str(document.id))
    builder.summarize_tree_recursive(root)
    builder.cluster_tree_recursive(root, settings.tree_fanout)
    storage.save_document_tree(document.id, serialize_branch(root), settings.tree_fanout)


def retrieve(documents, query, limit=12, db=None, all_sources=False):
    if not documents:
        return []
    if db is None:
        raise ValueError('Stride database session is required for semantic retrieval')
    settings = db.info['settings']
    client = db.info.get('pipeline_client') or create_pipeline_client(settings)
    storage = StorageManager(db)
    for document in documents:
        index_existing(document, storage, client, settings)
    if all_sources:
        # Coverage/planning needs all source leaves, not a relevance-filtered subset.
        return [{'id': f'{d.id}:{i}', 'document': d.name, **p} for d in documents for i, p in enumerate(d.passages)][:limit]
    retriever = DocumentRetriever([d.id for d in documents], storage, client, settings)
    retriever.evidence_only = True
    retriever._search_recursive(retriever.tree, query)
    lookup = {str(d.id): d for d in documents}
    results, seen = [], set()
    for chunk in retriever._collected:
        doc = lookup.get(str(chunk.document_id))
        index = (chunk.metadata or {}).get('passage_index')
        if doc is None or not isinstance(index, int) or not 0 <= index < len(doc.passages):
            raise ValueError('Retrieved leaf has invalid source attribution')
        source_id = f'{doc.id}:{index}'
        if source_id not in seen:
            seen.add(source_id)
            results.append({'id': source_id, 'document': doc.name, **doc.passages[index]})
    return results[:limit]
