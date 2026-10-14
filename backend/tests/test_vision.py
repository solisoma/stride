import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pipeline.vision_models import ImageExtraction
from pipeline.utils.core.vision_helper import VisionHelper
from pipeline.utils.parsers.extractors import analyze_images


class VisionTests(unittest.TestCase):
    def helper(self, kind, visible='', explanation=''):
        parsed = ImageExtraction(kind=kind, visible_text=visible, diagram_explanation=explanation)
        call = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]))
        return VisionHelper(SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=call))), 'vision-model'), call

    def test_text_returns_only_transcription(self):
        helper, call = self.helper('text', 'Equation: E = mc?', 'Unwanted commentary')
        self.assertEqual(helper.extract_image_content(b'\x89PNGtest'), 'Equation: E = mc?')
        self.assertIs(call.call_args.kwargs['response_format'], ImageExtraction)

    def test_diagram_returns_explanation(self):
        helper, _ = self.helper('diagram', 'Start End', 'An arrow connects Start to End.')
        self.assertEqual(helper.extract_image_content(b'\xff\xd8test'), 'An arrow connects Start to End.')

    def test_mixed_keeps_both_and_decorations_are_ignored(self):
        helper, _ = self.helper('mixed', 'Figure 1', 'A connects to B.')
        self.assertEqual(helper.extract_image_content(b'\x89PNGtest'), 'Figure 1\n\nA connects to B.')
        decorative, _ = self.helper('other')
        self.assertEqual(analyze_images([b'\x89PNGtest'], decorative), '')

    def test_missing_expected_content_fails_instead_of_fabricating(self):
        for kind in ('text', 'diagram', 'mixed'):
            helper, _ = self.helper(kind)
            with self.assertRaises(ValueError):
                helper.extract_image_content(b'\x89PNGtest')

    def test_unreadable_is_logged_and_skipped(self):
        helper, _ = self.helper('unreadable')
        with self.assertLogs('learnforward.vision', level='WARNING'):
            self.assertEqual(helper.extract_image_content(b'\x89PNGtest'), '')
