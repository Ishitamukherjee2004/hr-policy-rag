from pydantic import BaseModel, Field
from typing import List
from typing import Literal



class Citation(BaseModel):
    document: str = Field(description="Exact title or filename of the policy document")
    section: str = Field(description="Exact section or subsection heading where the fact was found")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Employee's natural language HR question")


class AskResponse(BaseModel):
    answer: str = Field(description="Grounded answer based strictly on policy excerpts, or refusal message")
    citations: List[Citation] = Field(default_factory=list, description="List of sources backing the answer")
    grounded: bool = Field(description="True if answered from policies; False if refusing due to missing info")
    
class FeedbackRequest(BaseModel):
    question: str
    answer: str
    rating: Literal["up", "down"]
    citations: list[Citation] = []
    comment: str = ""