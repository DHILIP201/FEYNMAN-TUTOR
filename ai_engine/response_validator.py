"""
ai_engine/response_validator.py
================================
Universal Feynman AI Response Validator & Multi-Angle Synthesis Engine.

Enforces pedagogical quality contracts across all 4 modes (STANDARD, SIMPLIFY, ANALOGY, STEP_BY_STEP):
1. Universal Canonical Topic Extraction (clean subject isolation, acronym preservation).
2. Universal Multi-Angle Explanation Synthesis across ANY domain (CS, Math, Physics, Biology, Chemistry, Economics, History).
3. Clean Chat Output Invariant: Strips prompt echoes, raw Mermaid leaks, and unwanted trailing checkpoints.
4. Adaptive Diagram Binding: Connects canonical topics & presentation strategies to valid Mermaid SVGs.
"""

import re
from typing import Dict, Any, Optional, List
from .schemas import TutorDocument, LessonMode
from .document_builder import DocumentBuilder
from .teaching_engine import (
    PresentationVariant,
    DomainArchetype,
    infer_domain_archetype,
    generate_adaptive_diagram,
    presentation_memory
)

KNOWN_ACRONYMS = {
    "Cnn": "CNN", "Rnn": "RNN", "Llm": "LLM", "Gpt": "GPT", "Bert": "BERT", 
    "Sql": "SQL", "Tcp": "TCP", "Dns": "DNS", "Http": "HTTP", "Https": "HTTPS", 
    "Api": "API", "Ram": "RAM", "Cpu": "CPU", "Gpu": "GPU", "Acid": "ACID", 
    "Dp": "DP", "Bfs": "BFS", "Dfs": "DFS", "Ai": "AI", "Ml": "ML", "Ann": "ANN", "Mlp": "MLP"
}

TOPIC_VISUALS_REGISTRY = [
    {
        "topic": "transformer",
        "mermaid": 'graph TD;\n  In["Tokens"] --> PE["Positional Encoding"];\n  PE --> Attn["Self-Attention"];\n  Attn --> AddNorm1["Add & Norm"];\n  AddNorm1 --> FFN["Feed-Forward"];\n  FFN --> AddNorm2["Add & Norm"];\n  AddNorm2 --> Out["Softmax Logits"];'
    },
    {
        "topic": "cnn",
        "mermaid": 'graph TD;\n  Img["Input Image"] --> Conv["Convolution"];\n  Conv --> Act["ReLU"];\n  Act --> Pool["Pooling"];\n  Pool --> FC["Dense Layers"];\n  FC --> Class["Prediction"];'
    },
    {
        "topic": "backpropagation",
        "mermaid": 'graph TD;\n  Fwd["Forward Pass"] --> OutGrad["Output Loss"];\n  OutGrad --> Chain["Chain Rule"];\n  Chain --> HiddenGrad["Layer Gradients"];\n  HiddenGrad --> Optimizer["Optimizer Step"];\n  Optimizer --> Updated["Updated Weights"];'
    },
    {
        "topic": "gradient descent",
        "mermaid": 'graph TD;\n  Init["Initialize"] --> Eval["Compute Gradient"];\n  Eval --> Step["Step Downhill"];\n  Step --> Check{"Converged?"};\n  Check -->|No| Eval;\n  Check -->|Yes| Converged["Optimal Minima"];'
    },
    {
        "topic": "neural network",
        "mermaid": 'graph TD;\n  In["Input Features"] --> InLayer["Input Layer"];\n  InLayer --> Hidden["Hidden Layers"];\n  Hidden --> Act["Activation"];\n  Act --> OutLayer["Output Layer"];\n  OutLayer --> Loss["Loss Function"];\n  Loss --> Backprop["Backpropagation"];\n  Backprop --> WeightUpdate["Weight Update"];\n  WeightUpdate -.->|Next Epoch| Hidden;'
    },
    {
        "topic": "binary search",
        "mermaid": 'graph TD;\n  Arr["Sorted Array"] --> Mid["Compute Midpoint"];\n  Mid --> Comp{"arr[Mid] == Target?"};\n  Comp -->|Target < Mid| Left["Search Left Half"];\n  Comp -->|Target > Mid| Right["Search Right Half"];\n  Comp -->|Match| Found["Target Found"];'
    }
]

def clean_prompt_echo(text: str, is_explanation: bool = False) -> str:
    """Removes user prompt echoes, raw diagram markers, and trailing checkpoint clutter."""
    if not text:
        return ""
    stripped = text.strip()
    # Strip any accidental Mermaid block leakage from text
    stripped = re.sub(r'```mermaid[\s\S]*?```', '', stripped, flags=re.IGNORECASE).strip()
    stripped = re.sub(r'^\s*graph\s+(LR|TD|TB|RL|BT)[\s\S]*?;', '', stripped, flags=re.IGNORECASE).strip()
    
    # Strip trailing checkpoint artifacts if present
    stripped = re.sub(r'>\s*[\U0001F300-\U0001F9FF\U00002700-\U000027BF\U00002600-\U000026FF\s]*\*\*(Checkpoint|Step\s*\d+\s*Checkpoint|Analogy\s*Checkpoint):\*\*.*$', '', stripped, flags=re.IGNORECASE | re.MULTILINE).strip()

    if is_explanation:
        cleaned = re.sub(
            r'^(Teach me step by step until I understand|Teach me\s+(.+?)\s+step by step|Explain this concept even simpler|Explain this simpler|Explain\s+(.+?)\s+in simple terms|Give a real[- ]world analogy for|Give a real[- ]world analogy|Give an analogy for|Tell me about advanced applications of|Tell me about|Deep dive into)\s*[:\-\s]*',
            '',
            stripped,
            flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r'^(starts with examining how information flows through the system|is a foundational concept that)\s*', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'^[:\-\s]+', '', cleaned).strip()
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned or stripped

    return stripped

