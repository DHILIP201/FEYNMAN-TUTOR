"""
ai_engine/teaching_engine.py
=============================
Universal Feynman AI Teaching Engine & Explanation-Variation System.

A subject-agnostic, adaptive pedagogical reasoning engine designed to:
1. Infer the domain archetype and optimal mental models for ANY academic or technical concept.
2. Select complementary presentation strategies (ARCHITECTURE, MECHANISM, PROCESS, CAUSE_AND_EFFECT,
   INTUITION, APPLICATION, WORKED_EXAMPLE, TRAINING_CYCLE, COMPARISON).
3. Maintain bounded presentation memory per (user_id, canonical_topic) so repeated queries
   deliver fresh, high-value pedagogical angles and distinct diagrams rather than identical templates.
4. Adapt visual structures (Cycles, Pipelines, Trees, Timelines, State Transitions, Decision Trees)
   using clean, valid Mermaid SVG diagrams without relying on hardcoded topic branches.
"""

import re
import json
import hashlib
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple


class PresentationVariant(str, Enum):
    INTUITION = "INTUITION"               # High-level mental model, geometric/physical intuition
    MECHANISM = "MECHANISM"               # Mathematical/internal transformations, operations, rules
    PROCESS = "PROCESS"                   # Chronological progression, step-by-step lifecycle, timeline
    CAUSE_AND_EFFECT = "CAUSE_AND_EFFECT" # Drivers, stimulus-response, feedback loops, equilibrium
    ARCHITECTURE = "ARCHITECTURE"         # Structural subsystems, components, layers, inputs/outputs
    WORKED_EXAMPLE = "WORKED_EXAMPLE"     # Concrete problem walkthrough, practical numbers/cases
    TRAINING_CYCLE = "TRAINING_CYCLE"     # Forward pass, error measurement, correction/optimization
    COMPARISON = "COMPARISON"             # Contrasting with alternatives, trade-offs, paradigms
    APPLICATION = "APPLICATION"           # Real-world system, industrial usage, engineering constraints


class DomainArchetype(str, Enum):
    MATHEMATICS = "MATHEMATICS"           # Calculus, linear algebra, probability, discrete math
    PHYSICS = "PHYSICS"                   # Mechanics, electromagnetism, thermodynamics, quantum
    COMPUTER_SCIENCE = "COMPUTER_SCIENCE" # Algorithms, architectures, distributed systems, AI/ML
    BIOLOGY = "BIOLOGY"                   # Genetics, cellular processes, physiology, ecology
    CHEMISTRY = "CHEMISTRY"               # Reactions, bonding, thermodynamics, molecular structure
    ECONOMICS_BUSINESS = "ECONOMICS"      # Markets, fiscal policy, micro/macro, finance, trade
    HUMANITIES_HISTORY = "HUMANITIES"     # History, philosophy, governance, social science
    GENERAL_ENGINEERING = "ENGINEERING"   # Mechanical, electrical, civil, systems engineering
    GENERAL = "GENERAL"                   # Broad academic and everyday educational concepts


