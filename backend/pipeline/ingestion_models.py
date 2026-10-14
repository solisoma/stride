from pydantic import BaseModel, Field
from typing import List, Optional

class Branch(BaseModel):
    header: str = Field(description="The heading or title of this section")
    summary: str = Field(description="A brief summary of the content within this branch")
    content: Optional[str] = Field(default=None, description="The raw text content of this section")
    parent: Optional["Branch"] = Field(default=None, description="The parent branch, if this is a subsection")
    children: Optional[List["Branch"]] = Field(default_factory=list, description="Subsections nested under this branch")
    page_number: Optional[int] = Field(default=None, description="The physical page number where this branch starts")
    document_id: Optional[str] = Field(default=None, description="Unique ID for the file")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata (e.g. timestamps for media)")
    
Branch.model_rebuild()

class SplitSection(BaseModel):
    header: str = Field(description="The heading or title of this section")
    content: str = Field(description="The raw text content of this section")

class SplitSectionList(BaseModel):
    sections: List[SplitSection]

class ClusterAssignment(BaseModel):
    cluster_name: str = Field(description="A concise, descriptive name for this semantic cluster")
    child_indices: List[int] = Field(description="0-based indices of the children that belong to this cluster")

class ClusteringResponse(BaseModel):
    clusters: List[ClusterAssignment] = Field(
        description="The grouped clusters. Each child index must appear in exactly one cluster."
    )

class WordBoundary(BaseModel):
    header: str = Field(description='Short title for this section')
    start_word: int = Field(description='Zero-based numbered word where the section starts')


class WordBoundaryList(BaseModel):
    sections: list[WordBoundary]