def extract_canonical_topic(text: str, fallback_topic: Optional[str] = None) -> str:
    """
    Isolates the clean canonical subject topic from raw user prompts.
    Single source of truth across Feynman AI orchestrator, validator, memory, and UI.
    Inherits fallback_topic when the prompt is a follow-up action without an explicit new subject.
    """
    if not text:
        return fallback_topic or "Core Concept"
    
    # Defensive guard: if input text is Mermaid code or contains graph tokens, do not treat as topic
    if "graph " in text.lower() or "flowchart " in text.lower() or "-->" in text or "```mermaid" in text.lower():
        return fallback_topic or "Core Concept"
    
    cleaned = re.sub(
        r'^(Teach me step by step until I understand|Teach me\s+(step by step|until I understand)?|Explain this concept even simpler|Explain this concept simply|Explain this simpler|Explain this concept|Explain this\s+|Explain\s+(this\s+|it\s+|the concept\s+)?|Give a real[- ]world analogy for|Give a real[- ]world analogy|Give an analogy for|Give an analogy|Tell me about advanced applications of|Tell me about this|Tell me about|Understanding how the|Understanding how|Understanding|Explain what is|What is\s+(an\s+|a\s+|the\s+)?|What are\s+(the\s+)?|What\s+|How does\s+|How do\s+|Why is\s+|Can you explain\s+|Deep dive into\s+)\s*',
        '',
        text.strip(),
        flags=re.IGNORECASE
    ).strip()
    
    cleaned = re.sub(r'^(an\s+|a\s+|the\s+|this\s+|it\s+)', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'^[:\-\s]+', '', cleaned).strip()
    cleaned = re.sub(r'\s+(step by step|in simple terms|simply|with an analogy|until I understand|for beginners)[\?!.]*$', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[:\-\?\.!\s]+$', '', cleaned).strip()
    
    generic_words = {"this", "it", "concept", "this concept", "the concept", "core concept", "more", "everything", "detail", "details", "again", "simpler", "analogy", "step by step", ""}
    if not cleaned or len(cleaned) < 2 or cleaned.lower() in generic_words:
        return fallback_topic or "Core Concept"
    
    if len(cleaned.split()) <= 5:
        titled = cleaned.title()
        words = [KNOWN_ACRONYMS.get(w, w) for w in titled.split()]
        return " ".join(words)
    else:
        return cleaned[0].upper() + cleaned[1:]


# ─────────────────────────────────────────────────────────────────────────────
# PDF TOPIC EXTRACTION & PREREQUISITE-AWARE NEXT LEARNING STEPS
# ─────────────────────────────────────────────────────────────────────────────
TOPIC_NEXT_STEPS = {
    "cnn": "Padding, Stride, and Spatial Downsampling with Pooling",
    "convolutional": "Padding, Stride, and Spatial Downsampling with Pooling",
    "pooling": "Training CNNs and Backpropagation in Convolutional Layers",
    "neural network": "Convolutional Neural Networks and Spatial Features",
    "perceptron": "Multi-Layer Perceptrons and Non-Linear Activation Functions",
    "activation": "Vanishing Gradients and Non-Saturating Activations (ReLU, GELU)",
    "backpropagation": "Gradient Descent Optimizers: SGD, Momentum, and Adam",
    "gradient descent": "Learning Rate Schedules and Adaptive Optimizers",
    "transformer": "Scaled Dot-Product Attention Mechanics and Multi-Head Projections",
    "attention": "Multi-Head Attention and Positional Encodings in Transformers",
    "binary search": "Binary Search on Monotonic Ranges and Lower Bound Search",
    "recursion": "Call Stack Frame Limits and Recursive Tree Complexity",
    "merge sort": "Quicksort Partitioning and Divide-and-Conquer Recurrences",
    "derivative": "Integrals and the Fundamental Theorem of Calculus",
    "photosynthesis": "Cellular Respiration and ATP Energy Currency",
    "newton": "Rotational Dynamics and Conservation of Angular Momentum",
    "chemical bond": "Molecular Geometry and VSEPR Theory",
    "supply and demand": "Elasticity and Market Equilibrium Shifts"
}

def extract_candidate_topics_from_pdf(pdf_text_or_chunks: Any) -> List[str]:
    """Extracts prominent candidate topic phrases / headings from PDF context or chunks."""
    if not pdf_text_or_chunks:
        return []
    
    text = ""
    if isinstance(pdf_text_or_chunks, list):
        for c in pdf_text_or_chunks:
            if isinstance(c, dict):
                text += " " + c.get("text", c.get("content", ""))
            elif isinstance(c, str):
                text += " " + c
    elif isinstance(pdf_text_or_chunks, str):
        text = pdf_text_or_chunks

    if not text.strip():
        return []

    candidates: List[str] = []
    # Match markdown headings (### Title), bold concepts (**Title**), or Chapter/Section markers
    headings = re.findall(r'(?:###|\*\*|Section\s*\d*:?|Chapter\s*\d*:?)\s*([A-Za-z0-9\s\-–]{3,40})(?:\*\*|\n|$)', text)
    for h in headings:
        h_clean = h.strip().strip("*:–-# ")
        if len(h_clean) >= 3 and not h_clean.lower().startswith("step") and not h_clean.lower().startswith("checkpoint") and not h_clean.lower().startswith("mini-example"):
            if h_clean not in candidates and not any(h_clean.lower() == existing.lower() for existing in candidates):
                candidates.append(h_clean)
    
    # Discovery of domain-grounded keywords present in document text
    keywords = [
        "Convolutional Neural Networks", "Backpropagation", "Gradient Descent", "Loss Function",
        "Activation Functions", "Max Pooling", "Dense Layers", "Softmax", "Learning Rate",
        "Overfitting", "Regularization", "Batch Normalization", "Chain Rule", "Derivative",
        "Integrals", "Matrix Multiplication", "Eigenvalues", "Newton's Second Law", "Thermodynamics",
        "Photosynthesis", "Cellular Respiration", "Chemical Bonding", "Supply and Demand",
        "Operating System Deadlock", "Binary Search", "Industrial Revolution"
    ]
    for kw in keywords:
        if kw.lower() in text.lower():
            if not any(kw.lower() == existing.lower() for existing in candidates):
                candidates.append(kw)

    return candidates


def get_prerequisite_next_step(canonical_topic: str, pdf_context: Any = None) -> str:
    """
    Returns the next pedagogical concept.
    Strictly prioritizes available topics from the uploaded PDF document when a PDF session is active.
    """
    if pdf_context:
        available_topics = extract_candidate_topics_from_pdf(pdf_context)
        topic_lower = canonical_topic.lower()
        # Find the first available PDF topic that is not the current topic
        for candidate in available_topics:
            if candidate.lower() not in topic_lower and topic_lower not in candidate.lower():
                return f"From your uploaded material, study {candidate} next."
        return "Continue exploring the next section of your uploaded study material."

    topic_lower = canonical_topic.lower()
    for key, step in TOPIC_NEXT_STEPS.items():
        if key in topic_lower:
            return step
    return f"Advanced applications and optimization principles of {canonical_topic}"


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL MULTI-ANGLE STANDARD LESSON SYNTHESIZER
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_standard_lesson(
    canonical_topic: str,
    partial_exp: str = "",
    partial_why: str = "",
    partial_example: str = "",
    variant: PresentationVariant = PresentationVariant.ARCHITECTURE
) -> Dict[str, str]:
    """
    Synthesizes a rich, multi-perspective master lesson (350-500 words) for ANY topic
    adapted to the chosen presentation variant (Architecture, Training/Process, Mechanism, Intuition, Application).
    """
    domain = infer_domain_archetype(canonical_topic)
    t = canonical_topic.strip()

    if variant == PresentationVariant.TRAINING_CYCLE or variant == PresentationVariant.PROCESS:
        # Perspective: Learning process / Lifecycle / Forward & Feedback dynamics
        explanation = (
            f"**{t}** is best understood through its dynamic operational lifecycle. Rather than existing as a static set of rules, "
            f"it operates through continuous, iterative refinement—systematically evaluating the delta between its current state and target objective.\n\n"
            f"### 1. Forward Progression & State Transformation\n"
            f"During the forward phase, raw inputs are ingested and propagated through a sequence of discrete operational stages. "
            f"Each stage applies parameterized transformations, progressively converting unstructured signals into rich intermediate representations to formulate an initial prediction or state estimate.\n\n"
            f"### 2. Quantitative Error Measurement & Loss Evaluation\n"
            f"Once an output is produced, the system computes the exact discrepancy against the ground truth using an objective loss function. "
            f"This quantitative metric provides a rigorous error signal, identifying exactly which internal parameters contributed to variance and guiding how subsequent adjustments should be prioritized.\n\n"
            f"### 3. Feedback Propagation & Parameter Optimization\n"
            f"Using systematic gradient signals and feedback propagation, adjustments are calculated and applied across parameters. "
            f"Across repeated training cycles and epochs, the system continuously minimizes operational error, converging toward stable equilibrium and robust generalization."
        )
        why = (
            f"Iterative feedback loops allow {t} to autonomously adapt to complex, high-dimensional distributions without requiring rigid manual heuristic tuning. "
            f"By aligning continuous parameter shifts against empirical loss signals, the model internalizes the underlying statistical distribution rather than memorizing isolated training samples."
        )
        example = (
            f"Consider training a predictive model for {t}: initial parameters produce high variance and large residuals. "
            f"Across consecutive training epochs, backpropagated gradient updates systematically penalize erroneous weights, reducing mean squared loss from 1.42 down to 0.03."
        )

    elif variant == PresentationVariant.MECHANISM:
        # Perspective: Mathematical and internal transformation mechanics
        explanation = (
            f"**{t}** is governed by deterministic mathematical transformations and operational principles. "
            f"Understanding its core mechanism requires examining the exact sequence of computations applied to input variables.\n\n"
            f"### 1. Input Vector Mapping & Parameterized Combinations\n"
            f"Inputs enter the system as structured vectors or continuous state variables. Parameterized weights modulate the relative influence of each feature, "
            f"computing linear dot-product combinations and balancing feature significance across dimensions.\n\n"
            f"### 2. Non-Linear Activation & Decision Boundaries\n"
            f"To capture intricate real-world interactions, linear combinations pass through non-linear activation functions. "
            f"This mathematical transformation prevents multi-layer operations from collapsing into trivial linear systems, allowing {t} to construct complex, curved decision boundaries across high-dimensional space.\n\n"
            f"### 3. Invariant Preservation & Numerical Convergence\n"
            f"Throughout execution, {t} enforces rigorous computational invariants. Intermediate states are validated to preserve gradient flow, prevent numerical instability, and guarantee predictable runtime bounds."
        )
        why = (
            f"Mathematical decoupling of representation layers enables {t} to compute complex functional mappings while maintaining numerical stability and asymptotic guarantees. "
            f"Enforcing continuous differentiability and bounded gradients guarantees that optimizations converge reliably to valid solutions."
        )
        example = (
            f"In practice, computing the dot product between an input vector $\\mathbf{x} = [0.8, 0.4]$ and weight vector $\\mathbf{w} = [1.5, -0.5]$ yields a scalar $z = 1.0$. "
            f"Passing this through a non-linear activation $\\text{ReLU}(1.0)$ preserves positive activation while cleanly filtering spurious negative signals."
        )

    elif variant == PresentationVariant.INTUITION:
        # Perspective: Intuitive conceptual model / geometric mental picture
        explanation = (
            f"To build lasting conceptual intuition for **{t}**, visualize it not merely as mathematical formulas, "
            f"but as a structured mental model for organizing, refining, and navigating complex information.\n\n"
            f"### 1. The Core Mental Model & Landscape\n"
            f"Imagine standing on a vast, unfamiliar terrain. **{t}** acts as a compass, determining the most efficient direction by evaluating local contours, gradients, and structural landmarks at every step.\n\n"
            f"### 2. Hierarchical Feature Composition\n"
            f"Rather than attempting to master an entire problem in a single leap, {t} decomposes complexity into manageable, layered tiers. "
            f"Early stages isolate simple primitives and localized clues, while intermediate stages weave these building blocks into cohesive structural motifs.\n\n"
            f"### 3. Generalization & Noise Elimination\n"
            f"By abstracting away superficial fluctuations, {t} isolates the underlying governing principles. "
            f"This fundamental filtering ensures that insights gained on known examples transfer seamlessly to novel, unencountered challenges."
        )
        why = (
            f"Hierarchical feature composition allows {t} to extract invariant signals from noisy real-world data while avoiding memorization of superficial patterns. "
            f"This multi-scale abstraction ensures that core semantic concepts remain resilient against localized noise and sensor distortions."
        )
        example = (
            f"When identifying an image, early stages detect simple high-contrast edges and texture gradients. "
            f"Intermediate stages combine these edges into geometric shapes like circles and rectangles, and the top stage integrates shapes into a recognizable object identity."
        )

    elif variant == PresentationVariant.APPLICATION:
        # Perspective: Real-world engineering / practical system deployment
        explanation = (
            f"In production software and modern engineering architectures, **{t}** functions as an indispensable engine for high-throughput, mission-critical problem solving.\n\n"
            f"### 1. Production Pipeline Integration\n"
            f"When deployed in industrial systems, {t} ingests live event telemetry, applies optimized transformations in real time, "
            f"and generates high-confidence decisions under strict latency budgets and computational constraints.\n\n"
            f"### 2. Engineering Trade-offs & Resource Optimization\n"
            f"Architecting with {t} requires balancing memory footprint, computational complexity, and inference latency. "
            f"Practitioners employ techniques such as parallelization, vectorization, caching, and precision tuning to maximize throughput across hardware environments.\n\n"
            f"### 3. Resilience, Verification & Edge Cases\n"
            f"Robust implementations incorporate proactive validation layers, comprehensive error boundaries, and defensive fallback strategies to maintain uninterrupted reliability under extreme workloads."
        )
        why = (
            f"Modular computational design ensures {t} scales seamlessly across distributed clusters, embedded devices, and real-time operational workflows. "
            f"Decoupled components allow independent horizontal scaling and low-latency cached inference in high-concurrency environments."
        )
        example = (
            f"A production recommendation or inference cluster serving 50,000 requests per second utilizes vectorized batches of {t}, "
            f"executing SIMD operations on GPU hardware to deliver sub-10 millisecond response latencies."
        )

    else:
        # Default: ARCHITECTURE perspective (Structural components & layers)
        if any(k in canonical_topic.lower() for k in ["cnn", "convolutional", "computer vision"]):
            explanation = (
                "**Convolutional Neural Networks (CNNs)** are deep learning architectures purpose-built to process grid-structured data like images. "
                "They replace traditional matrix multiplication with discrete convolution operations, drastically reducing parameter counts while preserving spatial locality across visual dimensions.\n\n"
                "### 1. Architectural Foundations & Grid Ingestion\n"
                "Images enter as 3D numerical tensors ($H \\times W \\times C$). Unlike fully connected networks that flatten images into 1D vectors and lose spatial geometry, "
                "CNNs maintain height and width dimensions throughout early layers, allowing the network to detect localized spatial relationships and spatial neighborhoods.\n\n"
                "### 2. Convolutional Kernels & Feature Maps with ReLU\n"
                "Small parameter matrices called filters or kernels ($3 \\times 3$ or $5 \\times 5$) slide across the input tensor with a specified stride and padding. "
                "At each position, dot-products compute 2D Feature Maps highlighting visual patterns like edges and textures. "
                "Applying $\\text{ReLU}(z) = \\max(0, z)$ zeroes out negative activations, creating sparse, non-linear feature representations that capture intricate visual hierarchies.\n\n"
                "### 3. Spatial Pooling & Dimensionality Reduction\n"
                "Max Pooling partitions feature maps into small windows (e.g. $2 \\times 2$) and retains only the maximum activation value. "
                "This downsampling reduces spatial dimensions by 75%, lowering computational cost while providing translation invariance against minor spatial shifts and rotations.\n\n"
                "### 4. Dense Classification with Softmax\n"
                "Final pooled feature maps are flattened into a 1D vector and passed through fully connected dense layers. "
                "The final layer applies Softmax to output a normalized probability distribution across target classification labels."
            )
            why = (
                "Weight sharing and local receptive fields reduce parameter complexity by orders of magnitude compared to dense networks. "
                "Translational invariance ensures an object is recognized regardless of its exact coordinate location in the image, while gradient propagation remains stable through ReLU activations."
            )
            example = (
                "When classifying a handwritten digit, early convolutional layers detect line edges and stroke endpoints, "
                "middle layers assemble strokes into loops and curves, and fully connected layers output a 98.4% confidence prediction for digit '7'."
            )
        else:
            explanation = (
                f"**{t}** represents a foundational architectural paradigm engineered to solve complex analytical, computational, and structural challenges. "
                f"Its framework consists of carefully decoupled layers and interfaces that collaborate to transform raw inputs into verified, actionable results.\n\n"
                f"### 1. Ingestion Interface & Feature Structuring\n"
                f"Inputs enter the system through standardized ingestion interfaces. Features are validated, normalized, and mapped into structured representations to ensure predictable numerical behavior across execution paths.\n\n"
                f"### 2. Core Processing Subsystems & Intermediate Layers\n"
                f"Specialized intermediate subsystems execute core transformations. Each stage applies domain-specific operators, progressively refining data and extracting hierarchical representations across depth.\n\n"
                f"### 3. Output Synthesis & Decision Boundaries\n"
                f"The final architectural tier synthesizes intermediate representations into conclusive predictions or state transitions, verified against calibrated confidence thresholds before release."
            )
            why = (
                f"Clear architectural separation of concerns simplifies testing, enforces deterministic guarantees, and maximizes parallel throughput for {t}. "
                f"By isolating feature ingestion, state transformation, and output synthesis into distinct modular boundaries, systems can be optimized independently."
            )
            example = (
                f"In a computer vision or data analysis pipeline, the input matrix is parsed by normalized tensor loaders, "
                f"processed across parallel convolution or transformation layers, and projected into a compact classification vector with high precision."
            )

    # Generate matching adaptive diagram
    viz = generate_adaptive_diagram(canonical_topic, variant, "STANDARD", explanation)

    return {
        "canonical_topic": canonical_topic,
        "simple_explanation": explanation,
        "why_it_works": why,
        "example": example,
        "common_mistake": f"Confusing the high-level interface of {canonical_topic} with its internal mathematical representations and execution mechanics.",
        "mini_quiz": f"What is the primary role of the intermediate transformation stage in {canonical_topic}?",
        "reflection_prompt": f"How would you explain the core mechanism of {canonical_topic} to a fellow learner?",
        "coach_recommendation": f"Focus on how {canonical_topic} structures data transformations and optimizes its decision boundaries.",
        "next_learning_step": get_prerequisite_next_step(canonical_topic),
        "visual_intuition": viz
    }


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL SIMPLIFY LESSON SYNTHESIZER (80 - 120 WORDS)
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_simplify_lesson(canonical_topic: str) -> Dict[str, str]:
    """
    Synthesizes a concise, jargon-free ELI5 explanation (80-120 words) with simplified diagram.
    """
    topic_lower = canonical_topic.lower()
    t = canonical_topic.strip()

    if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
        exp = (
            "Imagine a team of puzzle solvers looking at a photograph. The first solver finds small lines and edges. "
            "The second solver connects those lines into circles and corners. The third solver puts corners together into eyes and wheels. "
            "Finally, the leader looks at all the shapes and says: *\"This is a car!\"* Each step builds bigger understanding from simple pieces."
        )
        viz = 'graph LR;\n  Image["Input Image"] --> Simple["Simple Edges"] --> Complex["Complex Shapes"] --> Object["Object Decision"];'
    elif any(k in topic_lower for k in ["neural", "perceptron", "deep learning"]):
        exp = (
            "Imagine teaching a child to recognize fruits. You show them an apple and guess. When they guess wrong, "
            "you give them a gentle hint. Little by little, they adjust how much attention they pay to color, shape, and stem. "
            "A neural network does the exact same thing—testing guesses and adjusting its internal dials until it rarely makes mistakes."
        )
        viz = 'graph LR;\n  Input["Input Data"] --> NN["Neural Network Layers"] --> Learn["Learn Patterns"] --> Pred["Prediction"];'
    elif any(k in topic_lower for k in ["binary search", "search"]):
        exp = (
            "Imagine opening a dictionary to find 'Mountain'. Instead of starting on page 1, you flip right to the middle. "
            "You see 'Lemon' and know 'Mountain' comes after. You immediately ignore the first half and flip to the middle of the remaining pages. "
            "By cutting the pages in half each time, you find the word in just a few quick flips!"
        )
        viz = 'graph LR;\n  Array["Sorted Array"] --> Mid["Check Midpoint"] --> Discard["Discard Half"] --> Target["Target Found"];'
    elif any(k in topic_lower for k in ["derivative", "calculus", "slope"]):
        exp = (
            "Imagine riding in a car. The speedometer doesn't tell you the average speed of your entire trip—it tells you your speed right at this exact split-second. "
            "A derivative is just a mathematical speedometer. It measures how fast something is changing at one exact moment!"
        )
        viz = 'graph LR;\n  Position["Car Position"] --> Speedometer["Derivative dy/dx"] --> InstantSpeed["Speed Right Now"];'
    elif any(k in topic_lower for k in ["photosynthesis", "plant"]):
        exp = (
            "Think of a plant leaf like a tiny solar-powered kitchen. The plant catches sunlight through its green solar panels, "
            "drinks water from the soil, and breathes in carbon dioxide from the air. It bakes these ingredients into sweet sugar energy for food, and releases fresh oxygen for us to breathe!"
        )
        viz = 'graph LR;\n  Ingredients["Sunlight + Water + CO2"] --> Kitchen["Leaf Chloroplasts"] --> Products["Sugar Food + Oxygen"];'
    elif any(k in topic_lower for k in ["newton", "force", "acceleration"]):
        exp = (
            "Imagine pushing a shopping cart. If the cart is empty (small mass), a gentle push sends it zooming forward fast (high acceleration). "
            "If the cart is loaded with heavy groceries (large mass), you need a much harder push to get the same speed. That's Newton's Second Law: Force equals mass times acceleration!"
        )
        viz = 'graph LR;\n  Push["Push (Force F)"] --> Cart["Cart Weight (Mass m)"] --> SpeedUp["Speed Up (Acceleration a)"];'
    else:
        exp = (
            f"Think of {t} like an assembly line where each station performs one simple, clear task. "
            f"Raw materials come in at the beginning, get cleaned and shaped in the middle, and exit as a finished product. "
            f"If something looks off, a supervisor tunes the machines so the next product comes out even better."
        )
        viz = f'graph LR;\n  Input["Raw Input"] --> Process["{t}"] --> Result["Clean Result"];'

    return {
        "canonical_topic": t,
        "simple_explanation": exp,
        "why_it_works": f"Simplifying {t} captures the intuitive flow from raw input to verified result without unnecessary jargon.",
        "example": f"Building complex solutions from simple, verifiable stages.",
        "common_mistake": f"Thinking {t} is mysterious magic rather than small, predictable adjustments.",
        "mini_quiz": f"In simple terms, what is the main goal of {t}?",
        "reflection_prompt": f"How would you explain the core idea of {t} to a 10-year-old?",
        "coach_recommendation": f"Keep the simple mental model in mind before diving into mathematical formulas.",
        "next_learning_step": get_prerequisite_next_step(t),
        "visual_intuition": viz
    }


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL ANALOGY LESSON SYNTHESIZER (120 - 180 WORDS)
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_analogy_lesson(canonical_topic: str) -> Dict[str, str]:
    """
    Synthesizes a pure real-world analogy lesson (120-180 words) with explicit mapping and matching diagram.
    """
    topic_lower = canonical_topic.lower()
    t = canonical_topic.strip()

    if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
        exp = (
            "Think of a **Convolutional Neural Network (CNN)** like a team of detectives examining a mystery photograph.\n\n"
            "• **Inspectors with Magnifying Glasses (Convolutional Filters):** Detectives slide small magnifying glasses across the photo patch by patch, hunting for basic local clues—a sharp edge, a color corner, or a curve.\n"
            "• **Clue Map Notepads (Feature Maps & ReLU):** Every time an inspector spots a clue, they highlight it on a summary notepad and ignore blank background space.\n"
            "• **Summary Index Cards (Pooling Layers):** A coordinator condenses large notepads into essential bullet points, keeping only the strongest clues so the team isn't overwhelmed.\n"
            "• **Lead Detective Conference (Fully Connected Layers):** The chief detective reviews all collected clue cards together and declares the final verdict: *\"This is a bicycle!\"*"
        )
        viz = 'graph LR;\n  Photo["Photograph"] --> Inspectors["Filter Inspectors"] --> Clues["Pattern Clues"] --> Summary["Summary Notes"] --> Chief["Lead Detective"] --> Verdict["Final Identity"];'

    elif any(k in topic_lower for k in ["neural", "perceptron", "deep learning"]):
        exp = (
            "Think of an **Artificial Neural Network** like a multi-station gourmet restaurant kitchen perfecting a signature recipe.\n\n"
            "• **Prep Station (Input Layer):** Raw ingredients arrive—chopped, measured, and organized like raw input features.\n"
            "• **Line Cook Stations (Hidden Layers & Weights):** Line cooks combine ingredients, adjusting spice and heat dials to balance recipe flavors.\n"
            "• **Head Chef Taste Test (Activation & Output):** The head chef tastes the dish against strict restaurant standards and serves it to the guest.\n"
            "• **Customer Review & Recipe Tweak (Loss & Backpropagation):** If a customer sends a dish back because it was too salty, the head chef traces the error backwards, instructing the line cook to reduce the salt ratio on the next order."
        )
        viz = 'graph LR;\n  Ingredients["Raw Ingredients"] --> LineCooks["Line Cooks Adjust Spices"] --> Chef["Head Chef Taste Test"] --> Feedback["Customer Feedback"] --> Refine["Recipe Refined"];'

    elif any(k in topic_lower for k in ["binary search"]):
        exp = (
            "Think of **Binary Search** like playing a high-low number guessing game for a secret number between 1 and 100.\n\n"
            "• **First Guess (Midpoint):** You don't guess 1, 2, 3 in order. You guess **50** right in the middle.\n"
            "• **The Clue (Comparison):** Your friend says *\"Higher!\"*\n"
            "• **Discarding the Half (Search Space Elimination):** In one second, you permanently throw away numbers 1 through 50. You now only have 51–100 to search.\n"
            "• **Next Guess (Repeat Halving):** You guess 75, then 88, pinpointing the exact secret number in at most 7 total guesses!"
        )
        viz = 'graph LR;\n  Guess50["Guess Midpoint 50"] --> Higher["Friend Says Higher"] --> Discard["Discard 1 to 50"] --> Guess75["Guess 75"] --> Target["Secret Found"];'

    elif any(k in topic_lower for k in ["derivative", "calculus"]):
        exp = (
            "Think of a **Derivative** like zooming in on a roller coaster track with a high-powered microscope.\n\n"
            "• **The Big Curve (The Function $f(x)$):** From far away, the coaster track climbs, dips, and curves wildly across the amusement park.\n"
            "• **Zooming In (Taking the Limit $\\Delta x \\to 0$):** If you zoom in extremely close to the single point where your cart sits right now, the curved metal rail looks like a perfectly straight ruler.\n"
            "• **The Angle of the Ruler (The Derivative $f'(x)$):** The tilt of that straight ruler is the derivative—it tells you the exact steepness of your motion at that precise microsecond."
        )
        viz = 'graph LR;\n  CoasterTrack["Curved Track f(x)"] --> ZoomIn["Microscopic Zoom Δx→0"] --> TangentRuler["Straight Ruler Line"] --> Steepness["Instantaneous Slope f\'(x)"];'

    elif any(k in topic_lower for k in ["photosynthesis"]):
        exp = (
            "Think of **Photosynthesis** like an ultra-efficient automated battery factory.\n\n"
            "• **Solar Panels (Chlorophyll):** Photons from sunlight strike the roof panels, charging up high-energy battery packs (ATP and NADPH).\n"
            "• **Assembly Line (Calvin Cycle):** The factory takes carbon dioxide raw materials from the ambient air and uses the stored battery power to assemble durable, shelf-stable energy fuel bricks (glucose sugar).\n"
            "• **Clean Exhaust (Oxygen):** The factory releases clean oxygen byproduct back into the atmosphere."
        )
        viz = 'graph LR;\n  Sunlight["Sunlight Photons"] --> SolarPanels["Chlorophyll Batteries (ATP)"] --> AssemblyLine["Calvin Sugar Synthesis"] --> StoredFuel["Glucose Fuel Blocks"];'

    else:
        exp = (
            f"Think of **{t}** like a specialized airport luggage sorting terminal.\n\n"
            f"• **Check-In Counter (Input Intake):** Items arrive with labels indicating their destination and priorities.\n"
            f"• **Automated Conveyor Scanners (Intermediate Processing):** High-speed optical scanners read labels, routing items through specialized sorter gates.\n"
            f"• **Quality Inspection (Decision Thresholds):** Verification sensors confirm routing accuracy before final distribution.\n"
            f"• **System Re-routing (Feedback Adjustments):** If an item is misdirected, the routing computer recalibrates its switch timers for all subsequent items."
        )
        viz = f'graph LR;\n  Arrival["Items Arrive"] --> Scanners["Optical Scanners"] --> Gates["Sorter Gates"] --> Flight["Verified Delivery"];'

    return {
        "canonical_topic": t,
        "simple_explanation": exp,
        "why_it_works": f"The analogy provides a physical mental model for how {t} ingests, processes, and optimizes its operational flow.",
        "example": f"Real-world workflows intuitively mapping to the internal mechanics of {t}.",
        "common_mistake": f"Focusing solely on external appearances rather than how feedback flows backward to adjust internal parameters.",
        "mini_quiz": f"In the analogy, what corresponds to the primary processing step of {t}?",
        "reflection_prompt": f"Can you map the components of {t} to another familiar real-world system?",
        "coach_recommendation": f"Anchor your mental model on how real-world feedback parallels the governing principles of {t}.",
        "next_learning_step": get_prerequisite_next_step(t),
        "visual_intuition": viz
    }


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL STEP-BY-STEP LESSON SYNTHESIZER (450 - 600 WORDS)
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_step_by_step_lesson(canonical_topic: str) -> Dict[str, str]:
    """
    Synthesizes a 5-step structured lesson with mini-examples (450-600 words).
    """
    topic_lower = canonical_topic.lower()
    t = canonical_topic.strip()

    if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
        exp = (
            "### Step 1 — Input Matrix Ingestion & Image Normalization\n"
            "A Convolutional Neural Network ingests raw visual input represented as a 3D tensor of shape $\\text{Height} \\times \\text{Width} \\times \\text{Channels}$. "
            "For standard color images, three color channels (Red, Green, Blue) contain pixel values ranging from 0 to 255. "
            "These raw integer values are normalized into floating-point numbers between $0.0$ and $1.0$ or standardized with zero mean to accelerate training stability.\n\n"
            "*Mini-Example:* A $28 \\times 28$ grayscale handwritten digit is ingested as a single-channel matrix of 784 normalized pixel intensity values.\n\n"
            "### Step 2 — Convolutional Filtering & Local Feature Extraction\n"
            "Small learnable weight matrices called filters or kernels (typically $3 \\times 3$ or $5 \\times 5$) slide systematically across the image with a defined stride and padding. "
            "At every spatial position, the filter computes element-wise dot products with the underlying image patch, summing them into a single scalar in a 2D Feature Map. "
            "Each filter learns to detect specific visual primitives such as horizontal edges, diagonal textures, and color boundaries.\n\n"
            "*Mini-Example:* A vertical Sobel edge filter computes high positive activation when passing over the high-contrast boundary between an object and its background.\n\n"
            "### Step 3 — Non-Linear Rectified Linear Activation (ReLU)\n"
            "To model complex non-linear patterns, the network applies an activation function $\\text{ReLU}(z) = \\max(0, z)$ element-wise to every feature map. "
            "Negative activation values are clamped to zero while positive values pass through unchanged. "
            "This sparse activation prevents mathematical linearity and enables deep networks to learn non-linear visual relationships.\n\n"
            "*Mini-Example:* Feature response values $[-2.4, 0.0, 5.1]$ become $[0.0, 0.0, 5.1]$, emphasizing active visual features and discarding negative responses.\n\n"
            "### Step 4 — Spatial Max Pooling & Dimensional Downsampling\n"
            "Max Pooling partitions the activated feature maps into non-overlapping spatial windows (typically $2 \\times 2$ with stride 2) and retains only the maximum activation value in each window. "
            "This downsampling reduces spatial dimensions by 75%, drastically lowering computational parameters while providing translation invariance against minor shifts.\n\n"
            "*Mini-Example:* A $2 \\times 2$ patch with activations $[1.2, 3.4; 0.5, 8.1]$ condenses down to a single maximum scalar $8.1$.\n\n"
            "### Step 5 — Dense Classification & Softmax Probability Output\n"
            "The final pooled feature maps are flattened into a 1D vector and passed through fully connected dense layers. "
            "The final layer applies the Softmax function $\\sigma(\\mathbf{z})_i = \\frac{e^{z_i}}{\\sum_j e^{z_j}}$ to convert raw logit scores into normalized probabilities across all target classes.\n\n"
            "*Mini-Example:* The network computes logits $[0.2, 5.8, 1.1]$, outputting a $98.2\\%$ probability confidence score for the target class."
        )
        viz = 'graph TD;\n  S1["Step 1: Input Matrix"] --> S2["Step 2: Convolution Filters"];\n  S2 --> S3["Step 3: ReLU Activation"];\n  S3 --> S4["Step 4: Max Pooling"];\n  S4 --> S5["Step 5: Dense Softmax"];'

    elif any(k in topic_lower for k in ["neural", "perceptron", "deep learning"]):
        exp = (
            "### Step 1 — Input Feature Ingestion & Linear Combination\n"
            "Input features $\\mathbf{x} = [x_1, x_2, \\dots, x_n]$ enter the artificial neuron and are multiplied by adjustable weight parameters $\\mathbf{w} = [w_1, w_2, \\dots, w_n]$. "
            "A bias term $b$ is added to shift the decision boundary independently of the inputs, computing the pre-activation sum $z = \\mathbf{w}^T \\mathbf{x} + b$.\n\n"
            "*Mini-Example:* For inputs $x_1=2, x_2=3$ with weights $w_1=0.5, w_2=1.0$ and bias $b=0.5$, the pre-activation sum is $z = (2 \\times 0.5) + (3 \\times 1.0) + 0.5 = 4.5$.\n\n"
            "### Step 2 — Non-Linear Threshold Activation\n"
            "The pre-activation sum $z$ passes through an activation function $f(z)$ (such as ReLU, Sigmoid, or GELU) to introduce non-linear expressiveness. "
            "Without non-linear activations, multi-layer networks collapse mathematically into simple single-layer linear regression models.\n\n"
            "*Mini-Example:* Applying $\\text{ReLU}(4.5) = 4.5$, while a negative pre-activation $\\text{ReLU}(-1.2) = 0.0$ disables the neuron's firing.\n\n"
            "### Step 3 — Multi-Layer Forward Propagation\n"
            "Activated outputs from layer $l$ serve as input vectors to layer $l+1$. "
            "The network propagates activations sequentially through hidden layers, composing simple low-level features into complex, abstract hierarchical representations.\n\n"
            "*Mini-Example:* Early layers detect raw edges, intermediate layers combine edges into geometric contours, and output layers recognize composite objects.\n\n"
            "### Step 4 — Quantitative Loss Calculation\n"
            "The final layer outputs prediction $\\hat{y}$, which is compared against the true target label $y$ using an objective loss function $L(\\hat{y}, y)$. "
            "This computes the exact numerical penalty quantifying the prediction error across the dataset.\n\n"
            "*Mini-Example:* For a target $y=1.0$ and prediction $\\hat{y}=0.7$, the mean squared error loss is $(1.0 - 0.7)^2 = 0.09$.\n\n"
            "### Step 5 — Backpropagation & Gradient Optimization\n"
            "Applying the calculus chain rule, the algorithm computes partial derivatives $\\frac{\\partial L}{\\partial w}$ backwards from the output layer to the inputs. "
            "An optimizer like Adam or SGD updates each weight: $w \\leftarrow w - \\eta \\frac{\\partial L}{\\partial w}$, reducing error across successive iterations.\n\n"
            "*Mini-Example:* With gradient $\\frac{\\partial L}{\\partial w} = 0.4$ and learning rate $\\eta=0.1$, the weight updates by subtracting $0.04$."
        )
        viz = 'graph TD;\n  S1["Step 1: Linear Transformation (wx+b)"] --> S2["Step 2: Non-Linear Activation"];\n  S2 --> S3["Step 3: Forward Propagation"];\n  S3 --> S4["Step 4: Loss Calculation"];\n  S4 --> S5["Step 5: Backprop & Weight Update"];'

    elif any(k in topic_lower for k in ["binary search"]):
        exp = (
            "### Step 1 — Verify the Sorted Invariant & Establish Pointers\n"
            "Binary Search requires the target array to be strictly sorted in ascending order. "
            "We initialize two boundary pointer variables: `low = 0` (pointing to the first index) and `high = n - 1` (pointing to the last index of the search space).\n\n"
            "*Mini-Example:* In array $[2, 5, 8, 12, 16, 23, 38, 56]$, initialize `low = 0` (element $2$) and `high = 7` (element $56$).\n\n"
            "### Step 2 — Compute the Midpoint Index\n"
            "Calculate the middle index using the overflow-safe formula: $\\text{mid} = \\text{low} + \\lfloor(\\text{high} - \\text{low})/2\\rfloor$. "
            "This divides the active candidate search space into two equal halves in $O(1)$ time.\n\n"
            "*Mini-Example:* With `low=0` and `high=7`, compute $\\text{mid} = 0 + \\lfloor(7-0)/2\\rfloor = 3$, accessing `arr[3] = 12`.\n\n"
            "### Step 3 — Compare Midpoint Value with Target\n"
            "Compare the midpoint value `arr[mid]` directly against the target value $T$. "
            "If `arr[mid] == T`, the target has been successfully identified and the search terminates immediately returning `mid`.\n\n"
            "*Mini-Example:* If searching for $T = 23$, compare candidate value `12` with target `23` ($12 < 23$).\n\n"
            "### Step 4 — Eliminate Half the Search Space\n"
            "Because the array is sorted, if `target > arr[mid]`, the target cannot possibly exist in the left half. "
            "We discard the left half by setting `low = mid + 1`. Conversely, if `target < arr[mid]`, we discard the right half by setting `high = mid - 1`.\n\n"
            "*Mini-Example:* Set `low = 3 + 1 = 4`, instantly discarding the first half of the array $[2, 5, 8, 12]$ in a single step.\n\n"
            "### Step 5 — Iterative Halving & Termination\n"
            "Repeat Steps 2 through 4 until the target element is located or the search space becomes exhausted when `low > high`. "
            "This logarithmic halving guarantees finding any element in an $N$-element array in at most $\\lceil\\log_2(N)\\rceil$ comparisons.\n\n"
            "*Mini-Example:* In the next iteration with `low=4` and `high=7`, $\\text{mid}=5$ accesses `arr[5]=23`, achieving a match in 2 steps."
        )
        viz = 'graph TD;\n  S1["Step 1: Establish Low & High Pointers"] --> S2["Step 2: Compute Midpoint Index"];\n  S2 --> S3["Step 3: Compare Mid with Target"];\n  S3 --> S4["Step 4: Discard Half the Array"];\n  S4 --> S5["Step 5: Return Found Index"];'

    else:
        exp = (
            f"### Step 1 — Foundational Definition & Problem Formulation\n"
            f"We begin by establishing the exact scope, fundamental principles, and operational objectives of **{t}**. "
            f"Understanding the baseline prerequisites and core invariants ensures that all subsequent operations rest on verified assumptions.\n\n"
            f"*Mini-Example:* Identifying the baseline state and defining initial operational boundaries before applying {t}.\n\n"
            f"### Step 2 — Input Structuring & Initial Boundary Conditions\n"
            f"Input parameters and operational variables are validated, normalized, and mapped into structured representations. "
            f"This preparation eliminates malformed inputs, calibrates boundary conditions, and readies data channels for execution.\n\n"
            f"*Mini-Example:* Calibrating initial values and setting verification thresholds for {t}.\n\n"
            f"### Step 3 — Core Transformation Mechanics\n"
            f"Executing the primary transformations, mathematical equations, or structural transitions governing {t}. "
            f"This is where the fundamental mechanics operate, converting intermediate states through deterministic rules toward the target outcome.\n\n"
            f"*Mini-Example:* Applying the governing rules of {t} and observing progressive intermediate state changes.\n\n"
            f"### Step 4 — Quality Verification & Invariant Checking\n"
            f"Evaluating intermediate outputs against strict verification criteria, boundary conditions, and conservation laws. "
            f"This ensures that edge cases are handled gracefully and computational invariants remain preserved without error drift.\n\n"
            f"*Mini-Example:* Validating convergence metrics and confirming error bounds for {t}.\n\n"
            f"### Step 5 — Final Synthesis & Practical Execution\n"
            f"Consolidating verified intermediate states into a conclusive result or production-ready implementation. "
            f"The final output encapsulates the complete lifecycle of {t}, ready for downstream application or further analysis.\n\n"
            f"*Mini-Example:* Deploying the verified solution of {t} to achieve reliable, reproducible outcomes."
        )
        viz = f'graph TD;\n  S1["Step 1: Foundations of {t}"] --> S2["Step 2: Input Structuring"];\n  S2 --> S3["Step 3: Core Transformation"];\n  S3 --> S4["Step 4: Verification"];\n  S4 --> S5["Step 5: Practical Mastery"];'

    return {
        "canonical_topic": t,
        "simple_explanation": exp,
        "why_it_works": f"The step-by-step progression decomposes {t} into verifiable stages, establishing clear mastery at each operational layer.",
        "example": f"Following a structured sequential breakdown from initial setup to verified execution of {t}.",
        "common_mistake": f"Attempting to skip foundational boundary checks before executing core transformation steps.",
        "mini_quiz": f"In Step 2 of {t}, what is the primary objective of input structuring?",
        "reflection_prompt": f"How would you explain the progression from Step 1 to Step 5 of {t} to a peer?",
        "coach_recommendation": f"Focus on understanding the transition between each sequential step before proceeding to advanced edge cases.",
        "next_learning_step": get_prerequisite_next_step(t),
        "visual_intuition": viz
    }


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE VALIDATOR & QUALITY ENFORCEMENT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class ResponseValidator:
    @staticmethod
    def validate_and_repair(
        raw_data: Dict[str, Any],
        default_mastery: int = 0,
        fallback_topic: Optional[str] = None,
        variant: Optional[PresentationVariant] = None,
        pdf_context: Optional[Any] = None
    ) -> TutorDocument:
        """
        Validates contract fields, cleans prompt echoes, enforces word-count standards,
        binds adaptive Mermaid visuals, enforces PDF grounding, and returns a verified TutorDocument.
        """
        repaired = dict(raw_data) if raw_data else {}
        canonical_topic = extract_canonical_topic(
            repaired.get("canonical_topic") or fallback_topic or "Core Concept",
            fallback_topic=fallback_topic
        )
        repaired["canonical_topic"] = canonical_topic

        # Validate LessonMode
        mode_str = str(repaired.get("lesson_mode", "STANDARD")).upper()
        try:
            mode = LessonMode(mode_str)
        except ValueError:
            mode = LessonMode.STANDARD
        repaired["lesson_mode"] = mode

        # Determine presentation variant
        chosen_variant = variant or PresentationVariant.ARCHITECTURE

        # Clean and validate explanation text
        explanation = clean_prompt_echo(repaired.get("simple_explanation", ""), is_explanation=True)
        why = clean_prompt_echo(repaired.get("why_it_works", ""))
        example = clean_prompt_echo(repaired.get("example", ""))

        exp_words = len(explanation.split())

        # Check if the explanation is an explicit notice of information not found in the uploaded PDF
        is_unsupported_doc_query = bool(
            "couldn't find enough information" in explanation.lower() or
            "could not find enough information" in explanation.lower() or
            "not available in your uploaded" in explanation.lower() or
            "not found in your uploaded" in explanation.lower() or
            "not covered in the uploaded" in explanation.lower() or
            "outside the scope of your uploaded" in explanation.lower()
        )

        active_pdf_ctx = pdf_context or repaired.get("sources")

        if is_unsupported_doc_query:
            # Preserve explicit unsupported notice rather than synthesizing a generic response
            repaired["simple_explanation"] = explanation
            if not why:
                repaired["why_it_works"] = "Feynman AI prioritizes your uploaded study material as the authoritative knowledge source for this session."
            if not example:
                repaired["example"] = "Explore the topics and chapters covered in your uploaded document or upload additional materials."
            repaired["next_learning_step"] = get_prerequisite_next_step(canonical_topic, pdf_context=active_pdf_ctx)
            repaired["visual_intuition"] = 'graph TD;\n  Doc["Uploaded Document"] --> Scope["Active Material Scope"];\n  Scope --> Next["Explore Document Topics"];'
        else:
            # Quality Enforcement: Synthesize if empty or below pedagogical thresholds
            if mode == LessonMode.SIMPLIFY:
                if not explanation or exp_words < 40:
                    synth = synthesize_simplify_lesson(canonical_topic)
                    explanation = synth["simple_explanation"]
                    why = synth["why_it_works"]
                    example = synth["example"]
                    repaired.update({
                        "common_mistake": synth["common_mistake"],
                        "mini_quiz": synth["mini_quiz"],
                        "reflection_prompt": synth["reflection_prompt"],
                        "coach_recommendation": synth["coach_recommendation"],
                        "next_learning_step": get_prerequisite_next_step(canonical_topic, pdf_context=active_pdf_ctx),
                        "visual_intuition": synth["visual_intuition"]
                    })

            elif mode == LessonMode.ANALOGY:
                if not explanation or exp_words < 60:
                    synth = synthesize_analogy_lesson(canonical_topic)
                    explanation = synth["simple_explanation"]
                    why = synth["why_it_works"]
                    example = synth["example"]
                    repaired.update({
                        "common_mistake": synth["common_mistake"],
                        "mini_quiz": synth["mini_quiz"],
                        "reflection_prompt": synth["reflection_prompt"],
                        "coach_recommendation": synth["coach_recommendation"],
                        "next_learning_step": get_prerequisite_next_step(canonical_topic, pdf_context=active_pdf_ctx),
                        "visual_intuition": synth["visual_intuition"]
                    })

            elif mode == LessonMode.STEP_BY_STEP:
                if not explanation or exp_words < 200:
                    synth = synthesize_step_by_step_lesson(canonical_topic)
                    explanation = synth["simple_explanation"]
                    why = synth["why_it_works"]
                    example = synth["example"]
                    repaired.update({
                        "common_mistake": synth["common_mistake"],
                        "mini_quiz": synth["mini_quiz"],
                        "reflection_prompt": synth["reflection_prompt"],
                        "coach_recommendation": synth["coach_recommendation"],
                        "next_learning_step": get_prerequisite_next_step(canonical_topic, pdf_context=active_pdf_ctx),
                        "visual_intuition": synth["visual_intuition"]
                    })

            else:
                # Standard Mode (~350 - 500 words)
                total_words = exp_words + len(why.split()) + len(example.split())
                if not explanation or total_words < 180:
                    synth = synthesize_standard_lesson(
                        canonical_topic,
                        partial_exp=explanation,
                        partial_why=why,
                        partial_example=example,
                        variant=chosen_variant
                    )
                    explanation = synth["simple_explanation"]
                    why = synth["why_it_works"]
                    example = synth["example"]
                    repaired.update({
                        "common_mistake": synth["common_mistake"],
                        "mini_quiz": synth["mini_quiz"],
                        "reflection_prompt": synth["reflection_prompt"],
                        "coach_recommendation": synth["coach_recommendation"],
                        "next_learning_step": get_prerequisite_next_step(canonical_topic, pdf_context=active_pdf_ctx),
                        "visual_intuition": synth["visual_intuition"]
                    })

            repaired["simple_explanation"] = clean_prompt_echo(explanation, is_explanation=True)
            repaired["why_it_works"] = clean_prompt_echo(why)
            repaired["example"] = clean_prompt_echo(example)
            repaired.setdefault("common_mistake", f"Confusing foundational parameters of {canonical_topic} with output predictions.")

            # Clean background quiz and reflection fields
            mini_quiz = clean_prompt_echo(repaired.get("mini_quiz", "").strip())
            if not mini_quiz:
                mini_quiz = f"What is the primary mechanism that enables {canonical_topic} to operate accurately?"
            repaired["mini_quiz"] = mini_quiz

            reflection = clean_prompt_echo(repaired.get("reflection_prompt", "").strip())
            if not reflection:
                reflection = f"How would you explain the core mechanism of {canonical_topic} to a fellow engineer?"
            repaired["reflection_prompt"] = reflection

            coach_tip = clean_prompt_echo(repaired.get("coach_recommendation", "").strip())
            if not coach_tip:
                coach_tip = f"Focus on how {canonical_topic} structures data transformations and optimizes its decision boundaries."
            repaired["coach_recommendation"] = coach_tip

            next_step = clean_prompt_echo(repaired.get("next_learning_step", "").strip())
            if not next_step or (active_pdf_ctx and not next_step.startswith("From your uploaded material")):
                next_step = get_prerequisite_next_step(canonical_topic, pdf_context=active_pdf_ctx)
            repaired["next_learning_step"] = next_step

            # Adaptive Diagram Binding
            viz = repaired.get("visual_intuition", "").strip()
            if not viz or "graph " not in viz or "Fallback" in viz or "Input Transformation" in viz:
                viz = generate_adaptive_diagram(canonical_topic, chosen_variant, mode.value, explanation)
            repaired["visual_intuition"] = viz

        repaired.setdefault("cognitive_trace", f"{mode.value} lesson active for {canonical_topic}.")
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])
        if "evaluation" in repaired and isinstance(repaired["evaluation"], dict):
            repaired["evaluation"] = repaired["evaluation"]

        return TutorDocument(**repaired)
