import os
from functools import lru_cache
from threading import Lock
from utils.tracing import transcribe
from openai import OpenAI


class CompatibleTranscriber:
    """Adapter for endpoints implementing audio.transcriptions."""

    def __init__(self, settings):
        self.settings = settings

    def transcribe(self, path):
        if not self.settings.transcription_model or not self.settings.transcription_api_key:
            raise ValueError('Configure TRANSCRIPTION_MODEL and its API key.')
        client = OpenAI(api_key=self.settings.transcription_api_key, base_url=self.settings.transcription_base_url, timeout=float(os.getenv('LLM_TIMEOUT_SECONDS', '30')), max_retries=0)
        with path.open('rb') as audio:
            return transcribe(client, self.settings.transcription_model, audio)


class LocalWhisperTranscriber:
    """Load local weights lazily and reuse them across recording segments."""
    def __init__(self, settings):
        self.settings = settings

    def transcribe(self, path):
        from pathlib import Path
        from utils.shutdown import check_shutdown
        from utils.tracing import transcribe_local
        check_shutdown()
        path = Path(path)
        if not path.is_file():
            raise ValueError('Audio segment is unavailable')
        def call():
            model = load_local_model(self.settings.whisper_model, self.settings.whisper_device,
                                     str(self.settings.storage.parent / '.whisper'))
            check_shutdown()
            result = model.transcribe(str(path), task='transcribe',
                language=self.settings.whisper_language or None,
                fp16=self.settings.whisper_device != 'cpu', verbose=None)
            check_shutdown()
            text = result.get('text')
            if not isinstance(text, str) or not text.strip():
                raise ValueError('No readable transcript returned')
            return text.strip()
        return transcribe_local(self.settings.whisper_model, call)


def create_transcriber(settings):
    if settings.transcription_provider == 'whisper':
        return LocalWhisperTranscriber(settings)
    return CompatibleTranscriber(settings)


_local_model_lock = Lock()


@lru_cache(maxsize=1)
def load_local_model(model, device, directory):
    import shutil
    if shutil.which('ffmpeg') is None:
        raise RuntimeError('Install FFmpeg to use local Whisper transcription')
    try:
        from importlib import import_module
        whisper = import_module("whisper")
    except ImportError as exc:
        raise RuntimeError('Install local Whisper with uv sync --extra local-whisper') from exc
    with _local_model_lock:
        return whisper.load_model(model, device=device, download_root=directory)
