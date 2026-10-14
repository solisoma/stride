import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from utils.tracing import trace_client, transcribe, serialize_parsed_response


class TracingTests(unittest.TestCase):
    def test_enabled_requires_key(self):
        with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true', 'LANGSMITH_API_KEY': ''}):
            with self.assertRaisesRegex(ValueError, 'LANGSMITH_API_KEY'):
                trace_client(object(), 'pipeline')

    def test_wrapper_enabled_and_request_metadata(self):
        from utils.observability import request_id
        client = object()
        token = request_id.set('request-reference')
        try:
            with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true', 'LANGSMITH_API_KEY': 'fake-test-key'}), patch('langsmith.wrappers.wrap_openai', return_value=client) as wrapper:
                self.assertIs(trace_client(client, 'pipeline'), client)
                self.assertEqual(wrapper.call_args.kwargs['tracing_extra']['metadata']['request_id'], 'request-reference')
        finally:
            request_id.reset(token)

    def test_transcription_records_text_without_audio_inputs(self):
        audio = object()
        client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=Mock(return_value=SimpleNamespace(text='Transcript')))))
        with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true', 'LANGSMITH_API_KEY': 'fake-test-key'}), patch('langsmith.traceable', side_effect=lambda **kwargs: lambda call: call) as trace:
            self.assertEqual(transcribe(client, 'audio-model', audio), 'Transcript')
            self.assertEqual(trace.call_args.kwargs['process_inputs']({}), {'model': 'audio-model'})
            self.assertNotIn(audio, trace.call_args.kwargs.values())

    def test_disabled_keeps_original_client(self):
        client = object()
        with patch.dict(os.environ, {'LANGSMITH_TRACING': 'false'}):
            self.assertIs(trace_client(client, 'pipeline'), client)


class ParsedSerializationTests(unittest.TestCase):
    def test_specialized_none_serializer_with_real_parsed_model(self):
        import warnings
        from pydantic import BaseModel
        from pipeline.ingestion_models import SplitSectionList

        class Message(BaseModel):
            parsed: None = None
            content: str

        class Choice(BaseModel):
            message: Message

        class Response(BaseModel):
            choices: list[Choice]

        parsed = SplitSectionList(sections=[{'header': 'Facts', 'content': 'Original text.'}])
        response = Response(choices=[Choice(message=Message(content='json'))])
        response.choices[0].message.__dict__['parsed'] = parsed
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            data = serialize_parsed_response(response)
        self.assertEqual(data['choices'][0]['message']['parsed'], parsed.model_dump())
        self.assertIs(response.choices[0].message.parsed, parsed)

    def test_failed_call_has_no_output_to_serialize(self):
        self.assertEqual(serialize_parsed_response(None), {})

    def test_plain_completion_without_parsed_attribute(self):
        from pydantic import BaseModel
        class Message(BaseModel):
            content: str
        class Choice(BaseModel):
            message: Message
        class Response(BaseModel):
            choices: list[Choice]
        response = Response(choices=[Choice(message=Message(content='Useful response'))])
        output = serialize_parsed_response(response)
        self.assertEqual(output['choices'][0]['message']['content'], 'Useful response')
        self.assertIsNone(output['choices'][0]['message']['parsed'])

    def test_response_wrapper_and_dictionary_are_supported(self):
        data = {'choices': [{'message': {'content': 'Response'}}]}
        self.assertEqual(serialize_parsed_response(data), data)
        wrapper = SimpleNamespace(parse=lambda: None)
        self.assertEqual(serialize_parsed_response(wrapper), {})
