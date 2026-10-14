def validate_citations(result, evidence):
    allowed = {p['id'] for p in evidence}
    citations = result.get('citations')
    if not isinstance(citations, list) or not citations or any(not isinstance(c, str) or c not in allowed for c in citations):
        raise ValueError('Provider returned missing or invalid source references.')
