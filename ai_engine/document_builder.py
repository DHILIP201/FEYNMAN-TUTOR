"""
Feynman Cognitive Engine — Document Builder Module
Assembles typed TutorDocument instances and normalizes content blocks.
"""

from typing import Dict, Any, List
from .schemas import TutorDocument, DocumentBlock

class DocumentBuilder:
    @staticmethod
    def build_blocks(data: Dict[str, Any]) -> List[DocumentBlock]:
        blocks = []
        if data.get("simple_explanation"):
            blocks.append(DocumentBlock(type="summary", content=data["simple_explanation"]))
        if data.get("why_it_works"):
            blocks.append(DocumentBlock(type="mechanics", content=data["why_it_works"]))
        if data.get("example"):
            blocks.append(DocumentBlock(type="mental_model", content=data["example"]))
        if data.get("visual_intuition"):
            blocks.append(DocumentBlock(type="visualization", content=data["visual_intuition"]))
        if data.get("mini_quiz"):
            blocks.append(DocumentBlock(type="quiz", content=data["mini_quiz"]))
        if data.get("sources"):
            blocks.append(DocumentBlock(type="references", content=data["sources"]))
        return blocks

    @staticmethod
    def create_document(data: Dict[str, Any]) -> TutorDocument:
        blocks = DocumentBuilder.build_blocks(data)
        return TutorDocument(
            lesson_mode=data.get("lesson_mode", "STANDARD"),
            cognitive_trace=data.get("cognitive_trace", ""),
            simple_explanation=data.get("simple_explanation", ""),
            why_it_works=data.get("why_it_works", ""),
            example=data.get("example", ""),
            common_mistake=data.get("common_mistake", ""),
            mini_quiz=data.get("mini_quiz", ""),
            reflection_prompt=data.get("reflection_prompt", ""),
            coach_recommendation=data.get("coach_recommendation", ""),
            visual_intuition=data.get("visual_intuition", ""),
            next_learning_step=data.get("next_learning_step", ""),
            estimated_study_time=data.get("estimated_study_time", 4),
            mastery_score=data.get("mastery_score", 0),
            sources=data.get("sources", []),
            blocks=blocks
        )
