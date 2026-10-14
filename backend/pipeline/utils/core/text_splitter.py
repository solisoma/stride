from typing import List

class RecursiveCharacterTextSplitter:
    """
    A lightweight implementation of a recursive character text splitter.
    It attempts to split text using a sequence of separators (e.g. paragraphs, sentences, words, characters)
    so that each chunk is roughly under the maximum chunk size.
    """
    def __init__(
        self,
        separators: List[str] = None,
        chunk_size: int = 2000,
        chunk_overlap: int = 200
    ):
        self.separators = separators or ["\n\n", "\n", " ", ""]
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        # 1. Find the appropriate separator
        separator = separators[-1]
        new_separators = []
        for i, s in enumerate(separators):
            if s == "":
                separator = s
                break
            if s in text:
                separator = s
                new_separators = separators[i + 1:]
                break

        # 2. Split the text
        splits = text.split(separator) if separator else list(text)

        # 3. Process splits
        final_chunks = []
        good_splits = []
        _separator = "" if separator == "" else separator

        for s in splits:
            if len(s) <= self.chunk_size:
                if not s.strip():
                    continue
                good_splits.append(s)
            else:
                if good_splits:
                    merged_text = self._merge_splits(good_splits, _separator)
                    final_chunks.extend(merged_text)
                    good_splits = []
                
                if not new_separators:
                    final_chunks.append(s)
                else:
                    # Recursively split this specific oversized chunk
                    other_info = self._split_text(s, new_separators)
                    final_chunks.extend(other_info)

        if good_splits:
            merged_text = self._merge_splits(good_splits, _separator)
            final_chunks.extend(merged_text)

        return final_chunks

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        chunks = []
        current_chunk = []
        current_len = 0

        for split in splits:
            split_len = len(split)
            sep_len = len(separator) if current_len > 0 else 0
            
            if current_len + sep_len + split_len > self.chunk_size:
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                    
                    # Backtrack for overlap
                    overlap_len = 0
                    overlap_chunk = []
                    for s in (reversed(current_chunk) if self.chunk_overlap > 0 else []):
                        if overlap_len + len(s) + sep_len > self.chunk_overlap and overlap_chunk:
                            break
                        overlap_chunk.insert(0, s)
                        overlap_len += len(s) + sep_len
                    
                    current_chunk = overlap_chunk
                    current_len = overlap_len

            current_chunk.append(split)
            current_len += split_len + sep_len

        if current_chunk:
            chunks.append(separator.join(current_chunk))

        return chunks
