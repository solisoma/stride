from typing import Literal
from pydantic import BaseModel, Field


class ImageExtraction(BaseModel):
    kind: Literal['text', 'diagram', 'mixed', 'other', 'unreadable'] = Field(
        description='Classify readable text, explanatory diagram/chart, both, decorative image, or unreadable source')
    visible_text: str = Field(description='Exact visible text with useful line breaks; empty when there is none')
    diagram_explanation: str = Field(description='Explain visible diagram structure and relationships; empty for text-only, decorative, or unreadable images')
