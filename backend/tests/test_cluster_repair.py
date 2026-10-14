import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from core.config import Settings
from pipeline.tree_builder import TreeBuilder
from pipeline.ingestion_models import Branch, ClusteringResponse, ClusterAssignment
from utils.shutdown import shutdown_event


class ClusterRepairTests(unittest.TestCase):
    def setUp(self):
        shutdown_event.clear()

    def builder(self, groups):
        responses = [SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=ClusteringResponse(
            clusters=[ClusterAssignment(cluster_name=f'Theme {i}', child_indices=indices) for i, indices in enumerate(batch)])))]) for batch in groups]
        call = Mock(side_effect=responses)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=call)))
        return TreeBuilder('test', client=client, settings=Settings('sqlite://', Path('.'), '', None, '')), call

    def test_oversized_semantic_group_is_repaired_recursively(self):
        builder, call = self.builder([[[0, 1, 2, 3], [4, 5]], [[0, 1], [2, 3]]])
        root = Branch(header='Root', summary='', children=[Branch(header=str(i), content=f'Fact {i}.', summary=f'Fact {i}.') for i in range(6)])
        builder.cluster_tree_recursive(root, N=2)
        leaves = []
        def visit(node):
            self.assertLessEqual(len(node.children or []), 2)
            if not node.children:
                leaves.append(node.content)
            for child in node.children or []:
                visit(child)
        visit(root)
        self.assertEqual(leaves, [f'Fact {i}.' for i in range(6)])
        self.assertEqual(call.call_count, 2)

    def test_one_unchanged_oversized_group_stops_before_infinite_recursion(self):
        builder, call = self.builder([[[0, 1, 2, 3]]])
        children = [Branch(header=str(i), content=f'Fact {i}.', summary=f'Fact {i}.') for i in range(4)]
        root = Branch(header='Root', summary='', children=children)
        with self.assertRaisesRegex(RuntimeError, 'did not reduce'):
            builder.cluster_tree_recursive(root, N=2)
        self.assertEqual([c.content for c in root.children], [f'Fact {i}.' for i in range(4)])
        self.assertEqual(call.call_count, 1)
