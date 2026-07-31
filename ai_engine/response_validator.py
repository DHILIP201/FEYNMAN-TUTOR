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
        Validates contract response dictionary and preserves natural Gemini educational explanations.
        """
        repaired = dict(data)
        repaired.setdefault("cognitive_trace", "Active recall model evaluation completed.")
        
        explanation = repaired.get("simple_explanation", "").strip()
        why = repaired.get("why_it_works", "").strip()
        example = repaired.get("example", "").strip()

        # If simple_explanation is empty, fallback to why_it_works or example
        if not explanation:
            explanation = why or example or "Key concept breakdown."

        repaired["simple_explanation"] = explanation
        repaired.setdefault("why_it_works", why or "Underlying conceptual mechanics.")
        repaired.setdefault("example", example or "Illustrative real-world example.")
        repaired.setdefault("common_mistake", "Confusing foundational parameters with output predictions.")
        repaired.setdefault("mini_quiz", "What is the primary takeaway of this concept?")
        repaired.setdefault("reflection_prompt", "How would you explain this step to a peer?")
        repaired.setdefault("coach_recommendation", "Review core mechanics and practice active recall.")
        
        viz = repaired.get("visual_intuition", "").strip()
        if not viz or ("graph " not in viz and "flowchart " not in viz):
            topic_label = "Concept Workflow"
            viz = f"graph TD;\n  Start[{topic_label}] --> Process[Mechanics & Transformations];\n  Process --> Outcome[Mastered Outcome];"
        repaired["visual_intuition"] = viz

        repaired.setdefault("next_learning_step", "Explore adjacent architectural topics")
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])

        print(f"[VALIDATOR] Response validated and structured with {len(explanation.split())} words.")
        return DocumentBuilder.create_document(repaired)
