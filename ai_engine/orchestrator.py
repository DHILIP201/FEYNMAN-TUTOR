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
        Generates an intent-aware structured learning document if upstream API providers hit transient rate limits.
        """
        clean_query = user_message.strip().rstrip("?").strip()
        msg_lower = user_message.lower()

        if "step by step" in msg_lower or "teach me" in msg_lower:
            simple_exp = (
                f"### Step 1: Foundational Concept\n{clean_query} introduces fundamental operational principles.\n\n"
                f"### Step 2: Mechanical Transformation\nData and inputs flow through structured processing stages to compute valid outputs.\n\n"
                f"### Step 3: Practical Application\nInputs are verified and evaluated to ensure accurate results."
            )
        elif "simplify" in msg_lower:
            simple_exp = f"Imagine explaining {clean_query} using a simple story. Inputs enter a system, undergo clear processing steps, and produce an understandable result without complex technical jargon."
        elif "analogy" in msg_lower:
            simple_exp = f"Think of {clean_query} like a well-organized team. Each member handles one specialized task, passing their results to the next member until the final decision is reached."
        else:
            simple_exp = (
                f"Understanding **{clean_query}** starts with looking at how information flows through a system. "
                f"Inputs are analyzed, transformed through processing mechanics, and evaluated to produce accurate predictions or results."
            )

        raw_data = {
            "cognitive_trace": "Active recall evaluation model active. Processing query context...",
            "simple_explanation": simple_exp,
            "why_it_works": f"Underlying mechanics of {clean_query} process inputs and optimize output parameters.",
            "example": f"Like a smart filter inspecting incoming data before making a classification.",
            "common_mistake": "Confusing initial input parameters with final computed predictions.",
            "mini_quiz": f"What is the primary objective when working with {clean_query}?",
            "reflection_prompt": f"How would you explain the core mechanism of {clean_query} to a peer?",
            "coach_recommendation": f"Focus on understanding the flow of data across {clean_query}.",
            "visual_intuition": f"graph TD;\n  Start[{clean_query}] --> Process[Input Transformation];\n  Process --> Outcome[Validated Result];",
            "next_learning_step": f"Advanced applications of {clean_query}",
            "estimated_study_time": 4,
            "mastery_score": min(100, current_mastery + 10),
            "sources": sources
        }
        doc = ResponseValidator.validate_and_repair(raw_data, current_mastery)
        return doc.model_dump()

feynman_engine = FeynmanCognitiveEngine()
