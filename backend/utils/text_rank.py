"""Local extractive summaries using TF-IDF similarity and TextRank."""
import re
from utils.shutdown import check_shutdown


def summarize(text: str, sentence_count: int = 2) -> str:
    check_shutdown()
    if sentence_count < 1:
        raise ValueError('Summary sentence count must be positive')
    sentences = list(dict.fromkeys(part.strip() for part in re.split(r'(?<=[.!?\u3002\uff01\uff1f])\s+', text) if part.strip()))
    if not sentences:
        return ''
    if len(sentences) <= sentence_count:
        return ' '.join(sentences)
    # Bound dense similarity matrices; reduce long inputs in source order first.
    if len(sentences) > 300:
        candidates = [summarize('\n'.join(sentences[i:i + 300]), sentence_count)
                      for i in range(0, len(sentences), 300)]
        return summarize('\n'.join(candidates), sentence_count)
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    try:
        vectors = TfidfVectorizer(token_pattern=r'(?u)\b\w+\b').fit_transform(sentences)
    except ValueError as exc:
        if 'empty vocabulary' not in str(exc):
            raise
        return ' '.join(sentences[:sentence_count])
    similarity = (vectors @ vectors.T).toarray()
    np.fill_diagonal(similarity, 0)
    totals = similarity.sum(axis=1)
    transitions = np.divide(similarity, totals[:, None],
                            out=np.zeros_like(similarity), where=totals[:, None] != 0)
    n = len(sentences)
    scores = np.full(n, 1 / n)
    for _ in range(100):
        check_shutdown()
        next_scores = (1 - 0.85) / n + 0.85 * (
            transitions.T @ scores + scores[totals == 0].sum() / n)
        if np.abs(next_scores - scores).sum() < 1e-6:
            scores = next_scores
            break
        scores = next_scores
    ranked = sorted(range(n), key=lambda i: (-float(scores[i]), i))
    selected, seen = [], set()
    for index in ranked:
        if sentences[index] in seen:
            continue
        selected.append(index)
        seen.add(sentences[index])
        if len(selected) == sentence_count:
            break
    return ' '.join(sentences[i] for i in sorted(selected))
