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
        from .response_validator import extract_canonical_topic
        canonical_topic = extract_canonical_topic(user_message)
        msg_lower = user_message.lower()

        if "step by step" in msg_lower or "teach me" in msg_lower:
            simple_exp = (
                f"### Step 1 — Core Foundation of {canonical_topic}\n"
                f"{canonical_topic} begins by establishing how raw inputs enter the system and what problem it solves. Understanding the primary objective before diving into mechanics ensures a solid mental foundation.\n\n"
                f"> 🎯 **Step 1 Checkpoint:** Before moving on, can you identify what the primary input to {canonical_topic} represents?\n\n"
                f"### Step 2 — Information Flow and Mechanics\n"
                f"Data and signals move through intermediate stages, each applying mathematical or algorithmic transformations. Each layer or operation refines the data to extract patterns or sort elements.\n\n"
                f"> 🎯 **Step 2 Checkpoint:** What transformation happens to the data between the initial input and intermediate stages?\n\n"
                f"### Step 3 — Decision Rules & Output Calculation\n"
                f"Once intermediate representations are computed, decision rules (such as threshold activation functions or base cases) determine the final output prediction or result.\n\n"
                f"> 🎯 **Step 3 Checkpoint:** How does the system decide whether an output meets the required threshold?\n\n"
                f"### Step 4 — Feedback & Complete System Integration\n"
                f"Finally, feedback mechanisms (such as error loss calculation or recursive unwinding) optimize parameters so future iterations become faster and more accurate.\n\n"
                f"> 🎯 **Step 4 Checkpoint:** How does feedback adjust internal parameters to improve accuracy over time?"
            )
            mode = "STEP_BY_STEP"
        elif "simplify" in msg_lower or "simpler" in msg_lower or "simple" in msg_lower:
            simple_exp = (
                f"Imagine {canonical_topic} as a simple filter. Raw information goes in, "
                f"gets organized according to simple rules, and produces a clear, accurate result without unnecessary complexity."
            )
            mode = "SIMPLIFY"
        elif "analogy" in msg_lower:
            simple_exp = (
                f"Think of {canonical_topic} like a well-coordinated restaurant kitchen. "
                f"Each chef handles one specialized task (prepping, cooking, plating) and passes the dish to the next station until the final meal is served."
            )
            mode = "ANALOGY"
        else:
            simple_exp = (
                f"Understanding **{canonical_topic}** starts with examining how information flows through the system. "
                f"Inputs are analyzed, transformed through underlying algorithmic mechanics, and evaluated to produce reliable predictions or verified results."
            )
            mode = "STANDARD"

        raw_data = {
            "cognitive_trace": f"Active recall evaluation model active. Processing {canonical_topic} context...",
            "lesson_mode": mode,
            "canonical_topic": canonical_topic,
            "simple_explanation": simple_exp,
            "why_it_works": f"Underlying mechanics of {canonical_topic} process structured parameters and optimize output states.",
            "example": f"Like a smart classifier inspecting incoming data packets before making a routing decision.",
            "common_mistake": f"Confusing initial input parameters with computed output states.",
            "mini_quiz": f"What is the primary objective when working with {canonical_topic}?",
            "reflection_prompt": f"How would you explain the core mechanism of {canonical_topic} to a peer?",
            "coach_recommendation": f"Focus on understanding the flow of data across {canonical_topic}.",
            "visual_intuition": "",
            "next_learning_step": f"Advanced applications of {canonical_topic}",
            "estimated_study_time": 4,
            "mastery_score": min(100, current_mastery + 10),
            "sources": sources
        }
        doc = ResponseValidator.validate_and_repair(raw_data, current_mastery)
        return doc.model_dump()

feynman_engine = FeynmanCognitiveEngine()

