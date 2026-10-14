import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from core.config import Settings
from db.models import Base, Document, Journey
from db.session import create_database
from pipeline.ingestor import Ingestor, consume, flatten_tree
from pipeline.tree_builder import TreeBuilder
from pipeline.ingestion_models import Branch
from pipeline.utils.storage.storage_manager import StorageManager
from pipeline.utils.core.helper_fns import serialize_branch, deserialize_branch
from pipeline.utils.parsers.document_parser import StatefulDocumentParser
from retrieval.service import retrieve, index_existing
from retrieval.retriever import DocumentRetriever
from tests.pipeline_fake import PipelineClient


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.settings = Settings(f'sqlite:///{self.root / "test.db"}', self.root, '', None, '', tree_fanout=3, summary_backend="llm")
        self.client = PipelineClient()
        self.engine, self.sessions = create_database(self.settings.database_url)
        Base.metadata.create_all(self.engine)
        self.db = self.sessions()
        self.db.info.update(settings=self.settings, pipeline_client=self.client)
        self.storage = StorageManager(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def document(self, passages):
        journey = Journey(goal='exam', subject='Concepts', access_token='private')
        self.db.add(journey)
        self.db.flush()
        document = Document(journey_id=journey.id, name='notes', passages=passages)
        self.db.add(document)
        self.db.commit()
        return document

    def test_original_semantic_build_rollup_clustering_and_saved_source_ids(self):
        doc = self.document([{'page': i + 1, 'text': f'Concept {i} source facts.'} for i in range(16)])
        index_existing(doc, self.storage, self.client, self.settings)
        tree = deserialize_branch(self.storage.load_document_tree(doc.id))
        def verify(node):
            self.assertLessEqual(len(node.children or []), 3)
            self.assertTrue(node.summary)
            for child in node.children or []:
                verify(child)
        verify(tree)
        self.assertIn('ClusteringResponse', self.client.calls)
        self.assertIn('WordBoundaryList', self.client.calls)
        if self.settings.summary_backend == 'llm':
            self.assertIn('summary', self.client.calls)
        else:
            self.assertNotIn('summary', self.client.calls)
        evidence = retrieve([doc], 'Explain the concepts', limit=100, db=self.db)
        self.assertEqual(len(evidence), 16)
        self.assertEqual({p['id'] for p in evidence}, {f'{doc.id}:{i}' for i in range(16)})
        self.assertIn('RouterResponse', self.client.calls)

    def test_router_selection_controls_retrieval_without_keyword_matching(self):
        doc = self.document([{'page': 1, 'text': 'Plants turn sunlight into chemical energy.'}, {'page': 2, 'text': 'Unrelated source.'}])
        index_existing(doc, self.storage, self.client, self.settings)
        original = self.client.create
        def choose(model, messages, response_format=None, **kwargs):
            if response_format and response_format['json_schema']['name'] == 'RouterResponse':
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'relevant_children': [{'index': 0, 'action': 'DRILL'}]})))])
            return original(model, messages, response_format, **kwargs)
        self.client.create = choose
        evidence = retrieve([doc], 'photosynthesis', db=self.db)
        self.assertEqual([p['id'] for p in evidence], [f'{doc.id}:0'])
        self.assertIn('sunlight', evidence[0]['text'])

    def test_parser_checkpoint_resumes_and_preserves_physical_page(self):
        builder = TreeBuilder('upload', client=self.client, settings=self.settings)
        first = Branch(header='First', summary='', content='First page.', page_number=1, document_id='upload')
        self.storage.save_checkpoint('upload', {'completed_pages': 1, 'last_header': 'First', 'branches': [serialize_branch(first)]})
        parser = StatefulDocumentParser('upload', 'unused', tree_builder=builder, storage=self.storage)
        events = []
        tree = consume(parser.process_document_statefully(lambda _: [{'page': 1, 'text': 'First page.'}, {'page': 3, 'text': 'Third physical page.'}], n_value=3), events.append)
        passages = flatten_tree(tree)
        self.assertEqual([p['page'] for p in passages], [1, 3])
        self.assertEqual(self.client.calls.count('WordBoundaryList'), 1)
        self.assertIsNone(self.storage.load_checkpoint('upload'))
        self.assertTrue(any('Resuming' in event for event in events))

    def test_malformed_split_and_nonreducing_clusters_fail_without_losing_source(self):
        builder = TreeBuilder('upload', client=self.client, settings=self.settings)
        original = self.client.create
        def malformed(model, messages, response_format=None, **kwargs):
            if response_format and response_format['json_schema']['name'] == 'WordBoundaryList':
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'sections': [{'header': 'Invented', 'content': 'Invented facts'}]})))])
            return original(model, messages, response_format, **kwargs)
        self.client.create = malformed
        branches = builder.build_branch_recursive('Original facts.', 1)
        self.assertEqual(branches[0].content, 'Original facts.')
        node = Branch(header='Root', summary='', children=[Branch(header=str(i), summary='Summary', content=str(i)) for i in range(4)])
        from pipeline.ingestion_models import ClusteringResponse, ClusterAssignment
        builder._ask_llm_to_cluster = lambda *args, **kwargs: ClusteringResponse(clusters=[ClusterAssignment(cluster_name=str(i), child_indices=[i]) for i in range(4)])
        with self.assertRaises(RuntimeError):
            builder.cluster_tree_recursive(node, 3)
        self.assertEqual(len(node.children), 4)

    def test_cancel_retains_checkpoint(self):
        cancel = threading.Event(); cancel.set()
        self.storage.save_checkpoint('upload', {'completed_pages': 0, 'last_header': 'Intro', 'branches': []})
        parser = StatefulDocumentParser('upload', 'unused', tree_builder=TreeBuilder('upload', client=self.client, settings=self.settings), storage=self.storage, cancel_event=cancel)
        with self.assertRaises(ValueError):
            consume(parser.process_document_statefully(lambda _: ['Source text']))
        self.assertIsNotNone(self.storage.load_checkpoint('upload'))

    def test_media_runs_through_original_semantic_tree_with_timestamps(self):
        path = self.root / 'lecture.wav'
        path.write_bytes(b'fixture')
        segments = [{'page': '00:00:00 - 00:00:30', 'timestamp': '00:00:00 - 00:00:30', 'text': 'First spoken concept.'}, {'page': '00:00:30 - 00:00:45', 'timestamp': '00:00:30 - 00:00:45', 'text': 'Another spoken concept.'}]
        with patch('pipeline.utils.parsers.media_parser.extract_media', return_value=segments):
            tree = consume(Ingestor.process_file('media-upload', path, self.storage, self.client, self.settings, transcriber=object()))
        leaves = flatten_tree(tree)
        self.assertIn('timestamp', leaves[0])
        self.assertEqual(leaves[0]['timestamp'], '00:00:00 - 00:00:45')
        self.assertIn('WordBoundaryList', self.client.calls)
        if self.settings.summary_backend == 'llm':
            self.assertIn('summary', self.client.calls)
        else:
            self.assertNotIn('summary', self.client.calls)

    def test_pdf_blank_pages_do_not_renumber_source_locations(self):
        from pipeline.utils.parsers.extractors import extract_pdf_pages
        pages = [SimpleNamespace(extract_text=lambda: '', images=[]), SimpleNamespace(extract_text=lambda: 'Physical second page.', images=[])]
        with patch('pypdf.PdfReader', return_value=SimpleNamespace(pages=pages)):
            extracted = extract_pdf_pages('fixture.pdf', object())
        self.assertEqual(extracted[0]['page'], 2)

    def test_failed_router_stream_terminates_instead_of_hanging(self):
        doc = self.document([{'page': 1, 'text': 'A source concept.'}])
        index_existing(doc, self.storage, self.client, self.settings)
        retriever = DocumentRetriever([doc.id], self.storage, self.client, self.settings)
        retriever._ask_router = lambda *args: (_ for _ in ()).throw(ValueError('simulated routing failure'))
        with self.assertRaises(RuntimeError):
            list(retriever.search_library_stream('Explain this concept'))


class LocalSummaryPipelineTests(PipelineTests):
    def setUp(self):
        super().setUp()
        self.settings.summary_backend = 'textrank'

    def test_original_semantic_build_rollup_clustering_and_saved_source_ids(self):
        doc = self.document([{'page': i + 1, 'text': f'Concept {i} source facts.'} for i in range(8)])
        index_existing(doc, self.storage, self.client, self.settings)
        tree = deserialize_branch(self.storage.load_document_tree(doc.id))
        self.assertTrue(tree.summary)
        self.assertIn('ClusteringResponse', self.client.calls)
        self.assertIn('WordBoundaryList', self.client.calls)
        self.assertNotIn('summary', self.client.calls)
        evidence = retrieve([doc], 'Explain concepts', limit=100, db=self.db)
        self.assertEqual(len(evidence), 8)
        self.assertIn('RouterResponse', self.client.calls)
