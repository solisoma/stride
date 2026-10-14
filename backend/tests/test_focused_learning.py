import json
import unittest
from types import SimpleNamespace
from api.services.focused_learning import outline_evidence, guide_instruction


class FocusedLearningTests(unittest.TestCase):
    def test_outline_covers_late_sources_and_multiple_documents(self):
        class DB:
            def get(self, model, document_id):
                return SimpleNamespace(tree_data={'header': 'Course', 'children': [
                    {'header': 'Concept', 'summary': 'Required foundation',
                     'metadata': {'passage_index': i}} for i in range(40)]})
        documents = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        passages = [{'id': f'{d.id}:{i}', 'document': str(d.id), 'text': 'Original explanation'}
                    for d in documents for i in range(40)]
        result = outline_evidence(DB(), documents, passages)
        self.assertEqual(len(result), 80)
        self.assertEqual(result[-1]['id'], '2:39')
        self.assertEqual(result[-1]['outline_path'], ['Course', 'Concept'])
        self.assertEqual(passages[-1]['text'], 'Original explanation')

    def test_excluded_sources_do_not_reappear_from_tree(self):
        db = SimpleNamespace(get=lambda *args: None)
        result = outline_evidence(db, [SimpleNamespace(id=1)],
                                  [{'id': '1:1', 'document': 'Notes', 'text': 'Allowed'}])
        self.assertEqual([p['id'] for p in result], ['1:1'])

    def test_guide_preserves_goal_and_focus_contract(self):
        task = json.loads(guide_instruction(SimpleNamespace(goal='exam', subject='Kubernetes'),
                                          'Containers', {'citations': ['1:39']}))
        self.assertEqual(task['goal'], 'exam')
        self.assertEqual(task['topic_plan']['citations'], ['1:39'])
        self.assertIn('Merge repetition', task['approach'])
        self.assertIn('necessary foundations', task['approach'])
