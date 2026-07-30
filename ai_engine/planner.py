"""
Feynman Cognitive Engine — Learning Planner Module
Determines pedagogical strategy, difficulty, study style, and target objectives prior to prompt construction.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field

class LearningPlan(BaseModel):
    difficulty: str = Field(default="Intermediate")
    teaching_style: str = Field(default="FirstPrinciples")
    include_visualization: bool = Field(default=True)
    include_quiz: bool = Field(default=True)
    include_analogy: bool = Field(default=True)
    estimated_time: int = Field(default=4)
    target_objectives: List[str] = Field(default_factory=lambda: ["Master core concept mechanics", "Verify through active recall"])

class LearningPlanner:
    @staticmethod
    def plan(user_message: str, current_mastery: int, study_mode: str = "Focus") -> LearningPlan:
        """
        Analyzes student query and mastery history to formulate a targeted LearningPlan.
        """
        difficulty = "Beginner" if current_mastery < 30 else ("Advanced" if current_mastery > 75 else "Intermediate")
        
        # Adaptive teaching style selection
        user_msg_lower = user_message.lower()
        if "step by step" in user_msg_lower or "teach me" in user_msg_lower:
            teaching_style = "StepByStepIncremental (Provide 350-500 words breakdown across 3-4 numbered steps with a complete Mermaid diagram)"
            estimated_time = 8
        elif study_mode == "Exam":
            teaching_style = "RigorousProofAndEdgeCases"
            estimated_time = 6
        elif study_mode == "Interview":
            teaching_style = "SystemArchitectureAndComplexity"
            estimated_time = 5
        else:
            teaching_style = "FirstPrinciplesFeynman"
            estimated_time = 4

        return LearningPlan(
            difficulty=difficulty,
            teaching_style=teaching_style,
            include_visualization=True,
            include_quiz=True,
            include_analogy=True,
            estimated_time=estimated_time,
            target_objectives=[
                f"Explain '{user_message[:40]}' using first principles",
                "Identify common mental model pitfalls",
                "Assess retention via active recall mini quiz"
            ]
        )

learning_planner = LearningPlanner()
