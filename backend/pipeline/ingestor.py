from utils.shutdown import check_shutdown
"""Original parser orchestration adapted to independent Stride storage."""
from pathlib import Path
from pipeline.tree_builder import TreeBuilder
from pipeline.utils.parsers.document_parser import StatefulDocumentParser
from pipeline.utils.parsers.extractors import extract_pdf_pages, extract_docx_pages, extract_text_pages
from pipeline.utils.core.vision_helper import VisionHelper


class Ingestor:
    @staticmethod
    def process_file(document_id, file_path, storage, client, settings, transcriber=None, n_value=None, cancel_event=None, cache=None):
        path = Path(file_path)
        builder = TreeBuilder(document_id, client=client, settings=settings, checkpoint_cache=cache)
        vision = VisionHelper(client, settings.vision_model or settings.tree_builder_model or settings.model)
        if cache:
            cache.bind(builder, '_ask_llm_to_split', lambda text, previous_context=None: [text, previous_context])
            cache.bind(builder, '_summarize', lambda text: text)
            cache.bind(builder, '_summarize_cluster', lambda children: [[c.header, c.summary, c.content] for c in children])
            import hashlib
            cache.bind(vision, 'extract_image_content', lambda image: hashlib.sha256(image).hexdigest())
            if transcriber is not None:
                cache.bind(transcriber, 'transcribe', lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest())
        suffix = path.suffix.lower()
        if suffix in {'.mp3', '.wav', '.m4a', '.mp4', '.avi', '.mov', '.mkv'}:
            from pipeline.utils.parsers.media_parser import StatefulMediaParser
            parser = StatefulMediaParser(document_id, path, tree_builder=builder, storage=storage, transcriber=transcriber, max_seconds=settings.max_media_seconds, cancel_event=cancel_event)
            return (yield from parser.process_media_statefully(n_value=n_value or settings.tree_fanout))
        parser = StatefulDocumentParser(document_id, str(path), tree_builder=builder, storage=storage, cancel_event=cancel_event)
        if suffix == '.pdf':
            extractor = lambda p: extract_pdf_pages(p, vision, cache=cache)
        elif suffix == '.docx':
            extractor = lambda p: extract_docx_pages(p, vision, cache=cache)
        elif suffix in {'.txt', '.md'}:
            extractor = extract_text_pages
        else:
            raise ValueError('Unsupported learning material format')
        if cache:
            original_extractor = extractor
            extractor = lambda p: cache.run('document_extract', {'format': suffix}, lambda: original_extractor(p))
        return (yield from parser.process_document_statefully(extractor_func=extractor, n_value=n_value or settings.tree_fanout))


def consume(generator, progress=None):
    while True:
        try:
            event = next(generator)
            if event == 'cancelled':
                check_shutdown()
                raise ValueError('Ingestion cancelled; checkpoint retained')
            if progress:
                progress(event)
        except StopIteration as finished:
            check_shutdown()
            if finished.value is None:
                raise ValueError('Ingestion returned no semantic tree')
            return finished.value


def flatten_tree(root, document_id=None):
    passages = []
    def visit(node):
        if document_id is not None:
            node.document_id = str(document_id)
        if node.content:
            node.metadata['passage_index'] = len(passages)
            passage = {'header': node.header, 'page': node.metadata.get('page', node.page_number), 'text': node.content}
            if node.metadata.get('timestamp'):
                passage['timestamp'] = node.metadata['timestamp']
            passages.append(passage)
        for child in node.children or []:
            visit(child)
    visit(root)
    if not passages:
        raise ValueError('Semantic ingestion produced no source leaves')
    return passages
