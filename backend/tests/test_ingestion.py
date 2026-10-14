import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from pipeline.utils.parsers.extractors import extract_text_pages
from pipeline.utils.parsers.media_parser import transcribe_segments


class Audio:
    def __init__(self, length):
        self.length = length
    def __len__(self):
        return self.length
    def __getitem__(self, interval):
        return Audio(min(interval.stop, self.length) - interval.start)
    def export(self, filename, format):
        Path(filename).write_bytes(b'test audio')


class IngestionTests(unittest.TestCase):
    def test_audio_segments_preserve_timestamps(self):
        transcriber = SimpleNamespace(transcribe=lambda path: 'Explaining binary search.')
        with tempfile.TemporaryDirectory() as directory:
            passages = transcribe_segments(Audio(45000), transcriber, directory)
        self.assertEqual(len(passages), 2)
        self.assertEqual(passages[1]['timestamp'], '00:00:30 - 00:00:45')


    def test_failed_segment_and_duration_limit_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                transcribe_segments(Audio(1000), SimpleNamespace(transcribe=lambda path: ''), directory)
            with self.assertRaises(ValueError):
                transcribe_segments(Audio(61000), None, directory, max_seconds=60)

    def test_text_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'notes.MD'
            path.write_text('# Binary search\nSorted inputs are required.', encoding='utf-8')
            self.assertIn('Sorted inputs', extract_text_pages(path)[0]['text'])
