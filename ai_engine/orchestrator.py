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
        variant: Optional[PresentationVariant] = None,
        pdf_context: Optional[Any] = None
    ) -> TutorDocument:
        """Stage 4 & 5: Repair, validate contract fields, and return strongly-typed TutorDocument."""
        return ResponseValidator.validate_and_repair(
            raw_data,
            default_mastery,
            fallback_topic=fallback_topic,
            variant=variant,
            pdf_context=pdf_context
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
        variant: Optional[PresentationVariant] = None,
        pdf_context: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Generates an intent-aware structured learning document if upstream API providers hit transient rate limits.
        Inherits session_topic when processing follow-up actions like Simplify, Analogy, or Step-by-Step.
        Adapts presentation variant dynamically to prevent repetitive responses on repeated questions.
        Strictly prioritizes uploaded PDF material when an active document exists.
        """
        from .response_validator import (
            extract_canonical_topic,
            extract_candidate_topics_from_pdf,
            get_prerequisite_next_step,
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

        # Check if query is asking for information not supported in the active PDF
        available_pdf_topics = extract_candidate_topics_from_pdf(pdf_context) if pdf_context else []
        is_unsupported_pdf_query = False
        if pdf_context and available_pdf_topics:
            pdf_ctx_str = str(pdf_context).lower()
            topic_clean = canonical_topic.lower()
            has_topic_match = (
                topic_clean in pdf_ctx_str or
                any(t.lower() in topic_clean or topic_clean in t.lower() for t in available_pdf_topics)
            )
            if not has_topic_match:
                is_unsupported_pdf_query = True

        if is_unsupported_pdf_query:
            topics_summary = ", ".join(available_pdf_topics[:3]) if available_pdf_topics else "other concepts in your notes"
            mode = "STANDARD"
            synth = {
                "canonical_topic": canonical_topic,
                "simple_explanation": f"I couldn't find enough information about **{canonical_topic}** in your uploaded study material. Your uploaded document covers {topics_summary}.",
                "why_it_works": "Feynman AI prioritizes your uploaded study material as the authoritative knowledge source for this session.",
                "example": f"Try asking about {available_pdf_topics[0] if available_pdf_topics else 'a concept from your document'}.",
                "common_mistake": "Assuming concepts from outside documents are covered in this specific file.",
                "mini_quiz": f"Would you like to explore {available_pdf_topics[0] if available_pdf_topics else 'a topic from your file'} instead?",
                "reflection_prompt": "Which section of your uploaded study material would you like to focus on next?",
                "coach_recommendation": f"Focus your study session on the core concepts present in your uploaded document: {topics_summary}.",
                "next_learning_step": f"From your uploaded material, study {available_pdf_topics[0]} next." if available_pdf_topics else "Continue exploring your uploaded study material.",
                "visual_intuition": 'graph TD;\n  Doc["Uploaded Document"] --> Scope["Active Material Scope"];\n  Scope --> Next["Explore Document Topics"];'
            }
        elif is_step_by_step:
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
            variant=chosen_variant,
            pdf_context=pdf_context
        )
        return doc.model_dump()


feynman_engine = FeynmanCognitiveEngine()
