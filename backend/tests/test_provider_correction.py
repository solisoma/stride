import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from providers.compatible import CompatibleProvider


class ProviderCorrectionTests(unittest.TestCase):
    def provider(self, contents):
        settings = SimpleNamespace(model='test', api_key='non-secret-test', base_url=None)
        responses = [SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=c))]) for c in contents]
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=responses))))
        return CompatibleProvider(settings), client

    def test_bad_citation_gets_one_grounded_correction(self):
        provider, client = self.provider([json.dumps({'content':'Answer', 'citations':['old:0']}), json.dumps({'content':'Answer', 'citations':['1:0']})])
        with patch('providers.compatible.OpenAI'), patch('providers.compatible.trace_client', return_value=client):
            result = provider.generate('Explain', [{'id':'1:0', 'text':'Evidence'}])
        self.assertEqual(result['citations'], ['1:0'])
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_persistently_invalid_references_still_fail(self):
        invalid = json.dumps({'content':'Answer', 'citations':['invented:0']})
        provider, client = self.provider([invalid, invalid])
        with patch('providers.compatible.OpenAI'), patch('providers.compatible.trace_client', return_value=client):
            with self.assertRaises(ValueError):
                provider.generate('Explain', [{'id':'1:0', 'text':'Evidence'}])
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_malformed_json_can_be_corrected_without_accepting_uncited_text(self):
        provider, client = self.provider(['not JSON', json.dumps({'content':'Answer', 'citations':['1:0']})])
        with patch('providers.compatible.OpenAI'), patch('providers.compatible.trace_client', return_value=client):
            self.assertEqual(provider.generate('Explain', [{'id':'1:0', 'text':'Evidence'}])['content'], 'Answer')
