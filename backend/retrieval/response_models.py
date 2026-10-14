from pydantic import BaseModel, Field


class PageCitation(BaseModel):
    document_id: str
    page_number: int | str
    exact_quote: str


class ResearchResponse(BaseModel):
    narrative_summary: str = Field(description='Evidence-based learning explanation')
    all_citations: list[PageCitation]
