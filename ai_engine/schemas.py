"""
Feynman Cognitive Engine — Pydantic Document Schemas
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

class LessonMode(str, Enum):
    STANDARD = "STANDARD"
    SIMPLIFY = "SIMPLIFY"
    ANALOGY = "ANALOGY"
    STEP_BY_STEP = "STEP_BY_STEP"

class DocumentBlock(BaseModel):
    type: str = Field(description="Block type identifier e.g. summary, mechanics, mental_model, visualization, quiz, references")
    content: Any = Field(description="Block payload content string or object")

class TutorDocument(BaseModel):
    schema_version: int = Field(default=2, description="Versioned document schema identifier")
    document_type: str = Field(default="learning_document", description="Document type tag")
    lesson_mode: LessonMode = Field(default=LessonMode.STANDARD, description="Pedagogical mode enum: STANDARD, SIMPLIFY, ANALOGY, STEP_BY_STEP")
    cognitive_trace: str
    simple_explanation: str
    why_it_works: str
    example: str
    common_mistake: str
    mini_quiz: str
    reflection_prompt: str
    coach_recommendation: str
    visual_intuition: str
    next_learning_step: str
    estimated_study_time: int
    mastery_score: int
    sources: List[Any] = Field(default_factory=list)
    blocks: List[DocumentBlock] = Field(default_factory=list)