# ─────────────────────────────────────────────────────────────────────────────
# 1. DOMAIN INFERENCE ENGINE (Subject-Agnostic Keyword & Semantic Classifier)
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_PATTERNS = [
    (DomainArchetype.MATHEMATICS, [
        r'\b(derivative\w*|integral\w*|calculus|matri\w*|eigenvalue\w*|eigenvector\w*|limit\w*|slope\w*|tangent\w*|probabilit\w*|distribution\w*|bayes\w*|vector\w*|linear algebra|differential\w*|equation\w*|fourier\w*|geometr\w*|trigonometr\w*|polynomial\w*|logarithm\w*|proof\w*)\b'
    ]),
    (DomainArchetype.PHYSICS, [
        r'\b(newton\w*|force\w*|acceleration\w*|gravit\w*|momentum|thermodynamic\w*|entropy|quantum\w*|electromagnet\w*|maxwell\w*|optic\w*|relativit\w*|doppler\w*|energy conservation|kinetic|potential|wave\w*|friction|fluid dynamics|circuit\w*|voltage|current|magnetic\w*)\b'
    ]),
    (DomainArchetype.COMPUTER_SCIENCE, [
        r'\b(neural network\w*|cnn\w*|transformer\w*|backpropagation|binary search|merge sort|quicksort|hash table\w*|linked list\w*|heap\w*|graph\w*|algorithm\w*|recursion|tree\w*|operating system\w*|deadlock\w*|semaphore\w*|memory|tcp|ip|udp|packet\w*|socket\w*|database\w*|normalization|sql|b-tree|compiler\w*|thread\w*|concurrency|process\w*|cache\w*)\b'
    ]),
    (DomainArchetype.BIOLOGY, [
        r'\b(photosynthe\w*|cellular respiration|dna|rna|transcription|translation|mitosis|meiosis|enzyme\w*|protein synthesis|chloroplast\w*|mitochondri\w*|atp|krebs\w*|genetic\w*|mutation\w*|evolution\w*|immune\w*|neuron\w*|synapse\w*|ecosystem\w*|homeostasis)\b'
    ]),
    (DomainArchetype.CHEMISTRY, [
        r'\b(chemical bond\w*|bond\w*|covalent|ionic|hydrogen bond\w*|periodic table|electronegativit\w*|acid\w*|base\w*|ph\b|equilibrium|le chatelier\w*|thermodynamic\w*|enthalpy|gibbs|stoichiometr\w*|orbital\w*|redox|oxidation|reduction|catalyst\w*|kinetic\w*)\b'
    ]),
    (DomainArchetype.ECONOMICS_BUSINESS, [
        r'\b(supply and demand|demand\w*|suppl\w*|inflation\w*|gdp|monetary policy|fiscal policy|interest rate\w*|elasticit\w*|opportunity cost\w*|marginal utility|monopol\w*|oligopol\w*|market equilibrium|liquidit\w*|trade deficit\w*|comparative advantage)\b'
    ]),
    (DomainArchetype.HUMANITIES_HISTORY, [
        r'\b(industrial revolution|renaissance|enlightenment|french revolution|cold war|scientific method|democrac\w*|separation of powers|social contract|feudalism|globalization|silk road|reformation)\b'
    ]),
]


def infer_domain_archetype(topic: str, context_text: str = "") -> DomainArchetype:
    """Infers the academic domain archetype from canonical topic and context."""
    search_text = f"{topic} {context_text}".lower()
    for archetype, patterns in DOMAIN_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, search_text, re.IGNORECASE):
                return archetype
    return DomainArchetype.GENERAL


