"""
Feynman Cognitive Engine — Response Validator & Repair Module
"""

from typing import Dict, Any
from .schemas import TutorDocument
from .document_builder import DocumentBuilder

class ResponseValidator:
    @staticmethod
    def validate_and_repair(data: Dict[str, Any], default_mastery: int = 0) -> TutorDocument:
        """
        Validates contract response dictionary, repairs missing fields, and returns a TutorDocument model.
        """
        repaired = dict(data)
        repaired.setdefault("cognitive_trace", "Active recall model evaluation completed.")
        repaired.setdefault("simple_explanation", "")
        repaired.setdefault("why_it_works", "")
        repaired.setdefault("example", "")
        repaired.setdefault("common_mistake", "")
        repaired.setdefault("mini_quiz", "What is the core takeaway of this concept?")
        repaired.setdefault("reflection_prompt", "How would you explain this concept to a colleague?")
        repaired.setdefault("coach_recommendation", "Review core mechanics and practice active recall.")
        repaired.setdefault("visual_intuition", "")
        repaired.setdefault("next_learning_step", "Explore adjacent architectural topics")
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])
        
        return DocumentBuilder.create_document(repaired)
