"""
Feynman Cognitive Engine (FCE) Orchestrator
Manages prompt planning, LLM provider routing, document block generation, and fault-tolerant fallbacks.
"""

from typing import Dict, Any, List
from .planner import LearningPlanner, LearningPlan
from .prompt_builder import PromptBuilder
from .response_validator import ResponseValidator
from .document_builder import DocumentBuilder
from .schemas import TutorDocument
from .config import engine_config
from .providers.provider_factory import ProviderFactory

class FeynmanCognitiveEngine:
    def __init__(self, name: str = "Feynman Learning OS"):
        self.name = name

    def plan_learning_strategy(self, user_message: str, current_mastery: int, study_mode: str = "Focus") -> LearningPlan:
        """Stage 1: Formulate pedagogical LearningPlan strategy."""
        return LearningPlanner.plan(user_message, current_mastery, study_mode)

    def prepare_system_prompt(self, plan: LearningPlan, mistakes_text: str, context_text: str) -> str:
        """Stage 2: Build targeted system prompt instructions."""
        return PromptBuilder.build_system_prompt(plan, mistakes_text, context_text)

    def get_provider(self, provider_name: str = None):
        """Stage 3: Instantiate reasoning backend provider via ProviderFactory."""
        target_provider = provider_name or engine_config.provider_name
        return ProviderFactory.create(target_provider, engine_config.model_name)

    def validate_and_build_document(self, raw_data: Dict[str, Any], default_mastery: int = 0) -> TutorDocument:
        """Stage 4 & 5: Repair, validate contract fields, and return strongly-typed TutorDocument."""
        return ResponseValidator.validate_and_repair(raw_data, default_mastery)

    def build_document_blocks(self, tutor_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transforms flat contract response dictionary into a structured list of dict blocks.
        """
        blocks = DocumentBuilder.build_blocks(tutor_data)
        return [b.model_dump() for b in blocks]

    def get_fallback_document(self, user_message: str, current_mastery: int, sources: List[Any]) -> Dict[str, Any]:
        """
        Generates a 12-field structured fallback learning document if upstream API providers hit rate limits.
        """
        raw_data = {
            "cognitive_trace": "Active recall evaluation model active. Processing query context...",
            "simple_explanation": f"Here is the breakdown of your question: '{user_message}'. Recursion involves a function calling itself until a base case condition is met.",
            "why_it_works": "The call stack tracks each frame in memory until the base case halts execution and returns back up the call stack.",
            "example": "Like a set of nesting Russian dolls, where each doll represents a function call until you reach the smallest doll (base case).",
            "common_mistake": "Forgetting the base case, leading to stack overflow errors.",
            "mini_quiz": "What happens if a recursive function lacks a base case condition?",
            "reflection_prompt": "How would you implement this iteratively using a loop instead?",
            "coach_recommendation": "Focus on stack frame memory bounds and base case validation.",
            "visual_intuition": "graph TD;\n  f3[f(3)] --> f2[f(2)];\n  f2 --> f1[f(1) Base Case];",
            "next_learning_step": "Master stack bounds and memory efficiency",
            "estimated_study_time": 4,
            "mastery_score": min(100, current_mastery + 10),
            "sources": sources
        }
        doc = ResponseValidator.validate_and_repair(raw_data, current_mastery)
        return doc.model_dump()

feynman_engine = FeynmanCognitiveEngine()
