"""
Feynman Cognitive Engine (FCE) Orchestrator
Manages prompt planning, LLM provider routing, presentation strategy variation, and fault-tolerant document building.
"""

from typing import Dict, Any, List, Optional

from .planner import LearningPlanner, LearningPlan
from .prompt_builder import PromptBuilder
from .response_validator import ResponseValidator
from .document_builder import DocumentBuilder
from .schemas import TutorDocument
from .config import engine_config
from .providers.provider_factory import ProviderFactory
from .teaching_engine import (
    PresentationVariant,
    presentation_memory,
    generate_adaptive_diagram
)

class FeynmanCognitiveEngine:
    def __init__(self, name: str = "Feynman Learning OS"):
        self.name = name

    def plan_learning_strategy(self, user_message: str, current_mastery: int, study_mode: str = "Focus") -> LearningPlan:
        """Stage 1: Formulate pedagogical LearningPlan strategy."""
        return LearningPlanner.plan(user_message, current_mastery, study_mode)

    def prepare_system_prompt(
        self,
        plan: LearningPlan,
        mistakes_text: str,
        context_text: str,
        presentation_strategy: str = "INTUITION / MECHANISM"
    ) -> str:
        """Stage 2: Build targeted system prompt instructions with explicit presentation strategy."""
        return PromptBuilder.build_system_prompt(
            plan,
            mistakes_text,
            context_text,
            presentation_strategy=presentation_strategy
        )

    def get_provider(self, provider_name: str = None):
        """Stage 3: Instantiate reasoning backend provider via ProviderFactory."""
        target_provider = provider_name or engine_config.provider_name
        return ProviderFactory.create(target_provider, engine_config.model_name)

    def validate_and_build_document(
        self,
        raw_data: Dict[str, Any],
        default_mastery: int = 0,
        fallback_topic: Optional[str] = None,
        variant: Optional[PresentationVariant] = None
    ) -> TutorDocument:
        """Stage 4 & 5: Repair, validate contract fields, and return strongly-typed TutorDocument."""
        return ResponseValidator.validate_and_repair(
            raw_data,
            default_mastery,
            fallback_topic=fallback_topic,
            variant=variant
        )

    def build_document_blocks(self, tutor_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transforms flat contract response dictionary into a structured list of dict blocks.
        """
        blocks = DocumentBuilder.build_blocks(tutor_data)
        return [b.model_dump() for b in blocks]

    def get_fallback_document(
        self,
        user_message: str,
        current_mastery: int,
        sources: List[Any],
        session_topic: Optional[str] = None,
        variant: Optional[PresentationVariant] = None
    ) -> Dict[str, Any]:
        """
        Generates an intent-aware structured learning document if upstream API providers hit transient rate limits.
        Inherits session_topic when processing follow-up actions like Simplify, Analogy, or Step-by-Step.
        Adapts presentation variant dynamically to prevent repetitive responses on repeated questions.
        """
        from .response_validator import (
            extract_canonical_topic,
            synthesize_standard_lesson,
            synthesize_analogy_lesson,
            synthesize_simplify_lesson,
            synthesize_step_by_step_lesson
        )
        canonical_topic = extract_canonical_topic(user_message, fallback_topic=session_topic)
        chosen_variant = variant or PresentationVariant.ARCHITECTURE

        import re
        msg_lower = user_message.lower()
        is_step_by_step = bool(re.search(r'\b(teach me\s+.*?\s*step by step|teach me step by step|step[- ]by[- ]step)\b', msg_lower))
        is_simplify = bool(re.search(r'\b(explain\s+.*?\s*simply|explain this simply|explain simply|simplify|even simpler|in simple terms|eli5)\b', msg_lower))
        is_analogy = bool(re.search(r'\b(give\s+.*?\s*analogy|real[- ]world analogy|analogy for|explain with an analogy)\b', msg_lower))

        if is_step_by_step:
            synth = synthesize_step_by_step_lesson(canonical_topic)
            mode = "STEP_BY_STEP"
        elif is_simplify:
            synth = synthesize_simplify_lesson(canonical_topic)
            mode = "SIMPLIFY"
        elif is_analogy:
            synth = synthesize_analogy_lesson(canonical_topic)
            mode = "ANALOGY"
        else:
            synth = synthesize_standard_lesson(canonical_topic, variant=chosen_variant)
            mode = "STANDARD"

        raw_data = {
            "cognitive_trace": f"{mode} lesson active for {canonical_topic} ({chosen_variant.value}).",
            "lesson_mode": mode,
            "canonical_topic": canonical_topic,
            "simple_explanation": synth["simple_explanation"],
            "why_it_works": synth["why_it_works"],
            "example": synth["example"],
            "common_mistake": synth["common_mistake"],
            "mini_quiz": synth["mini_quiz"],
            "reflection_prompt": synth["reflection_prompt"],
            "coach_recommendation": synth["coach_recommendation"],
            "visual_intuition": synth.get("visual_intuition", ""),
            "next_learning_step": synth["next_learning_step"],
            "estimated_study_time": 4,
            "mastery_score": min(100, current_mastery + 10),
            "sources": sources
        }

        doc = ResponseValidator.validate_and_repair(
            raw_data,
            current_mastery,
            fallback_topic=canonical_topic,
            variant=chosen_variant
        )
        return doc.model_dump()


feynman_engine = FeynmanCognitiveEngine()
