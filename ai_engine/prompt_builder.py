"""
Feynman Cognitive Engine — Prompt Builder Module
Assembles system instructions, study modes, student misconceptions, presentation strategy, and RAG contexts from a LearningPlan.
"""

from .prompts import FEYNMAN_COGNITIVE_SYSTEM_PROMPT
from .planner import LearningPlan

class PromptBuilder:
    @staticmethod
    def build_system_prompt(
        plan: LearningPlan,
        mistakes_text: str,
        context_text: str,
        presentation_strategy: str = "INTUITION / MECHANISM"
    ) -> str:
        study_mode_formatted = f"{plan.teaching_style} (Difficulty: {plan.difficulty})"
        return FEYNMAN_COGNITIVE_SYSTEM_PROMPT.format(
            study_mode=study_mode_formatted,
            presentation_strategy=presentation_strategy or "INTUITION / MECHANISM",
            mistakes_text=mistakes_text or "None recorded yet.",
            context_text=context_text or "No external PDF context retrieved."
        )
