from pydantic import BaseModel, Field
from typing import List, Literal


class ChildDecision(BaseModel):
    index: int = Field(
        description="The 0-based index of the relevant child in the children list"
    )
    action: Literal["ANSWER", "DRILL"] = Field(
        description=(
            "ANSWER if the child's summary is sufficient to answer the query. "
            "DRILL if the summary hints at relevance but we need to go deeper into its children."
        )
    )


class RouterResponse(BaseModel):
    relevant_children: List[ChildDecision] = Field(
        description=(
            "Only include children that are relevant to the query. "
            "Omit irrelevant children entirely. Return an empty list if nothing is relevant."
        )
    )
