import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Settings:
    database_url: str
    storage: Path
    api_key: str
    base_url: str | None
    model: str
    max_upload_bytes: int = 20 * 1024 * 1024
    transcription_model: str = ''
    transcription_api_key: str = ''
    transcription_base_url: str | None = None
    max_media_seconds: int = 1800
    session_secure: bool = False
    tree_builder_model: str = ''
    retrieval_model: str = ''
    vision_model: str = ''
    tree_fanout: int = 5
    ollama_enabled: bool = False
    log_level: str = "INFO"
    log_dir: Path | None = None
    summary_backend: str = "textrank"

    rabbitmq_url: str = 'amqp://guest:guest@localhost:5672/%2F'
    ingestion_max_attempts: int = 3

    transcription_provider: str = 'api'
    whisper_model: str = 'base'
    whisper_device: str = 'cpu'
    whisper_language: str = ''

    def __post_init__(self):
        if self.transcription_provider not in {'api', 'whisper'}:
            raise ValueError('TRANSCRIPTION_PROVIDER must be api or whisper')
        if self.whisper_device not in {'cpu', 'cuda'}:
            raise ValueError('WHISPER_DEVICE must be cpu or cuda')
        if self.whisper_model not in {'tiny', 'base', 'small', 'medium', 'large', 'large-v1', 'large-v2', 'large-v3', 'turbo', 'large-v3-turbo', 'tiny.en', 'base.en', 'small.en', 'medium.en'}:
            raise ValueError('WHISPER_MODEL must be a supported Whisper model name')
        if self.ingestion_max_attempts < 1:
            raise ValueError('INGESTION_MAX_ATTEMPTS must be positive')
        if self.summary_backend not in {"textrank", "llm"}:
            raise ValueError("SUMMARY_BACKEND must be textrank or llm")
        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        self.log_level = self.log_level.upper()
        if self.max_upload_bytes <= 0 or self.max_media_seconds <= 0:
            raise ValueError('Upload size and media duration limits must be positive.')
        if self.tree_fanout < 2:
            raise ValueError('TREE_FANOUT must be at least two')

    @classmethod
    def load(cls):
        root = Path(__file__).resolve().parents[1]
        load_dotenv(root / '.env', override=False)
        return cls(
            os.getenv('STRIDE_DATABASE_URL') or os.getenv('LEARNFORWARD_DATABASE_URL') or os.getenv('DATABASE_URL') or f'sqlite:///{root / "learnforward.db"}',
            Path(os.getenv('STRIDE_STORAGE') or os.getenv('LEARNFORWARD_STORAGE', str(root / 'uploads'))),
            os.getenv('LLM_API_KEY', ''), os.getenv('LLM_BASE_URL') or None,
            os.getenv('LEARNING_MODEL', ''),
            max_upload_bytes=int(os.getenv('MAX_UPLOAD_BYTES', str(20 * 1024 * 1024))),
            transcription_model=os.getenv('TRANSCRIPTION_MODEL', ''),
            transcription_api_key=os.getenv('TRANSCRIPTION_API_KEY', '') or os.getenv('LLM_API_KEY', ''),
            transcription_base_url=os.getenv('TRANSCRIPTION_BASE_URL') or os.getenv('LLM_BASE_URL') or None,
            max_media_seconds=int(os.getenv('MAX_MEDIA_SECONDS', '1800')),
            session_secure=os.getenv('SESSION_SECURE', 'false').lower() == 'true',
            tree_builder_model=os.getenv('TREE_BUILDER_MODEL', ''),
            retrieval_model=os.getenv('RETRIEVAL_MODEL', ''),
            vision_model=os.getenv('VISION_MODEL', ''),
            tree_fanout=int(os.getenv('TREE_FANOUT', '5')),
            summary_backend=os.getenv('SUMMARY_BACKEND', 'textrank'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_dir=Path(os.getenv('LOG_DIR', str(root / 'logs'))),
            transcription_provider=os.getenv('TRANSCRIPTION_PROVIDER', 'api'),
            whisper_model=os.getenv('WHISPER_MODEL', 'base'),
            whisper_device=os.getenv('WHISPER_DEVICE', 'cpu'),
            whisper_language=os.getenv('WHISPER_LANGUAGE', ''),
            rabbitmq_url=os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/%2F'),
            ingestion_max_attempts=int(os.getenv('INGESTION_MAX_ATTEMPTS', '3')),
            ollama_enabled=os.getenv('OLLAMA_ENABLED', 'false').lower() == 'true',
        )
