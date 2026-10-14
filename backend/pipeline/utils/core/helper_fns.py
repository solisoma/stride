from pipeline.ingestion_models import Branch

def serialize_branch(node: Branch) -> dict:
    """Serialize a Branch to JSON-safe dict, excluding circular parent refs."""
    return {
        "header": node.header,
        "summary": node.summary,
        "content": node.content,
        "page_number": node.page_number,
        "document_id": node.document_id,
        "metadata": node.metadata,
        "children": [serialize_branch(c) for c in (node.children or [])],
    }

def deserialize_branch(data: dict) -> Branch:
    """Reconstruct a Branch tree from a serialized dict and wire parent links."""
    children = [deserialize_branch(c) for c in data.get("children", [])]
    node = Branch(
        header=data["header"],
        summary=data.get("summary", ""),
        content=data.get("content"),
        page_number=data.get("page_number"),
        document_id=data.get("document_id"),
        metadata=data.get("metadata", {}),
        children=children,
    )

    for child in children:
        child.parent = node
    return node
