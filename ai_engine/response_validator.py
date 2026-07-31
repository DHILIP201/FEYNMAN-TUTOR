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
        exp_lower = (explanation + " " + why + " " + example).lower()

        # Deterministic Topic Visual Engine
        if not viz or ("graph " not in viz and "flowchart " not in viz) or "Input Layer" in viz or "Hidden Processing Layers" in viz or "Fallback" in viz:
            if "neural" in exp_lower or "deep learning" in exp_lower or "perceptron" in exp_lower:
                viz = "graph TD;\n  Img[Input Features] --> W[Weighted Sum & Bias];\n  W --> Act[Activation Function];\n  Act --> Out[Prediction Output];"
            elif "binary search" in exp_lower or "search algorithm" in exp_lower:
                viz = "graph TD;\n  Arr[Sorted Array] --> Mid[Find Mid Element];\n  Mid --> Comp{Is Mid == Target?};\n  Comp -->|Smaller| Left[Search Left Half];\n  Comp -->|Larger| Right[Search Right Half];"
            elif "tcp" in exp_lower or "handshake" in exp_lower or "packet" in exp_lower:
                viz = "graph TD;\n  Client[Client] -->|1. SYN| Server[Server];\n  Server -->|2. SYN-ACK| Client;\n  Client -->|3. ACK| Server;"
            elif "recursion" in exp_lower or "tree" in exp_lower:
                viz = "graph TD;\n  Call[Function Call] --> Base{Base Case Met?};\n  Base -->|No| Recurse[Recursive Call];\n  Base -->|Yes| Return[Return Base Value];"
            elif "sql" in exp_lower or "join" in exp_lower or "database" in exp_lower:
                viz = "graph TD;\n  T1[Table A] --> Join[JOIN Key Match];\n  T2[Table B] --> Join;\n  Join --> Res[Combined Result Set];"
            else:
                viz = f"graph TD;\n  Start[Input Context] --> Process[Socratic Breakdown & Mechanics];\n  Process --> Outcome[Mastered Concept];"
        repaired["visual_intuition"] = viz

        repaired.setdefault("next_learning_step", "Explore adjacent architectural topics")
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])

        print(f"[VALIDATOR] Response validated and structured with {len(explanation.split())} words.")
        return DocumentBuilder.create_document(repaired)