# Strategy rotation orders based on domain archetype
DOMAIN_DEFAULT_STRATEGY_ROTATIONS: Dict[DomainArchetype, List[PresentationVariant]] = {
    DomainArchetype.MATHEMATICS: [
        PresentationVariant.INTUITION,
        PresentationVariant.MECHANISM,
        PresentationVariant.WORKED_EXAMPLE,
        PresentationVariant.APPLICATION,
        PresentationVariant.COMPARISON
    ],
    DomainArchetype.PHYSICS: [
        PresentationVariant.MECHANISM,
        PresentationVariant.INTUITION,
        PresentationVariant.CAUSE_AND_EFFECT,
        PresentationVariant.WORKED_EXAMPLE,
        PresentationVariant.APPLICATION
    ],
    DomainArchetype.COMPUTER_SCIENCE: [
        PresentationVariant.ARCHITECTURE,
        PresentationVariant.MECHANISM,
        PresentationVariant.TRAINING_CYCLE,
        PresentationVariant.PROCESS,
        PresentationVariant.INTUITION,
        PresentationVariant.APPLICATION
    ],
    DomainArchetype.BIOLOGY: [
        PresentationVariant.PROCESS,
        PresentationVariant.CAUSE_AND_EFFECT,
        PresentationVariant.ARCHITECTURE,
        PresentationVariant.INTUITION,
        PresentationVariant.COMPARISON
    ],
    DomainArchetype.CHEMISTRY: [
        PresentationVariant.MECHANISM,
        PresentationVariant.CAUSE_AND_EFFECT,
        PresentationVariant.PROCESS,
        PresentationVariant.INTUITION,
        PresentationVariant.WORKED_EXAMPLE
    ],
    DomainArchetype.ECONOMICS_BUSINESS: [
        PresentationVariant.CAUSE_AND_EFFECT,
        PresentationVariant.INTUITION,
        PresentationVariant.WORKED_EXAMPLE,
        PresentationVariant.APPLICATION,
        PresentationVariant.COMPARISON
    ],
    DomainArchetype.HUMANITIES_HISTORY: [
        PresentationVariant.PROCESS,
        PresentationVariant.CAUSE_AND_EFFECT,
        PresentationVariant.COMPARISON,
        PresentationVariant.INTUITION,
        PresentationVariant.APPLICATION
    ],
    DomainArchetype.GENERAL_ENGINEERING: [
        PresentationVariant.ARCHITECTURE,
        PresentationVariant.MECHANISM,
        PresentationVariant.WORKED_EXAMPLE,
        PresentationVariant.APPLICATION,
        PresentationVariant.CAUSE_AND_EFFECT
    ],
    DomainArchetype.GENERAL: [
        PresentationVariant.INTUITION,
        PresentationVariant.MECHANISM,
        PresentationVariant.PROCESS,
        PresentationVariant.APPLICATION,
        PresentationVariant.CAUSE_AND_EFFECT
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. BOUNDED PRESENTATION MEMORY (Avoids Repetitive Angles per User & Topic)
# ─────────────────────────────────────────────────────────────────────────────

class BoundedPresentationMemory:
    """
    Tracks recent presentation strategies and visual variants per (user_id, canonical_topic).
    Stored in memory with bounded size (last 5 variants per topic per user).
    """
    def __init__(self, max_history_per_topic: int = 5):
        self.max_history = max_history_per_topic
        # Map: "user_id:canonical_topic_lower" -> list of PresentationVariant
        self._history: Dict[str, List[PresentationVariant]] = {}

    def _get_key(self, user_id: Any, canonical_topic: str) -> str:
        clean_topic = canonical_topic.strip().lower()
        return f"{user_id}:{clean_topic}"

    def get_recent_variants(self, user_id: Any, canonical_topic: str) -> List[PresentationVariant]:
        key = self._get_key(user_id, canonical_topic)
        return list(self._history.get(key, []))

    def record_variant_used(self, user_id: Any, canonical_topic: str, variant: PresentationVariant):
        key = self._get_key(user_id, canonical_topic)
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(variant)
        if len(self._history[key]) > self.max_history:
            self._history[key].pop(0)

    def select_next_variant(
        self,
        user_id: Any,
        canonical_topic: str,
        lesson_mode: str = "STANDARD",
        context_text: str = ""
    ) -> PresentationVariant:
        """
        Selects the next optimal, non-repetitive presentation strategy for this user and topic.
        """
        domain = infer_domain_archetype(canonical_topic, context_text)
        rotation = DOMAIN_DEFAULT_STRATEGY_ROTATIONS.get(domain, DOMAIN_DEFAULT_STRATEGY_ROTATIONS[DomainArchetype.GENERAL])

        # Mode-specific priority constraints
        mode_upper = lesson_mode.upper()
        if mode_upper == "SIMPLIFY":
            return PresentationVariant.INTUITION
        elif mode_upper == "ANALOGY":
            return PresentationVariant.INTUITION
        elif mode_upper == "STEP_BY_STEP":
            return PresentationVariant.PROCESS

        recent = self.get_recent_variants(user_id, canonical_topic)
        if not recent:
            return rotation[0]

        # Find the first strategy in the domain rotation that has NOT been used in recent history
        for candidate in rotation:
            if candidate not in recent[-2:]:  # Avoid repeating the last 2 strategies
                return candidate

        # If all candidates recently used, cycle to the least recent one
        last_used = recent[-1]
        available = [s for s in rotation if s != last_used]
        return available[0] if available else rotation[0]


presentation_memory = BoundedPresentationMemory()


# ─────────────────────────────────────────────────────────────────────────────
# 3. UNIVERSAL DYNAMIC MERMAID GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

# Domain-specific canonical templates for rapid, reliable rendering
CANONICAL_VISUAL_TEMPLATES: Dict[Tuple[str, PresentationVariant], str] = {
    # ── Computer Science & AI ──
    ("neural network", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  In["Input Features"] --> InLayer["Input Layer (X)"];\n'
        '  InLayer --> Hidden["Hidden Layers (Weights + Bias)"];\n'
        '  Hidden --> Act["Non-Linear Activation (ReLU/Sigmoid)"];\n'
        '  Act --> OutLayer["Output Layer (Predictions)"];'
    ),
    ("neural network", PresentationVariant.TRAINING_CYCLE): (
        'graph TD;\n'
        '  Data["Input Batch"] --> Forward["Forward Pass Prediction"];\n'
        '  Forward --> Loss["Loss Calculation (Error L)"];\n'
        '  Loss --> Backprop["Backpropagation (Chain Rule Gradients)"];\n'
        '  Backprop --> Update["Optimizer (Weight Adjustment W - η∇L)"];\n'
        '  Update -.->|Next Epoch| Forward;'
    ),
    ("neural network", PresentationVariant.MECHANISM): (
        'graph LR;\n'
        '  Inputs["Inputs (x1, x2, ... xn)"] --> DotProd["Weighted Sum: Σ(wi·xi) + b"];\n'
        '  DotProd --> Activation["Activation Function: f(z)"];\n'
        '  Activation --> Output["Neuron Output: a"];'
    ),
    ("neural network", PresentationVariant.INTUITION): (
        'graph LR;\n'
        '  RawData["Raw Input Patterns"] --> Detectors["Feature Detectors"] --> Combiner["Layer Aggregation"] --> Decision["Recognized Concept"];'
    ),
    ("convolutional neural networks", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  Img["Input Image"] --> Conv["Convolution Filters"];\n'
        '  Conv --> Act["ReLU Activation"];\n'
        '  Act --> Pool["Max Pooling"];\n'
        '  Pool --> FC["Dense Layers"];\n'
        '  FC --> Class["Prediction"];'
    ),
    ("convolutional neural network", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  Img["Input Image"] --> Conv["Convolution Filters"];\n'
        '  Conv --> Act["ReLU Activation"];\n'
        '  Act --> Pool["Max Pooling"];\n'
        '  Pool --> FC["Dense Layers"];\n'
        '  FC --> Class["Prediction"];'
    ),
    ("cnn", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  Img["Input Image"] --> Conv["Convolution Filters"];\n'
        '  Conv --> Act["ReLU Activation"];\n'
        '  Act --> Pool["Max Pooling"];\n'
        '  Pool --> FC["Dense Layers"];\n'
        '  FC --> Class["Prediction"];'
    ),
    ("convolutional", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  Img["Input Image"] --> Conv["Convolution Filters"];\n'
        '  Conv --> Act["ReLU Activation"];\n'
        '  Act --> Pool["Max Pooling"];\n'
        '  Pool --> FC["Dense Layers"];\n'
        '  FC --> Class["Prediction"];'
    ),
    ("transformer", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  In["Tokens"] --> PE["Positional Encoding"];\n'
        '  PE --> Attn["Self-Attention"];\n'
        '  Attn --> AddNorm1["Add & Norm"];\n'
        '  AddNorm1 --> FFN["Feed-Forward"];\n'
        '  FFN --> AddNorm2["Add & Norm"];\n'
        '  AddNorm2 --> Out["Softmax Logits"];'
    ),
    ("backpropagation", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  Fwd["Forward Pass"] --> OutGrad["Output Loss"];\n'
        '  OutGrad --> Chain["Chain Rule"];\n'
        '  Chain --> HiddenGrad["Layer Gradients"];\n'
        '  HiddenGrad --> Optimizer["Optimizer Step"];\n'
        '  Optimizer --> Updated["Updated Weights"];'
    ),
    ("gradient descent", PresentationVariant.ARCHITECTURE): (
        'graph TD;\n'
        '  Init["Initialize"] --> Eval["Compute Gradient"];\n'
        '  Eval --> Step["Step Downhill"];\n'
        '  Step --> Check{"Converged?"};\n'
        '  Check -->|No| Eval;\n'
        '  Check -->|Yes| Converged["Optimal Minima"];'
    ),
    ("binary search", PresentationVariant.MECHANISM): (
        'graph TD;\n'
        '  Arr["Sorted Array [Low..High]"] --> Mid["Calculate Midpoint: (Low+High)/2"];\n'
        '  Mid --> Comp{"arr[Mid] == Target?"};\n'
        '  Comp -->|Target < Mid| Left["Set High = Mid - 1 (Search Left)"];\n'
        '  Comp -->|Target > Mid| Right["Set Low = Mid + 1 (Search Right)"];\n'
        '  Comp -->|Equal| Found["Target Found at Index Mid"];'
    ),
    ("binary search", PresentationVariant.INTUITION): (
        'graph LR;\n'
        '  N["N Elements"] --> Half["N/2 Elements (Discard 50%)"] --> Quarter["N/4 Elements (Discard 75%)"] --> One["1 Element Found: O(log N)"];'
    ),

    # ── Mathematics ──
    ("derivative", PresentationVariant.INTUITION): (
        'graph LR;\n'
        '  Secant["Secant Line (Δy / Δx)"] --> Limit["Take Limit as Δx → 0"] --> Tangent["Tangent Line Slope: f\'(x)"];'
    ),
    ("derivative", PresentationVariant.MECHANISM): (
        'graph TD;\n'
        '  Formula["Limit Definition: lim[h→0] (f(x+h) - f(x))/h"] --> Diff["Compute Difference Quotient"];\n'
        '  Diff --> Eval["Evaluate Infinitesimal Limit"];\n'
        '  Eval --> Rate["Instantaneous Rate of Change: dy/dx"];'
    ),
    ("matrix multiplication", PresentationVariant.MECHANISM): (
        'graph LR;\n'
        '  Row["Row i of Matrix A"] --> Dot["Dot Product Σ(Aik · Bkj)"] --> Col["Column j of Matrix B"];\n'
        '  Dot --> Cell["Result Element C(i,j)"];'
    ),

    # ── Physics ──
    ("newton's second law", PresentationVariant.MECHANISM): (
        'graph LR;\n'
        '  NetForce["Net Force Applied (ΣF)"] --> MassFactor["Divided by Mass (m)"] --> Acceleration["Resulting Acceleration (a = F/m)"];'
    ),
    ("newton's second law", PresentationVariant.CAUSE_AND_EFFECT): (
        'graph TD;\n'
        '  DoubleForce["2× Force with Constant Mass"] --> DoubleAcc["2× Acceleration (Linear Proportionality)"];\n'
        '  DoubleMass["2× Mass with Constant Force"] --> HalfAcc["½ Acceleration (Inverse Proportionality)"];'
    ),
    ("thermodynamics", PresentationVariant.PROCESS): (
        'graph TD;\n'
        '  HeatIn["Heat Added (Q)"] --> InternalEnergy["Change in Internal Energy (ΔU)"] --> WorkDone["Work Done by System (W)"];'
    ),

    # ── Biology ──
    ("photosynthesis", PresentationVariant.PROCESS): (
        'graph TD;\n'
        '  Light["Light + H2O"] --> Thylakoid["Light Reactions (Thylakoid)"];\n'
        '  Thylakoid --> Energy["ATP + NADPH (O2 Released)"];\n'
        '  Energy --> Calvin["Calvin Cycle (Stroma + CO2)"];\n'
        '  Calvin --> Glucose["Glucose (C6H12O6)"];'
    ),
    ("photosynthesis", PresentationVariant.CAUSE_AND_EFFECT): (
        'graph LR;\n'
        '  Photons["Sunlight Energy"] --> Chlorophyll["Chlorophyll Excitation"] --> ElectronFlow["Electron Transport Chain"] --> ChemicalBonds["Stable Chemical Energy in Sugar"];'
    ),
    ("cellular respiration", PresentationVariant.PROCESS): (
        'graph TD;\n'
        '  Glucose["Glucose (C6H12O6)"] --> Glycolysis["Glycolysis (Cytoplasm → 2 Pyruvate + 2 ATP)"];\n'
        '  Glycolysis --> Krebs["Krebs Cycle (Mitochondria Matrix → NADH/FADH2)"];\n'
        '  Krebs --> ETC["Electron Transport Chain (Inner Membrane → ~32 ATP + H2O)"];'
    ),

    # ── Chemistry ──
    ("chemical bonding", PresentationVariant.INTUITION): (
        'graph TD;\n'
        '  IsolatedAtoms["Unstable Isolated Atoms (High Energy)"] --> SharingOrTransfer["Electron Sharing or Transfer (Octet Rule)"];\n'
        '  SharingOrTransfer --> StableMolecules["Stable Low-Energy Bond (Attractive Equilibrium)"];'
    ),
    ("le chatelier's principle", PresentationVariant.CAUSE_AND_EFFECT): (
        'graph TD;\n'
        '  StressApplied["System Stress: Temperature / Pressure / Concentration"] --> CounterReaction["Equilibrium Shifts to Oppose Change"];\n'
        '  CounterReaction --> NewEquilibrium["Restored Dynamic Equilibrium State"];'
    ),

    # ── Economics ──
    ("supply and demand", PresentationVariant.CAUSE_AND_EFFECT): (
        'graph TD;\n'
        '  PriceHigh["Price > Equilibrium"] --> Surplus["Surplus Created (Supply > Demand)"] --> PriceFalls["Price Decreases to Eq"];\n'
        '  PriceLow["Price < Equilibrium"] --> Shortage["Shortage Created (Demand > Supply)"] --> PriceRises["Price Increases to Eq"];'
    ),
    ("inflation", PresentationVariant.MECHANISM): (
        'graph LR;\n'
        '  MoneySupply["Expansion of Money Supply / Rising Production Costs"] --> PurchasingPower["Decline in Purchasing Power per Currency Unit"] --> PriceLevel["Broad Increase in Overall Price Level"];'
    ),

    # ── History & Humanities ──
    ("industrial revolution", PresentationVariant.PROCESS): (
        'graph TD;\n'
        '  Agrarian["Agrarian Economy (Manual Labor)"] --> SteamPower["Steam Engine & Mechanization (1760s)"];\n'
        '  SteamPower --> FactorySystem["Factory System & Urbanization"];\n'
        '  FactorySystem --> MassProduction["Mass Production & Global Industrial Economy"];'
    ),
}


def generate_adaptive_diagram(
    canonical_topic: str,
    presentation_variant: PresentationVariant,
    lesson_mode: str = "STANDARD",
    explanation_text: str = ""
) -> str:
    """
    Generates a semantically accurate, valid Mermaid diagram suited to the canonical topic,
    selected presentation variant, and lesson mode.
    """
    topic_clean = canonical_topic.strip().lower()

    # Tier 1: Check canonical template registry for EXACT (topic, variant) match with highest specificity
    matching_templates = [
        (tpl_topic, tpl_variant, mermaid_code)
        for (tpl_topic, tpl_variant), mermaid_code in CANONICAL_VISUAL_TEMPLATES.items()
        if (tpl_topic in topic_clean or topic_clean in tpl_topic) and tpl_variant == presentation_variant
    ]
    if matching_templates:
        matching_templates.sort(key=lambda item: len(item[0]), reverse=True)
        return matching_templates[0][2]

    # Tier 2: Domain-driven semantic archetype synthesis
    domain = infer_domain_archetype(canonical_topic, explanation_text)
    t = canonical_topic.strip()

    if presentation_variant == PresentationVariant.INTUITION or lesson_mode == "SIMPLIFY":
        return f'graph LR;\n  Input["Familiar Starting Point"] --> Insight["{t} Mental Shift"] --> Understanding["Clear Conceptual Mastery"];'

    elif presentation_variant == PresentationVariant.CAUSE_AND_EFFECT:
        return f'graph TD;\n  Trigger["Stimulus / Input Change"] --> Mechanism["{t} Governing Principle"] --> Outcome["Observable Effect / Equilibrium"];'

    elif presentation_variant == PresentationVariant.PROCESS or lesson_mode == "STEP_BY_STEP":
        return f'graph TD;\n  Stage1["Stage 1: Initialization"] --> Stage2["Stage 2: {t} Core Action"] --> Stage3["Stage 3: Transformation"] --> Stage4["Stage 4: Verified Result"];'

    elif presentation_variant == PresentationVariant.ARCHITECTURE:
        return f'graph TD;\n  Inputs["Input Signals / Data"] --> CoreLayer["{t} Processing Architecture"] --> Subsystems["Internal Subcomponents"] --> Outputs["System Output"];'

    elif presentation_variant == PresentationVariant.WORKED_EXAMPLE:
        return f'graph LR;\n  Problem["Sample Problem Scenario"] --> Step1["Apply {t} Step 1"] --> Step2["Compute Step 2"] --> Solution["Final Solution Verified"];'

    elif presentation_variant == PresentationVariant.TRAINING_CYCLE:
        return f'graph TD;\n  Attempt["Initial Operation"] --> Evaluate["Measure Error / Difference"] --> Adjust["Tune {t} Parameters"] --> Improved["Refined Performance"];\n  Adjust -.->|Repeat Loop| Attempt;'

    elif presentation_variant == PresentationVariant.COMPARISON:
        return f'graph TD;\n  ApproachA["Alternative / Naive Approach"] -.->|Trade-Offs| Comparison["Comparison Criteria"];\n  ApproachB["{t} Optimized Approach"] --> Comparison --> Winner["Optimal Problem Resolution"];'

    else:
        # Default mechanism flowchart
        return f'graph LR;\n  Inputs["Initial Conditions"] --> Mechanism["{t} Dynamics"] --> Output["Predictable Outcome"];'
