"""Adapted audio extraction/chunking with isolated temporary storage."""
import tempfile
from pathlib import Path

MEDIA_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.mp4', '.avi', '.mov', '.mkv'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}


def timestamp(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


def transcribe_segments(audio, transcriber, directory, max_seconds=1800):
    if len(audio) > max_seconds * 1000:
        raise ValueError('Recording exceeds the configured duration limit.')
    if not len(audio):
        raise ValueError('Recording has no audio.')
    passages = []
    for start in range(0, len(audio), 30000):
        chunk = audio[start:start + 30000]
        path = Path(directory) / 'segment.wav'
        chunk.export(str(path), format='wav')
        # Fail the whole upload if a segment fails; never silently omit speech.
        text = transcriber.transcribe(path)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'No transcript for segment beginning {timestamp(start / 1000)}.')
        location = f'{timestamp(start / 1000)} - {timestamp((start + len(chunk)) / 1000)}'
        passages.append({'page': location, 'timestamp': location, 'text': text.strip()})
    return passages


def extract_media(path, transcriber, max_seconds=1800):
    if transcriber is None:
        raise ValueError('Configure a transcription provider before uploading media.')
    from pydub import AudioSegment
    with tempfile.TemporaryDirectory(prefix='learnforward-media-') as directory:
        audio_path = path
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            from moviepy import VideoFileClip
            audio_path = Path(directory) / 'audio.wav'
            with VideoFileClip(str(path)) as video:
                if video.audio is None:
                    raise ValueError('Video contains no audio track.')
                if video.duration > max_seconds:
                    raise ValueError('Recording exceeds the configured duration limit.')
                video.audio.write_audiofile(str(audio_path), logger=None)
        audio = AudioSegment.from_file(str(audio_path))
        return transcribe_segments(audio, transcriber, directory, max_seconds)


class StatefulMediaParser:
    """Original transcript-to-semantic-tree lifecycle with timestamp checkpoints."""
    def __init__(self, document_id, file_path, tree_builder, storage, transcriber, max_seconds, cancel_event=None):
        self.document_id, self.file_path = document_id, file_path
        self.builder, self.storage = tree_builder, storage
        self.transcriber, self.max_seconds = transcriber, max_seconds
        self.cancel_event = cancel_event

    def process_media_statefully(self, n_value=None):
        from pipeline.utils.parsers.document_parser import StatefulDocumentParser
        from pipeline.utils.core.text_splitter import RecursiveCharacterTextSplitter
        yield 'Extracting and transcribing recording...'
        cached = self.storage.load_checkpoint(self.document_id, '_transcript')
        segments = cached['segments'] if cached else extract_media(self.file_path, self.transcriber, self.max_seconds)
        if not cached:
            self.storage.save_checkpoint(self.document_id, {'segments': segments}, '_transcript')
        text, offsets = '', []
        for segment in segments:
            start = len(text)
            text += segment['text'] + ' '
            offsets.append((start, len(text), segment['timestamp']))
        splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
        pages, cursor = [], 0
        for chunk in splitter.split_text(text):
            start = text.find(chunk, cursor)
            if start < 0:
                raise ValueError('Transcript chunk could not be mapped to its timestamps')
            cursor = start
            end = start + len(chunk)
            stamps = [stamp for left, right, stamp in offsets if end > left and start < right]
            if not stamps:
                raise ValueError('Transcript timestamp attribution failed')
            stamp = stamps[0].split(' - ')[0] + ' - ' + stamps[-1].split(' - ')[1]
            pages.append({'page': stamp, 'timestamp': stamp, 'text': chunk})
        parser = StatefulDocumentParser(self.document_id, self.file_path, tree_builder=self.builder, storage=self.storage, cancel_event=self.cancel_event)
        parser.checkpoint_suffix = '_media'
        root = yield from parser.process_document_statefully(lambda _: pages, n_value=n_value)
        if root is not None and not getattr(self.storage, 'defer_cleanup', False):
            self.storage.delete_checkpoint(self.document_id, '_transcript')
        return root
