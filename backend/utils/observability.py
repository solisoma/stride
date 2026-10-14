"""Structured, request-correlated logging without payloads or credentials."""
import contextvars
import json
import logging
import threading
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastapi import HTTPException

request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar('request_id', default=None)
_lock = threading.Lock()
_users = 0


def get_logger(name):
    return logging.getLogger(f'learnforward.{name}')


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {'timestamp': datetime.now(timezone.utc).isoformat(), 'level': record.levelname, 'logger': record.name, 'event': record.getMessage(), 'request_id': request_id.get()}
        data.update(getattr(record, 'fields', {}))
        return json.dumps(data, ensure_ascii=True, default=str)


def configure_logging(directory, level='INFO'):
    global _users
    with _lock:
        logger = logging.getLogger('learnforward')
        if not _users:
            Path(directory).mkdir(parents=True, exist_ok=True)
            file = RotatingFileHandler(Path(directory) / 'backend.jsonl', maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
            for handler in [logging.StreamHandler(), file]:
                handler.setFormatter(JsonFormatter())
                logger.addHandler(handler)
            logger.setLevel(level)
            logger.propagate = False
        _users += 1


def close_logging():
    global _users
    with _lock:
        _users = max(0, _users - 1)
        if not _users:
            logger = logging.getLogger('learnforward')
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)


PUBLIC_MESSAGES = {
    'REQUEST_CANCELLED': 'Stride is restarting. Please try again shortly.',
    'PROVIDER_TIMEOUT': 'This is taking longer than expected. Please try again.',
    'PROVIDER_RATE_LIMIT': 'Stride is busy right now. Please try again in a few minutes.',
    'MATERIAL_NOT_READABLE': 'We could not read this file. Try a readable document or a recording with clear audio.',
    'MODEL_RESPONSE_INVALID': 'We could not prepare a useful response this time. Please try again.',
}


class OperationError(HTTPException):
    def __init__(self, status_code, detail, code, stage):
        self.diagnostic = detail
        super().__init__(status_code, PUBLIC_MESSAGES.get(code, 'We could not complete this request right now. Please try again later.'))
        self.code, self.stage = code, stage


def describe_failure(stage, exception):
    cause = exception
    seen = set()
    while cause.__cause__ and id(cause) not in seen:
        seen.add(id(cause)); cause = cause.__cause__
    name = type(cause).__name__.lower()
    status = getattr(cause, 'status_code', None)
    if name == 'operationcancelled':
        return OperationError(503, 'Server shutdown requested; operation cancelled.', 'REQUEST_CANCELLED', stage)
    if 'timeout' in name:
        return OperationError(504, f'{stage} timed out. Retry or check the model endpoint.', 'PROVIDER_TIMEOUT', stage)
    if status == 401 or 'authentication' in name:
        return OperationError(502, 'The AI provider rejected its credentials. Check the backend API key and endpoint.', 'PROVIDER_AUTH_FAILED', stage)
    if status == 429 or 'ratelimit' in name:
        return OperationError(503, 'The AI provider is rate-limited or out of quota. Check quota and retry later.', 'PROVIDER_RATE_LIMIT', stage)
    if status == 404:
        return OperationError(502, 'The configured model or provider endpoint was not found. Check the model name and base URL.', 'PROVIDER_NOT_FOUND', stage)
    if 'connection' in name:
        return OperationError(502, 'Cannot reach the AI provider. Check the endpoint and network connection.', 'PROVIDER_UNREACHABLE', stage)
    if status in {400, 403, 422}:
        return OperationError(502, 'The AI provider rejected this request. Check model permissions and support for structured output, images, or audio.', 'PROVIDER_REQUEST_REJECTED', stage)
    # Inspect known local errors for classification, but never expose arbitrary exception text.
    message = str(cause).lower()
    if isinstance(cause, ValueError) and ('configure' in message or 'model' in message and 'required' in message):
        return OperationError(503, 'AI configuration is incomplete. Set the required model and API key in backend/.env.', 'CONFIGURATION_MISSING', stage)
    if stage == 'ingestion' and isinstance(cause, ValueError) and any(s in message for s in ['no readable', 'no audio', 'duration limit', 'unsupported']):
        return OperationError(422, 'The file could not be processed. Check readable content, supported format, audio track, and duration limit.', 'MATERIAL_NOT_READABLE', stage)
    if isinstance(cause, (ValueError, TypeError)):
        return OperationError(502, 'The model response failed validation. Retry or check the configured model capabilities.', 'MODEL_RESPONSE_INVALID', stage)
    return OperationError(500, f'{stage} failed unexpectedly. Use the request ID to find the backend log.', 'OPERATION_FAILED', stage)


def failure(stage, exception, **fields):
    error = describe_failure(stage, exception)
    chain, seen, current = [], set(), exception
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        frames = traceback.extract_tb(current.__traceback__)
        chain.append({'type': type(current).__name__, 'frames': [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name} for f in frames]})
        current = current.__cause__
    get_logger('errors').error('operation_failed', extra={'fields': {'stage': stage, 'error_code': error.code, 'diagnostic': error.diagnostic, 'exception_chain': chain, **fields}})
    return error
