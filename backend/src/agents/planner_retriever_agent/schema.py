"""
Schema for PlannerRetrieverAgent output
Combines course info (title, description) with learning path (chapters)
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Chapter(BaseModel):
    caption: str = Field(
        description="Short caption of the chapter. Optimally 1-5 words"
    )
    content: List[str] = Field(
        description="Content of the chapter. Each element should be a specific learning point (one bullet point/sentence)"
    )
    time: int = Field(
        description="Time of the chapter in minutes"
    )
    note: Optional[str] = Field(
        default=None,
        description="Optional additional context or prerequisites for the explainer agent"
    )


class CourseInfoWithPath(BaseModel):
    """
    Combined output schema: Course information + Learning path
    """
    title: str = Field(
        description="Short, catchy title for the course (1-2 sentences max)"
    )
    description: str = Field(
        description="Brief overview of what the course covers (1-2 sentences)"
    )
    chapters: List[Chapter] = Field(
        description="List of chapters forming the learning path"
    )
