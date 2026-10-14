import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from core.config import Settings
from providers.transcription import create_transcriber, LocalWhisperTranscriber, CompatibleTranscriber, load_local_model
from utils.shutdown import shutdown_event


class LocalTranscriptionTests(unittest.TestCase):
    def setUp(self):
        shutdown_event.clear()
        load_local_model.cache_clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.audio = self.root / 'segment.wav'
        self.audio.write_bytes(b'test audio')
        self.settings = Settings('sqlite://', self.root / 'uploads', '', None, '',
                                 transcription_provider='whisper', whisper_language='fr')

    def tearDown(self):
        load_local_model.cache_clear()
        self.tmp.cleanup()

    def test_factory_keeps_api_default_and_local_needs_no_key(self):
        self.assertIsInstance(create_transcriber(self.settings), LocalWhisperTranscriber)
        self.settings.transcription_provider = 'api'
        self.assertIsInstance(create_transcriber(self.settings), CompatibleTranscriber)

    def test_local_weights_are_lazy_reused_and_language_is_preserved(self):
        model = Mock()
        model.transcribe.return_value = {'text': ' Bonjour '}
        module = SimpleNamespace(load_model=Mock(return_value=model))
        with patch.dict('sys.modules', whisper=module), patch('shutil.which', return_value='ffmpeg'), \
             patch('utils.tracing.transcribe_local', side_effect=lambda name, call: call()):
            provider = create_transcriber(self.settings)
            module.load_model.assert_not_called()
            self.assertEqual(provider.transcribe(self.audio), 'Bonjour')
            self.assertEqual(provider.transcribe(self.audio), 'Bonjour')
            module.load_model.assert_called_once_with('base', device='cpu', download_root=str(self.root / '.whisper'))
            self.assertEqual(model.transcribe.call_args.kwargs['language'], 'fr')
            self.assertEqual(model.transcribe.call_args.kwargs['task'], 'transcribe')
            self.assertFalse(model.transcribe.call_args.kwargs['fp16'])

    def test_blank_transcript_is_rejected(self):
        model = Mock()
        model.transcribe.return_value = {'text': ' '}
        with patch('providers.transcription.load_local_model', return_value=model), \
             patch('utils.tracing.transcribe_local', side_effect=lambda name, call: call()):
            with self.assertRaises(ValueError):
                create_transcriber(self.settings).transcribe(self.audio)

    def test_missing_optional_dependency_or_ffmpeg_explains_setup(self):
        with patch('shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'FFmpeg'):
                load_local_model('base', 'cpu', str(self.root))
        with patch('shutil.which', return_value='ffmpeg'), patch.dict('sys.modules', whisper=None):
            with self.assertRaisesRegex(RuntimeError, 'uv sync --extra local-whisper'):
                load_local_model('base', 'cpu', str(self.root))

    def test_provider_and_model_settings_are_validated(self):
        for option in ({'transcription_provider': 'unknown'}, {'whisper_model': 'unknown'}, {'whisper_device': 'unknown'}):
            with self.assertRaises(ValueError):
                Settings('sqlite://', self.root, '', None, '', **option)
