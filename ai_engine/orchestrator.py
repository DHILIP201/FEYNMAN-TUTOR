"""
Feynman Cognitive Engine (FCE) Orchestrator
Manages prompt planning, LLM provider routing, document block generation, and fault-tolerant fallbacks.
"""

from typing import Dict, Any, List, Optional

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

    def validate_and_build_document(self, raw_data: Dict[str, Any], default_mastery: int = 0, fallback_topic: Optional[str] = None) -> TutorDocument:
        """Stage 4 & 5: Repair, validate contract fields, and return strongly-typed TutorDocument."""
        return ResponseValidator.validate_and_repair(raw_data, default_mastery, fallback_topic=fallback_topic)

    def build_document_blocks(self, tutor_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transforms flat contract response dictionary into a structured list of dict blocks.
        """
        blocks = DocumentBuilder.build_blocks(tutor_data)
        return [b.model_dump() for b in blocks]

    def get_fallback_document(self, user_message: str, current_mastery: int, sources: List[Any], session_topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates an intent-aware structured learning document if upstream API providers hit transient rate limits.
        Inherits session_topic when processing follow-up actions like Simplify, Analogy, or Step-by-Step.
        """
        from .response_validator import extract_canonical_topic, synthesize_standard_lesson
        canonical_topic = extract_canonical_topic(user_message, fallback_topic=session_topic)

        import re
        msg_lower = user_message.lower()
        is_step_by_step = bool(re.search(r'\b(teach me\s+.*?\s*step by step|teach me step by step|step[- ]by[- ]step)\b', msg_lower))
        is_simplify = bool(re.search(r'\b(explain\s+.*?\s*simply|explain this simply|explain simply|simplify|even simpler|in simple terms|eli5)\b', msg_lower))
        is_analogy = bool(re.search(r'\b(give\s+.*?\s*analogy|real[- ]world analogy|analogy for|explain with an analogy)\b', msg_lower))

        if is_step_by_step:
            simple_exp = (
                f"### Step 1 — Input Ingestion & Feature Representation\n"
                f"At the very beginning, {canonical_topic} ingests raw input signals or datasets and structures them into a well-defined numerical vector or state space. Every element represents a distinct measurable feature of the input domain.\n\n"
                f"*Concrete Example:* When processing an image, the input layer transforms a 2D pixel grid into a flattened 1D array of numerical brightness values normalized between 0.0 and 1.0.\n\n"
                f"> 🎯 **Step 1 Checkpoint:** Before moving to Step 2, what would happen if the input features were unnormalized or had missing values?\n\n"
                f"### Step 2 — Linear Transformations & Parameterized Weights\n"
                f"Signals pass into internal processing stages where each unit computes a weighted sum of all incoming connections and adds a bias offset ($z = \\mathbf{{w}}^T \\mathbf{{x}} + b$). The weights act as adjustable sensitivity dials that amplify critical patterns while suppressing irrelevant noise.\n\n"
                f"*Concrete Example:* If a feature strongly indicates an important pattern, its associated weight will be large and positive, driving the neuron's sum higher.\n\n"
                f"> 🎯 **Step 2 Checkpoint:** Why is the scalar bias term necessary in addition to the multiplying weights?\n\n"
                f"### Step 3 — Non-Linear Activation & Hierarchical Extraction\n"
                f"The pre-activation value is passed through a non-linear activation function (such as ReLU or Sigmoid). This introduces non-linearity, allowing the system to learn complex curved boundaries and abstract feature hierarchies across deeper layers.\n\n"
                f"*Concrete Example:* A ReLU function passes positive signals straight through while blocking negative noise by clamping them to zero.\n\n"
                f"> 🎯 **Step 3 Checkpoint:** What would happen to deep multi-layer architectures if all activation functions were purely linear?\n\n"
                f"### Step 4 — Prediction Formulation & Loss Quantification\n"
                f"The forward pass concludes at the output layer, formulating final predictions or classifications $\\hat{{y}}$. The model immediately evaluates its output against the ground truth $y$ using a Loss Function to quantify the exact prediction error.\n\n"
                f"*Concrete Example:* If the system outputs an incorrect confidence score, the loss function computes a high penalty value representing error magnitude.\n\n"
                f"> 🎯 **Step 4 Checkpoint:** How does the loss function mathematically measure how far the prediction is from the target?\n\n"
                f"### Step 5 — Backpropagation & Parameter Optimization\n"
                f"Using the multivariable calculus chain rule, the algorithm propagates error gradients backward from the output layer to the input layer. An optimization algorithm updates the parameters in the direction that minimizes loss ($w \\leftarrow w - \\eta \\frac{{\\partial L}}{{\\partial w}}$), completing the training iteration.\n\n"
                f"*Concrete Example:* If a specific weight caused a large error, its gradient will be steep, causing the optimizer to adjust it downward on the next cycle.\n\n"
                f"> 🎯 **Step 5 Checkpoint (Feynman Challenge):** In your own words, why must backpropagation occur in reverse order after forward propagation?"
            )
            mode = "STEP_BY_STEP"
            raw_data = {
                "cognitive_trace": f"Step-by-step 5-stage learning active for {canonical_topic}.",
                "lesson_mode": mode,
                "canonical_topic": canonical_topic,
                "simple_explanation": simple_exp,
                "why_it_works": f"Sequential 5-step breakdown isolates cognitive load across {canonical_topic}.",
                "example": f"Walking through input ingestion, parameter weighting, activation, loss evaluation, and gradient updates.",
                "common_mistake": f"Skipping intermediate validation checkpoints when studying {canonical_topic}.",
                "mini_quiz": f"Why does Step 3 require a non-linear activation function in {canonical_topic}?",
                "reflection_prompt": f"Can you summarize how all 5 steps of {canonical_topic} connect together in the full training cycle?",
                "coach_recommendation": f"Focus on how error signals in Step 5 directly refine the parameter weights introduced in Step 2.",
                "visual_intuition": "",
                "next_learning_step": f"Advanced architectural variations and optimization of {canonical_topic}",
                "estimated_study_time": 6,
                "mastery_score": min(100, current_mastery + 10),
                "sources": sources
            }
        elif is_simplify:
            simple_exp = (
                f"Imagine {canonical_topic} like a smart team of inspectors working together to solve a puzzle. "
                f"The first inspector looks at simple raw clues like colors and shapes. They pass their observations to the next inspector, "
                f"who combines those clues into bigger patterns. The final inspector looks at the combined evidence and makes a clear, confident decision. "
                f"Whenever the team makes a wrong guess, a coach tells them where they made a mistake, and each inspector adjusts how carefully they listen "
                f"to each other until their guesses become remarkably accurate."
            )
            mode = "SIMPLIFY"
            raw_data = {
                "cognitive_trace": f"Simplified intuitive breakdown active for {canonical_topic}.",
                "lesson_mode": mode,
                "canonical_topic": canonical_topic,
                "simple_explanation": simple_exp,
                "why_it_works": f"Simplifying {canonical_topic} removes heavy technical jargon while preserving the essential input-to-output flow.",
                "example": f"A team of inspectors refining clues until reaching a verified conclusion.",
                "common_mistake": f"Assuming {canonical_topic} requires complicated magic rather than simple collaborative adjustments.",
                "mini_quiz": f"In simple terms, how does the team in {canonical_topic} get better over time?",
                "reflection_prompt": f"How would you explain the team inspector idea of {canonical_topic} to a 10-year-old?",
                "coach_recommendation": f"Keep the intuitive picture of inspectors passing refined clues up the chain.",
                "visual_intuition": "",
                "next_learning_step": f"Exploring the technical machinery inside {canonical_topic}",
                "estimated_study_time": 2,
                "mastery_score": min(100, current_mastery + 10),
                "sources": sources
            }
        elif is_analogy:
            simple_exp = (
                f"Think of {canonical_topic} like a multi-station gourmet restaurant kitchen preparing complex dishes.\\n\\n"
                f"At Station 1 (the prep cooks), raw ingredients arrive—chopped, measured, and organized like raw input data. "
                f"At Station 2 (the line cooks), chefs combine ingredients, adjusting spices and heat according to exact recipes (these are the weights and biases). "
                f"At Station 3 (the head chef), dishes are tasted and evaluated against strict quality standards (the activation function) before being served to guests.\\n\\n"
                f"If a customer sends a dish back because it was too salty, the head chef traces the mistake backwards through the kitchen (backpropagation). "
                f"The head chef instructs the line cook to reduce the salt ratio on the next order (the weight update). Over hundreds of dinner services, "
                f"the kitchen staff refines their coordination until every meal comes out cooked to absolute perfection."
            )
            mode = "ANALOGY"
            raw_data = {
                "cognitive_trace": f"Real-world kitchen analogy active for {canonical_topic}.",
                "lesson_mode": mode,
                "canonical_topic": canonical_topic,
                "simple_explanation": simple_exp,
                "why_it_works": f"Physical kitchen analogies anchor abstract mechanics of {canonical_topic} in intuitive physical roles.",
                "example": f"A coordinated restaurant kitchen where dishes are prepared, tasted, and refined based on customer feedback.",
                "common_mistake": f"Focusing solely on the food rather than how feedback flows backward to adjust recipes.",
                "mini_quiz": f"In the kitchen analogy, what corresponds to the backpropagation step in {canonical_topic}?",
                "reflection_prompt": f"Can you create another real-world analogy for {canonical_topic} using music, sports, or manufacturing?",
                "coach_recommendation": f"Notice how customer feedback in the kitchen directly mirrors error loss minimization.",
                "visual_intuition": "",
                "next_learning_step": f"Connecting the kitchen analogy to mathematical implementations of {canonical_topic}",
                "estimated_study_time": 3,
                "mastery_score": min(100, current_mastery + 10),
                "sources": sources
            }

        else:
            synth = synthesize_standard_lesson(canonical_topic)
            mode = "STANDARD"
            raw_data = {
                "cognitive_trace": f"Standard master lesson active for {canonical_topic}.",
                "lesson_mode": mode,
                "canonical_topic": canonical_topic,
                "simple_explanation": synth["simple_explanation"],
                "why_it_works": synth["why_it_works"],
                "example": synth["example"],
                "common_mistake": synth["common_mistake"],
                "mini_quiz": synth["mini_quiz"],
                "reflection_prompt": synth["reflection_prompt"],
                "coach_recommendation": synth["coach_recommendation"],
                "visual_intuition": "",
                "next_learning_step": synth["next_learning_step"],
                "estimated_study_time": 4,
                "mastery_score": min(100, current_mastery + 10),
                "sources": sources
            }

        doc = ResponseValidator.validate_and_repair(raw_data, current_mastery, fallback_topic=canonical_topic)
        return doc.model_dump()


feynman_engine = FeynmanCognitiveEngine()

