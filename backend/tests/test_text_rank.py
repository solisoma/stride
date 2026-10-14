import unittest
from utils.text_rank import summarize


class TextRankTests(unittest.TestCase):
    def test_representative_source_sentences_in_source_order(self):
        sentences = ['Rain falls outside.', 'Binary search checks sorted arrays.', 'Binary search halves sorted arrays.', 'Binary search is efficient on sorted arrays.']
        result = summarize(' '.join(sentences))
        self.assertNotIn(sentences[0], result)
        self.assertEqual(result, summarize(' '.join(sentences)))
        self.assertEqual(sum(sentence in result for sentence in sentences), 2)
        self.assertEqual(result, ' '.join(sentence for sentence in sentences if sentence in result))

    def test_empty_short_and_symbol_only_inputs(self):
        self.assertEqual(summarize(''), '')
        self.assertEqual(summarize('One exact sentence.'), 'One exact sentence.')
        self.assertEqual(summarize('+++. ---. ***.'), '+++. ---.')

    def test_duplicate_sentences_do_not_consume_all_summary_slots(self):
        result = summarize('Repeated sentence. Repeated sentence. Different topic.')
        self.assertEqual(result.count('Repeated sentence.'), 1)
        self.assertIn('Different topic.', result)

    def test_long_inputs_are_bounded_and_keep_original_sentences(self):
        sentences = [f'Topic {i} explains local processing.' for i in range(650)]
        result = summarize(' '.join(sentences))
        self.assertEqual(sum(sentence in result for sentence in sentences), 2)

    def test_pdf_wrapped_lines_remain_complete_sentences(self):
        first = 'First sentence wraps\nacross lines.'
        second = 'Second sentence\nalso wraps.'
        result = summarize(first + ' ' + second)
        self.assertIn(first, result)
        self.assertIn(second, result)

    def test_pdf_blank_lines_between_words_do_not_create_word_summaries(self):
        text = 'Rain falls outside. Binary search checks sorted arrays. Binary search halves sorted arrays. Binary search is efficient on sorted arrays.'
        extracted = '\n \n'.join(text.split())
        result = ' '.join(summarize(extracted).split())
        self.assertNotIn('Rain falls outside.', result)
        self.assertIn('Binary search', result)
        self.assertGreater(len(result.split()), 8)
