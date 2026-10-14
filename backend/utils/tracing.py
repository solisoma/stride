from utils.model_limits import limit_client, model_gate
"""Trace model calls to LangSmith; never send credentials or audio files."""
import os
from utils.observability import request_id


def tracing_enabled():
    enabled = os.getenv('LANGSMITH_TRACING', 'true').lower() == 'true'
    if enabled and not os.getenv('LANGSMITH_API_KEY'):
        raise ValueError('Configure LANGSMITH_API_KEY for model tracing')
    if enabled:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "learnforward")
    return enabled


def serialize_parsed_response(response):
    # LangSmith also processes outputs=None when the underlying LLM call raises.
    # Its error is recorded separately; there is no successful output to serialize.
    if response is None:
        return {}
    if isinstance(response, dict):
        return response
    if not hasattr(response, 'model_dump') and callable(getattr(response, 'parse', None)):
        response = response.parse()
        if response is None:
            return {}
    # Some SDK responses retain a serializer specialized for parsed=None.
    # Serialize that field separately using its actual Pydantic model.
    data = response.model_dump(mode='json', exclude={
        'choices': {'__all__': {'message': {'parsed'}}}
    })
    for choice, serialized in zip(response.choices, data.get('choices', [])):
        parsed = getattr(choice.message, 'parsed', None)
        dump_parsed = getattr(parsed, 'model_dump', None)
        serialized['message']['parsed'] = dump_parsed(mode='json') if callable(dump_parsed) else parsed
    return data


def trace_client(client, component):
    if not tracing_enabled():
        return limit_client(client)
    from langsmith import traceable
    from langsmith.wrappers import wrap_openai
    completions = getattr(getattr(client, 'chat', None), 'completions', None)
    original_parse = getattr(completions, 'parse', None)
    metadata = {'component': component, 'request_id': request_id.get()}
    wrapped = wrap_openai(client, chat_name=f'Stride.{component}', tracing_extra={
        'metadata': metadata,
    })
    if original_parse is not None:
        # Keep automatic tracing for create(); use safe serialization for parse().
        wrapped.chat.completions.parse = traceable(
            name=f'Stride.{component}', run_type='llm',
            project_name=os.getenv('LANGSMITH_PROJECT', 'learnforward'),
            metadata=metadata, process_outputs=serialize_parsed_response,
        )(original_parse)
    return limit_client(wrapped)


def transcribe(client, model, audio):
    def call():
        def request():
            if hasattr(audio, 'seek'):
                audio.seek(0)
            return client.audio.transcriptions.create(model=model, file=audio).text
        return model_gate().run(request)
    if not tracing_enabled():
        return call()
    from langsmith import traceable
    traced = traceable(name='Stride.transcription', run_type='llm',
        project_name=os.getenv('LANGSMITH_PROJECT', 'learnforward'),
        metadata={'component': 'transcription', 'request_id': request_id.get(), 'model': model},
        process_inputs=lambda inputs: {'model': model},
    )(call)
    return traced()


def transcribe_local(model, call):
    """Trace text output without sending audio bytes or its file path."""
    if not tracing_enabled():
        return call()
    from langsmith import traceable
    return traceable(name='Stride.local_transcription', run_type='llm',
        project_name=os.getenv('LANGSMITH_PROJECT', 'learnforward'),
        metadata={'component': 'transcription', 'provider': 'local_whisper', 'model': model,
                  'request_id': request_id.get()},
        process_inputs=lambda inputs: {'model': model})(call)()
