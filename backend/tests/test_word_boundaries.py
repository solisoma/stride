import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
from core.config import Settings
from pipeline.tree_builder import TreeBuilder
from pipeline.ingestion_models import WordBoundary, WordBoundaryList


class BoundaryTests(unittest.TestCase):
    def split(self, text, starts):
        parsed = WordBoundaryList(sections=[WordBoundary(header=f'Section {i}', start_word=n) for i, n in enumerate(starts)])
        call = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=call)))
        settings = Settings('sqlite://', Path('.'), '', None, '')
        result = TreeBuilder('test', client=client, settings=settings)._ask_llm_to_split(text)
        return result, call

    def test_exact_original_text_including_pdf_characters_and_whitespace(self):
        text = '  Certi\ufb01ed title\nIntroduction real-world.\n\nTarget candidate hands\u2011on.  '
        sections, call = self.split(text, [0, 4])
        self.assertEqual(''.join(s['content'] for s in sections), text)
        self.assertTrue(sections[1]['content'].startswith('Target'))
        self.assertIn('[4]Target', call.call_args.kwargs['messages'][1]['content'])

    def test_mid_line_boundary_and_atomic_source(self):
        text = 'First topic. Second topic.'
        sections, _ = self.split(text, [0, 2])
        self.assertEqual([s['content'] for s in sections], ['First topic. ', 'Second topic.'])
        sections, _ = self.split(text, [0])
        self.assertEqual(sections[0]['content'], text)

    def test_invalid_boundaries_keep_every_source_character(self):
        for starts in ([], [0, 0], [0, 3, 2], [0, 99], [0, -1]):
            with self.subTest(starts=starts):
                sections, _ = self.split('One two three four.', starts)
                self.assertEqual(sections, [{'header': 'Source section', 'content': 'One two three four.'}])

    def test_sections_are_rechecked_until_atomic(self):
        responses = [WordBoundaryList(sections=[WordBoundary(header='First', start_word=0), WordBoundary(header='Second', start_word=2)]),
                     WordBoundaryList(sections=[WordBoundary(header='Atomic', start_word=0)]),
                     WordBoundaryList(sections=[WordBoundary(header='Atomic', start_word=0)])]
        call = Mock(side_effect=[SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=p))]) for p in responses])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=call)))
        builder = TreeBuilder('test', client=client, settings=Settings('sqlite://', Path('.'), '', None, ''))
        branches = builder.build_branch_recursive('First topic. Second topic.', 7)
        self.assertEqual(call.call_count, 3)
        self.assertEqual(''.join(b.content or '' for b in branches), 'First topic. Second topic.')
        self.assertEqual([b.header for b in branches], ['First', 'Second'])
        self.assertTrue(all(b.page_number == 7 for b in branches))

    def test_nested_hierarchy_preserves_text_and_parent_links(self):
        builder = TreeBuilder('test', client=object(), settings=Settings('sqlite://', Path('.'), '', None, ''))
        builder._ask_llm_to_split = Mock(side_effect=[
            [{'header': 'Group', 'content': 'Alpha. Beta. '}, {'header': 'Last', 'content': 'Gamma.'}],
            [{'header': 'Alpha', 'content': 'Alpha. '}, {'header': 'Beta', 'content': 'Beta. '}],
            [{'header': 'Atomic', 'content': 'Alpha. '}],
            [{'header': 'Atomic', 'content': 'Beta. '}],
            [{'header': 'Atomic', 'content': 'Gamma.'}],
        ])
        branches = builder.build_branch_recursive('Alpha. Beta. Gamma.', 2)
        self.assertEqual(builder._ask_llm_to_split.call_count, 5)
        group = branches[0]
        self.assertEqual(group.header, 'Group')
        self.assertIsNone(group.content)
        self.assertEqual([c.header for c in group.children or []], ['Alpha', 'Beta'])
        self.assertTrue(all(c.parent is group for c in group.children or []))
        self.assertEqual(''.join(c.content or '' for c in group.children or []) + (branches[1].content or ''), 'Alpha. Beta. Gamma.')

    def test_depth_limit_preserves_source_and_marks_reason(self):
        builder = TreeBuilder('test', client=object(), settings=Settings('sqlite://', Path('.'), '', None, ''))
        builder.max_split_depth = 0
        branch = builder.build_branch_recursive('Original source.', 3)[0]
        self.assertEqual(branch.content, 'Original source.')
        self.assertEqual(branch.metadata['split_stop_reason'], 'depth_limit')

    def test_invalid_boundaries_log_reason_then_retry_with_correction(self):
        bad = WordBoundaryList(sections=[WordBoundary(header='Private title', start_word=-1)])
        good = WordBoundaryList(sections=[WordBoundary(header='Good title', start_word=0)])
        call = Mock(side_effect=[SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=p))]) for p in (bad, good)])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=call)))
        builder = TreeBuilder('test', client=client, settings=Settings('sqlite://', Path('.'), '', None, ''))
        with self.assertLogs('learnforward.pipeline.tree_builder', level='WARNING') as captured:
            result = builder._ask_llm_to_split('Private source text.')
        self.assertEqual(result[0]['content'], 'Private source text.')
        self.assertEqual(call.call_count, 2)
        fields = captured.records[0].fields
        self.assertEqual(fields['start_words'], [-1])
        self.assertEqual(fields['validation_reasons'], ['start_out_of_range'])
        self.assertNotIn('Private', str(fields))
        self.assertIn('start_out_of_range', call.call_args.kwargs['messages'][0]['content'])

    def test_invalid_retries_are_bounded_and_source_is_retained(self):
        with self.assertLogs('learnforward.pipeline.tree_builder', level='WARNING') as captured:
            result, call = self.split('Original source.', [2])
        self.assertEqual(call.call_count, 2)
        self.assertEqual(result[0]['content'], 'Original source.')
        self.assertEqual(captured.records[-1].msg, 'semantic_boundaries_invalid_source_preserved')
        self.assertIn('start_out_of_range', captured.records[-1].fields['validation_reasons'])

    def test_first_boundary_corrected_without_retry_or_shifting_later_starts(self):
        text = 'D) Add the --batch flag. Another section.'
        with self.assertLogs('learnforward.pipeline.tree_builder', level='WARNING') as captured:
            sections, call = self.split(text, [1, 5])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(''.join(s['content'] for s in sections), text)
        self.assertTrue(sections[0]['content'].startswith('D)'))
        self.assertEqual(sections[1]['content'], 'Another section.')
        record = captured.records[0]
        self.assertEqual(record.msg, 'semantic_first_boundary_corrected')
        self.assertEqual(record.fields['original_start_words'], [1, 5])
        self.assertEqual(record.fields['start_words'], [0, 5])
        self.assertNotIn('D)', str(record.fields))

    def test_atomic_section_positive_start_is_corrected(self):
        with self.assertLogs('learnforward.pipeline.tree_builder', level='WARNING'):
            sections, call = self.split('D) Original source.', [2])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(sections[0]['content'], 'D) Original source.')

    def test_prompt_prioritizes_coherent_units_and_atomic_examples(self):
        _, call = self.split('D) Add the --batch flag.', [0])
        prompt = call.call_args.kwargs['messages'][0]['content']
        self.assertIn('single logical flow', prompt)
        self.assertIn('lose meaning or necessary context', prompt)
        self.assertIn('distinct logical subsections', prompt)
        self.assertIn('If a new topic begins, ignore the previous context', prompt)
        self.assertNotIn('Batch flag option', prompt)
        self.assertNotIn('ALL its answer choices', prompt)
        self.assertNotIn('[0]Introduction [1]Basics.', prompt)
