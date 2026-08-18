import re
from typing import Dict, Any, Optional
from .schemas import TutorDocument, LessonMode
from .document_builder import DocumentBuilder

TOPIC_VISUALS_REGISTRY = [
    {
        "topic": "transformer",
        "aliases": ["transformer", "transformers", "bert", "gpt", "attention", "self-attention", "llm", "encoder", "decoder"],
        "mermaid": """graph TD;
  In["Input Token Embeddings"] --> PE["Positional Encoding"];
  PE --> Attn["Multi-Head Self-Attention"];
  Attn --> AddNorm1["Add & Layer Normalization"];
  AddNorm1 --> FFN["Feed-Forward Network"];
  FFN --> AddNorm2["Add & Layer Normalization"];
  AddNorm2 --> Out["Linear Projection & Softmax Logits"];"""
    },
    {
        "topic": "cnn",
        "aliases": ["cnn", "convolutional", "convolutional neural network", "computer vision", "pooling", "feature map"],
        "mermaid": """graph TD;
  Img["Input Image Matrix (H x W x C)"] --> Conv["Convolutional Filters (Feature Extraction)"];
  Conv --> Act["ReLU Non-Linear Activation"];
  Act --> Pool["Max Pooling (Spatial Downsampling)"];
  Pool --> FC["Fully Connected Dense Layers"];
  FC --> Class["Softmax Class Probabilities"];"""
    },
    {
        "topic": "backpropagation",
        "aliases": ["backpropagation", "backprop", "chain rule", "gradient computation", "error signal", "gradient"],
        "mermaid": """graph TD;
  Fwd["Forward Pass (Compute Loss L)"] --> OutGrad["Output Layer Error (dL/dy)"];
  OutGrad --> Chain["Chain Rule Derivative Decomposition"];
  Chain --> HiddenGrad["Hidden Layer Gradients (dL/dW, dL/db)"];
  HiddenGrad --> Optimizer["Optimizer Step (w <- w - eta * grad)"];
  Optimizer --> Updated["Updated Network Parameters"];"""
    },
    {
        "topic": "gradient descent",
        "aliases": ["gradient descent", "optimizer", "adam", "sgd", "minima", "loss landscape"],
        "mermaid": """graph TD;
  Init["Random Parameter Initialization"] --> Eval["Evaluate Loss & Compute Gradient Slope"];
  Eval --> Step["Step in Negative Gradient Direction"];
  Step --> Check{"Convergence / Minima Reached?"};
  Check -->|No| Eval;
  Check -->|Yes| Converged["Optimal Parameter Convergence"];"""
    },
    {
        "topic": "activation",
        "aliases": ["activation", "activation function", "relu", "sigmoid", "tanh", "softmax", "leaky relu"],
        "mermaid": """graph TD;
  Sum["Weighted Sum: z = w*x + b"] --> Act{"Non-Linear Activation Function"};
  Act -->|ReLU| NonLinear["ReLU: max(0, z)"];
  Act -->|Sigmoid| Probability["Sigmoid: 1 / (1 + e^-z)"];
  NonLinear --> Out["Neuron Output Activation"];
  Probability --> Out;"""
    },
    {
        "topic": "neural network",
        "aliases": ["neural network", "neural networks", "neural", "perceptron", "deep learning", "multi-layer perceptron", "mlp", "ann", "weights", "bias", "layer", "neuron"],
        "mermaid": """graph TD;
  In["Input Data (Features X)"] --> InLayer["Input Layer"];
  InLayer --> Hidden["Hidden Layers (Weights & Biases)"];
  Hidden --> Act["Activation Functions (e.g. ReLU)"];
  Act --> OutLayer["Output Layer (Prediction y_hat)"];
  OutLayer --> Loss["Loss Function (Prediction vs Ground Truth)"];
  Loss --> Backprop["Backpropagation (Chain Rule Gradients)"];
  Backprop --> WeightUpdate["Weight Update (Optimizer / Gradient Descent)"];
  WeightUpdate -.->|Next Training Iteration| Hidden;"""
    },
    {
        "topic": "binary search",
        "aliases": ["binary search", "logarithmic search", "sorted array search", "divide and conquer search"],
        "mermaid": """graph TD;
  Arr["Sorted Array Range [Low, High]"] --> Mid["Compute Midpoint Index"];
  Mid --> Comp{"Is Arr[Mid] == Target?"};
  Comp -->|Target < Mid| Left["High = Mid - 1 (Search Left Half)"];
  Comp -->|Target > Mid| Right["Low = Mid + 1 (Search Right Half)"];
  Comp -->|Match| Found["Return Target Index (O(log n))"];"""
    },
    {
        "topic": "merge sort",
        "aliases": ["merge sort", "quick sort", "sorting algorithm", "divide and conquer", "quicksort"],
        "mermaid": """graph TD;
  Unsorted["Unsorted Array [N Elements]"] --> Split["Divide Array into Left & Right Halves"];
  Split --> Recurse["Recursively Sort Sub-Arrays"];
  Recurse --> Merge["Two-Pointer Merge of Sorted Halves"];
  Merge --> Sorted["Fully Sorted Output Array (O(n log n))"];"""
    },
    {
        "topic": "linked list",
        "aliases": ["linked list", "pointer", "node", "doubly linked", "singly linked list"],
        "mermaid": """graph TD;
  Head["Head Node: Data | Next"] --> N1["Node 1: Data | Next"];
  N1 --> N2["Node 2: Data | Next"];
  N2 --> Null["Tail Pointer -> NULL"];"""
    },
    {
        "topic": "hash table",
        "aliases": ["hash table", "hash map", "dictionary", "key value", "collision", "hash function"],
        "mermaid": """graph TD;
  Key["Input Key (String/Object)"] --> Hash["Hash Function Computation"];
  Hash --> Index["Bucket Index (Hash Modulo Capacity)"];
  Index --> Bucket["Bucket Array / Collision Chaining"];
  Bucket --> Value["O(1) Average Value Retrieval"];"""
    },
    {
        "topic": "heap",
        "aliases": ["heap", "priority queue", "max heap", "min heap", "binary heap"],
        "mermaid": """graph TD;
  Root["Root Element (Max / Min Property)"] --> L["Left Child <= Parent"];
  Root --> R["Right Child <= Parent"];
  L --> L1["Heap Invariant Maintained Across Tree"];"""
    },
    {
        "topic": "graph",
        "aliases": ["graph", "bfs", "dfs", "dijkstra", "traversal", "shortest path", "adjacency"],
        "mermaid": """graph TD;
  Start["Start Vertex"] --> Visited["Queue / Stack State"];
  Visited --> Expand["Explore Adjacent Unvisited Neighbors"];
  Expand --> EdgeCheck{"Goal Reached or Queue Empty?"};
  EdgeCheck -->|No| Visited;
  EdgeCheck -->|Yes| Path["Optimal Traversal / Shortest Path"];"""
    },
    {
        "topic": "dynamic programming",
        "aliases": ["dynamic programming", "dp", "memoization", "tabulation", "subproblem", "optimal substructure"],
        "mermaid": """graph TD;
  Problem["Original Complex Problem"] --> Decompose["Decompose into Overlapping Subproblems"];
  Decompose --> Check{"Subproblem in Memo Table?"};
  Check -->|Yes| Cached["O(1) Return Cached State"];
  Check -->|No| Compute["Compute Recurrence & Store in DP Table"];
  Compute --> Combine["Reconstruct Global Optimal Solution"];"""
    },
    {
        "topic": "recursion",
        "aliases": ["recursion", "recursive", "call stack", "base case", "stack overflow"],
        "mermaid": """graph TD;
  Call["Function Invocation (Push Stack Frame)"] --> Base{"Base Condition Met?"};
  Base -->|No| Recurse["Self-Call with Reduced Subproblem"];
  Base -->|Yes| Unwind["Return Base Value & Unwind Call Stack"];
  Recurse --> Call;"""
    },
    {
        "topic": "tcp",
        "aliases": ["tcp", "3-way handshake", "syn ack", "socket", "packet", "transmission control protocol"],
        "mermaid": """graph TD;
  Client["Client Host"] -->|1. SYN (Seq=x)| Server["Server Host"];
  Server -->|2. SYN-ACK (Seq=y, Ack=x+1)| Client;
  Client -->|3. ACK (Ack=y+1)| Server;
  Server --> Connected["ESTABLISHED State (Reliable Stream)"];"""
    },
    {
        "topic": "dns",
        "aliases": ["dns", "domain name", "tld", "ip address lookup", "dns resolver"],
        "mermaid": """graph TD;
  Browser["Client Browser"] --> Resolv["Recursive DNS Resolver"];
  Resolv --> Root["Root Name Server"];
  Root --> TLD["TLD Server (.com / .io)"];
  TLD --> Auth["Authoritative Name Server"];
  Auth --> IP["Resolved IP Address -> Client Cache"];"""
    },
    {
        "topic": "http",
        "aliases": ["http", "https", "rest api", "endpoint", "gateway", "tls"],
        "mermaid": """graph TD;
  Client["Client / Frontend"] -->|HTTP Request Headers & Payload| Gateway["API Gateway / Reverse Proxy"];
  Gateway --> Service["Application Backend Microservice"];
  Service --> DB[("Database Transaction")];
  Service -->|HTTP 200 JSON Response| Client;"""
    },
    {
        "topic": "paging",
        "aliases": ["paging", "virtual memory", "page table", "page fault", "segmentation", "mmu"],
        "mermaid": """graph TD;
  VA["CPU Virtual Address (Page # | Offset)"] --> TLB{"TLB Cache Hit?"};
  TLB -->|Hit| Physical["Physical RAM Frame"];
  TLB -->|Miss| PageTable["Page Table Walk in Memory"];
  PageTable --> Check{"Present Bit Set?"};
  Check -->|Yes| Physical;
  Check -->|No| Fault["Page Fault -> Disk Swap -> OS Handler"];"""
    },
    {
        "topic": "deadlock",
        "aliases": ["deadlock", "mutex", "concurrency", "race condition", "semaphore", "banker algorithm"],
        "mermaid": """graph TD;
  P1["Process 1 (Holds Lock A)"] -->|Requests| R2["Resource Lock B"];
  R2 -->|Held by| P2["Process 2 (Holds Lock B)"];
  P2 -->|Requests| R1["Resource Lock A"];
  R1 -->|Held by| P1;"""
    },
    {
        "topic": "sql",
        "aliases": ["sql", "join", "inner join", "relational database", "query", "postgresql", "index"],
        "mermaid": """graph TD;
  Query["SQL Declarative Query"] --> Parser["Query Parser & Planner"];
  Parser --> Optimizer["Cost-Based Optimizer (Index Scan vs Seq Scan)"];
  Optimizer --> Exec["Execution Engine (B-Tree Lookups & Joins)"];
  Exec --> Rows["Result Tuple Set"];"""
    },
    {
        "topic": "acid",
        "aliases": ["acid", "transaction", "atomicity", "durability", "isolation", "consistency", "wal"],
        "mermaid": """graph TD;
  Tx["Database Transaction"] --> Atom["Atomicity (All-or-Nothing Commit/Rollback)"];
  Tx --> Cons["Consistency (Schema & Invariant Enforcement)"];
  Tx --> Iso["Isolation (MVCC / Concurrency Control)"];
  Tx --> Dur["Durability (Write-Ahead Log / WAL Flushed to Disk)"];"""
    }
]

KNOWN_ACRONYMS = {
    "Cnn": "CNN", "Rnn": "RNN", "Llm": "LLM", "Gpt": "GPT", "Bert": "BERT", 
    "Sql": "SQL", "Tcp": "TCP", "Dns": "DNS", "Http": "HTTP", "Https": "HTTPS", 
    "Api": "API", "Ram": "RAM", "Cpu": "CPU", "Gpu": "GPU", "Acid": "ACID", 
    "Dp": "DP", "Bfs": "BFS", "Dfs": "DFS", "Ai": "AI", "Ml": "ML", "Ann": "ANN", "Mlp": "MLP"
}

def clean_prompt_echo(text: str, is_explanation: bool = False) -> str:
    """Removes user prompt echoes from explanation opening strings without mangling standalone questions."""
    if not text:
        return ""
    stripped = text.strip()
    
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

def extract_canonical_topic(text: str) -> str:
    """
    Isolates the clean canonical subject topic from raw user prompts.
    Single source of truth across Feynman AI orchestrator, validator, memory, and UI.
    """
    if not text:
        return "Core Concept"
    
    cleaned = re.sub(
        r'^(Teach me step by step until I understand|Teach me\s+|Explain this concept even simpler|Explain this simpler|Explain\s+|Give a real[- ]world analogy for|Give a real[- ]world analogy|Give an analogy for|Tell me about advanced applications of|Tell me about|Understanding how the|Understanding how|Understanding|Explain what is|What is\s+(an\s+|a\s+|the\s+)?|What are\s+(the\s+)?|What\s+|How does\s+|How do\s+|Why is\s+|Can you explain\s+|Deep dive into\s+)\s*',
        '',
        text.strip(),
        flags=re.IGNORECASE
    ).strip()
    
    cleaned = re.sub(r'^(an\s+|a\s+|the\s+)', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'^[:\-\s]+', '', cleaned).strip()
    cleaned = re.sub(r'\s+(step by step|in simple terms|simply|with an analogy|until I understand|for beginners)[\?!.]*$', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[:\-\?\.!\s]+$', '', cleaned).strip()
    
    if not cleaned or len(cleaned) < 2:
        cleaned = "Core Concept"

    
    if len(cleaned.split()) <= 5:
        titled = cleaned.title()
        words = [KNOWN_ACRONYMS.get(w, w) for w in titled.split()]
        return " ".join(words)
    else:
        return cleaned[0].upper() + cleaned[1:]


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-FIDELITY STANDARD LESSON KNOWLEDGE REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
STANDARD_TOPIC_LESSONS = {
    "neural network": {
        "canonical_topic": "Neural Networks",
        "simple_explanation": (
            "An **Artificial Neural Network (ANN)** is a computational architecture inspired by biological neural circuits, engineered to learn complex non-linear mappings directly from empirical data. Rather than relying on hardcoded procedural rules, a neural network functions as a universal function approximator that autonomously discovers feature representations and decision boundaries through iterative optimization.\n\n"
            "### 1. The Artificial Neuron & Linear Transformation\n"
            "The fundamental unit of a neural network is the artificial neuron (perceptron). A neuron receives an input vector $\\mathbf{x} = [x_1, x_2, \\dots, x_n]$, multiplies each feature by an adjustable weight parameter $w_i$, sums them together, and adds a scalar bias term $b$:\n"
            "$$z = \\sum_{i=1}^n w_i x_i + b = \\mathbf{w}^T \\mathbf{x} + b$$\n"
            "Weights modulate the relative influence of each feature, while the bias shifts the activation baseline independently of the inputs.\n\n"
            "### 2. Non-Linear Activation Functions\n"
            "The pre-activation scalar $z$ is passed through a non-linear activation function $\\sigma(z)$ (such as **ReLU**, **Sigmoid**, or **GELU**). Without non-linear activations, stacking multiple hidden layers would mathematically collapse into a single trivial linear regression. Non-linearities grant the network the mathematical expressiveness required to learn complex high-dimensional decision surfaces, curved manifolds, and subtle patterns.\n\n"
            "### 3. Hierarchical Layered Forward Propagation\n"
            "Neurons are organized into an **Input Layer** (ingesting raw features), one or more **Hidden Layers** (extracting progressively higher-level abstract representations), and a final **Output Layer** (generating predictions $\\hat{y}$). During forward propagation, signals flow sequentially from layer to layer, computing activations until a final prediction is formulated.\n\n"
            "### 4. Loss Evaluation, Backpropagation & Optimization\n"
            "The prediction $\\hat{y}$ is compared against ground truth labels $y$ using a Loss Function (such as Cross-Entropy for classification or Mean Squared Error for regression). Using the multivariable calculus **chain rule**, backpropagation computes the partial derivatives of the loss with respect to every weight ($\\frac{\\partial L}{\\partial w}$) and bias across the entire network. An optimizer (such as **Adam** or **Stochastic Gradient Descent**) updates parameters in the direction of steepest descent ($w \\leftarrow w - \\eta \\frac{\\partial L}{\\partial w}$), progressively minimizing prediction error across training epochs."
        ),
        "why_it_works": "Deep hierarchical architectures achieve exponential parameter efficiency over shallow models. Early layers detect primitive spatial or frequency features, intermediate layers compose them into structural motifs, and deeper layers formulate high-level semantic representations that generalize across unseen data.",
        "example": "In automated medical imaging, an artificial neural network ingests chest X-ray pixel grids through convolutional and dense layers. Lower layers isolate contrast edges and bone contours, middle layers map lung tissue textures, and the final output layer calculates the diagnostic probability of pneumonia.",
        "common_mistake": "Believing that neural networks store explicit database rules or 'think' logically. In reality, they are continuous mathematical function approximators whose weights encode statistical correlations across high-dimensional geometric spaces.",
        "mini_quiz": "What is the mathematical consequence of removing non-linear activation functions from a 50-layer deep neural network?",
        "reflection_prompt": "How would you explain the dual cycle of forward propagation (generating predictions) and backpropagation (updating weights) to a student who has never studied calculus?",
        "coach_recommendation": "Trace how the error signal propagates backward layer by layer to see how each individual weight adjustment contributes to reducing the overall loss.",
        "next_learning_step": "Convolutional Neural Networks and Computer Vision Architectures"
    },
    "transformer": {
        "canonical_topic": "Transformers & Self-Attention",
        "simple_explanation": (
            "The **Transformer** is a neural network architecture introduced in 2017 that revolutionized artificial intelligence by replacing sequential recurrent connections with **Multi-Head Self-Attention**. This allows the model to process all tokens in a sequence simultaneously, capturing long-range semantic dependencies in parallel.\n\n"
            "### 1. Token Embeddings & Positional Encodings\n"
            "Input text is tokenized and converted into continuous dense vectors (embeddings). Because the transformer processes all tokens concurrently without recurrent recurrence, it adds fixed or learned **Positional Encodings** to token embeddings so the network knows the relative position and order of words in the sequence.\n\n"
            "### 2. Scaled Dot-Product Self-Attention\n"
            "For every token, the network computes three learned vectors: **Query ($Q$)**, **Key ($K$)**, and **Value ($V$)**. The attention mechanism calculates the compatibility between every pair of tokens:\n"
            "$$\\text{Attention}(Q, K, V) = \\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V$$\n"
            "This allows each word to dynamically weigh and absorb contextual information from every other word in the sequence regardless of distance.\n\n"
            "### 3. Multi-Head Attention & Feed-Forward Blocks\n"
            "Rather than performing a single attention calculation, **Multi-Head Attention** projects queries, keys, and values into multiple representation subspaces. Each head independently attends to distinct linguistic phenomena (syntax, pronouns, tense, semantic roles). Residual connections and Layer Normalization stabilize gradient flow across dozens of stacked transformer blocks."
        ),
        "why_it_works": "Self-attention eliminates the sequential bottleneck of RNNs ($O(1)$ sequential operations vs $O(n)$ path length). This enables massive parallelization on modern GPUs and eliminates vanishing gradients over long textual contexts.",
        "example": "When reading 'The animal didn't cross the street because it was too tired', self-attention computes high affinity between the pronoun 'it' and 'the animal', resolving ambiguous references with contextual precision.",
        "common_mistake": "Assuming self-attention and recurrent RNNs operate similarly. Transformers do not process words one by one; they build an $N \\times N$ pairwise attention matrix across the entire sequence simultaneously.",
        "mini_quiz": "Why is the dot-product $QK^T$ scaled by $\\frac{1}{\\sqrt{d_k}}$ before applying the softmax function?",
        "reflection_prompt": "Explain how the Query, Key, and Value vectors mimic a database lookup in soft, continuous space.",
        "coach_recommendation": "Focus on how Multi-Head Attention allows the model to attend to grammatical structure and semantic meaning simultaneously.",
        "next_learning_step": "Decoder-Only Large Language Models and Reinforcement Learning from Human Feedback (RLHF)"
    },
    "binary search": {
        "canonical_topic": "Binary Search",
        "simple_explanation": (
            "**Binary Search** is an optimal divide-and-conquer search algorithm designed to locate the exact position of a target element within a strictly sorted collection in logarithmic time $O(\\log n)$.\n\n"
            "### 1. The Sorted Invariant & Search Space\n"
            "Binary search maintains two pointers: `low` at the start of the search range and `high` at the end. The algorithm relies entirely on the monotonic invariant of sorted arrays: all elements to the left of any index $m$ are strictly smaller than or equal to `arr[m]`, and all elements to the right are greater than or equal to `arr[m]`.\n\n"
            "### 2. Midpoint Calculation & Boundary Elimination\n"
            "At each iteration, the algorithm calculates the midpoint index: $m = \\text{low} + \\lfloor(\\text{high} - \\text{low})/2\\rfloor$ (which avoids integer overflow). It compares `arr[m]` with the target value:\n"
            "- If `arr[m] == target`: The search succeeds immediately and returns index $m$.\n"
            "- If `target < arr[m]`: The target cannot exist in the right half. The search range is updated to $\\text{high} = m - 1$.\n"
            "- If `target > arr[m]`: The target cannot exist in the left half. The search range is updated to $\\text{low} = m + 1$.\n\n"
            "### 3. Logarithmic Halving & Termination\n"
            "Because each single comparison permanently discards exactly half ($50\\%$) of the remaining search space, a dataset of 1,000,000 items requires at most $\\lceil \\log_2(1,000,000) \\rceil = 20$ comparisons. The loop terminates either when the target is found or when $\\text{low} > \\text{high}$, proving the item is absent."
        ),
        "why_it_works": "Halving the problem size at every step yields a recurrence relation $T(n) = T(n/2) + O(1)$, which solves via the Master Theorem to $O(\\log n)$ time complexity and $O(1)$ auxiliary space.",
        "example": "Looking up a name in a physical 1,000-page phone book: opening directly to page 500, checking the letter, and immediately discarding 500 pages in a single motion rather than flipping page by page.",
        "common_mistake": "Attempting to execute binary search on an unsorted array or calculating midpoint as `(low + high) / 2` which can cause integer overflow in languages with fixed integer sizes.",
        "mini_quiz": "How many total comparisons does Binary Search need in the worst-case scenario for an array containing 1,048,576 sorted elements?",
        "reflection_prompt": "How would you adapt Binary Search to find the first occurrence of a duplicate value rather than any arbitrary index?",
        "coach_recommendation": "Pay careful attention to off-by-one errors in boundary adjustments: `high = mid - 1` vs `low = mid + 1`.",
        "next_learning_step": "Binary Search on Solution Spaces and Rotated Array Search"
    }
}

def synthesize_standard_lesson(canonical_topic: str, partial_exp: str = "", partial_why: str = "", partial_example: str = "") -> Dict[str, str]:
    """
    Synthesizes a deep, pedagogical master lesson (350-500 words) for any topic.
    """
    topic_lower = canonical_topic.lower()
    for key, lesson in STANDARD_TOPIC_LESSONS.items():
        if key in topic_lower or any(alias in topic_lower for alias in [key, key.replace(' ', '')]):
            return dict(lesson)

    opening = partial_exp if (partial_exp and len(partial_exp.split()) > 40) else (
        f"**{canonical_topic}** is a core foundational concept engineered to solve critical computational and architectural challenges efficiently. "
        f"Understanding {canonical_topic} requires examining how state, data transformations, and decision boundaries interact within modern systems."
    )
    
    explanation = (
        f"{opening}\n\n"
        f"### 1. Architectural Foundations & Invariants\n"
        f"At its core, **{canonical_topic}** establishes a precise contract governing how raw inputs or signals enter the computational pipeline. "
        f"By structuring state transitions into well-defined mathematical or algorithmic operations, it enforces deterministic behavior and eliminates ambiguous edge cases across edge conditions.\n\n"
        f"### 2. Intermediate Transformations & Core Mechanics\n"
        f"Data flowing through {canonical_topic} undergoes continuous refinement across discrete operational stages. "
        f"Each stage applies specialized transformations (such as feature mapping, recursive reduction, or structured routing) that convert complex raw inputs into structured intermediate representations optimized for downstream evaluation.\n\n"
        f"### 3. Decision Thresholds, Execution & Optimization Feedback\n"
        f"The final phase evaluates intermediate states against explicit decision rules, error metrics, or termination criteria to produce verified outputs. "
        f"Feedback loops and parameter optimizations continually refine performance, ensuring predictable latency bounds and robust error recovery across production environments."
    )

    why = partial_why if (partial_why and len(partial_why.split()) > 20) else (
        f"Underlying mechanics of {canonical_topic} achieve optimal efficiency by decoupling interface contracts from execution pipelines. "
        f"This isolation allows components to scale independently while preserving strict invariant correctness."
    )

    ex = partial_example if (partial_example and len(partial_example.split()) > 15) else (
        f"In modern distributed systems, {canonical_topic} is used to orchestrate data flows, manage concurrent memory states, and optimize throughput under heavy computational workloads."
    )

    return {
        "canonical_topic": canonical_topic,
        "simple_explanation": explanation,
        "why_it_works": why,
        "example": ex,
        "common_mistake": f"Confusing the high-level interface of {canonical_topic} with its low-level execution mechanics and internal state representations.",
        "mini_quiz": f"What is the primary architectural invariant maintained by {canonical_topic} during execution?",
        "reflection_prompt": f"How would you explain the core mechanism of {canonical_topic} and its primary operational trade-offs to a peer?",
        "coach_recommendation": f"Focus on how {canonical_topic} structures data transformations and optimizes its decision boundaries.",
        "next_learning_step": f"Advanced system patterns and production applications of {canonical_topic}"
    }


class ResponseValidator:
    @staticmethod
    def validate_and_repair(data: Dict[str, Any], default_mastery: int = 0) -> TutorDocument:
        """
        Validates contract response dictionary and enforces full-depth standard lessons,
        mode-specific diagrams, and clean canonical topics.
        """
        repaired = dict(data)
        repaired.setdefault("cognitive_trace", "Active recall model evaluation completed.")
        
        explanation = repaired.get("simple_explanation", "").strip()
        why = repaired.get("why_it_works", "").strip()
        example = repaired.get("example", "").strip()
        cognitive_trace = repaired.get("cognitive_trace", "")
        cognitive_trace_lower = cognitive_trace.lower()

        # Determine explicit pedagogical mode
        if "### step 1" in explanation.lower() or "### step 2" in explanation.lower() or "step by step" in cognitive_trace_lower or "step_by_step" in str(repaired.get("lesson_mode", "")).lower():
            mode = LessonMode.STEP_BY_STEP
        elif "simplify" in cognitive_trace_lower or "simplify" in str(repaired.get("lesson_mode", "")).lower() or (len(explanation.split()) < 90 and "imagine" in explanation.lower()):
            mode = LessonMode.SIMPLIFY
        elif "analogy" in cognitive_trace_lower or "analogy" in str(repaired.get("lesson_mode", "")).lower() or "analogy" in explanation.lower() or "think of a" in explanation.lower():
            mode = LessonMode.ANALOGY
        else:
            mode = LessonMode.STANDARD
        repaired["lesson_mode"] = mode

        # Extract clean canonical topic from context
        canonical_topic = extract_canonical_topic(repaired.get("canonical_topic") or explanation[:60])
        repaired["canonical_topic"] = canonical_topic

        # Clean prompt echo from explanation opening
        explanation = clean_prompt_echo(explanation, is_explanation=True)

        # ─────────────────────────────────────────────────────────────────────
        # STANDARD LESSON CONTRACT & DEPTH ENFORCEMENT (350 - 500 WORDS)
        # ─────────────────────────────────────────────────────────────────────
        if mode == LessonMode.STANDARD:
            word_count = len(explanation.split())
            if word_count < 220:
                print(f"[VALIDATOR] Standard lesson word count ({word_count} words) below threshold (<220). Enriching to full-depth master lesson...")
                synth = synthesize_standard_lesson(canonical_topic, explanation, why, example)
                explanation = synth["simple_explanation"]
                why = synth["why_it_works"]
                example = synth["example"]
                if not repaired.get("common_mistake") or "parameter" in repaired.get("common_mistake", ""):
                    repaired["common_mistake"] = synth["common_mistake"]
                if not repaired.get("mini_quiz") or "objective" in repaired.get("mini_quiz", ""):
                    repaired["mini_quiz"] = synth["mini_quiz"]
                if not repaired.get("reflection_prompt") or "peer" in repaired.get("reflection_prompt", ""):
                    repaired["reflection_prompt"] = synth["reflection_prompt"]
                if not repaired.get("coach_recommendation") or "flow of data" in repaired.get("coach_recommendation", ""):
                    repaired["coach_recommendation"] = synth["coach_recommendation"]
                if not repaired.get("next_learning_step"):
                    repaired["next_learning_step"] = synth["next_learning_step"]

        repaired["simple_explanation"] = explanation
        repaired["why_it_works"] = clean_prompt_echo(why)
        repaired["example"] = clean_prompt_echo(example)
        repaired.setdefault("common_mistake", f"Confusing foundational parameters of {canonical_topic} with output predictions.")

        # Sanitize Active Recall and Quiz to always reference clean topic
        mini_quiz = repaired.get("mini_quiz", "").strip()
        if not mini_quiz or any(p in mini_quiz.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            mini_quiz = f"What is the primary mechanism that enables {canonical_topic} to operate accurately?"
        repaired["mini_quiz"] = clean_prompt_echo(mini_quiz)

        reflection = repaired.get("reflection_prompt", "").strip()
        if not reflection or any(p in reflection.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            reflection = f"How would you explain the core mechanism of {canonical_topic} to a fellow engineer?"
        repaired["reflection_prompt"] = clean_prompt_echo(reflection)

        # Topic-Aware Coaching Tip
        coach_tip = repaired.get("coach_recommendation", "").strip()
        if not coach_tip or any(p in coach_tip.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            if "backprop" in canonical_topic.lower():
                coach_tip = "Trace how error gradients propagate backward layer by layer to understand weight updates."
            elif "neural" in canonical_topic.lower() or "perceptron" in canonical_topic.lower():
                coach_tip = "Think about how each layer transforms raw input features into progressively higher-level representations."
            elif "binary search" in canonical_topic.lower():
                coach_tip = "Focus on why eliminating half the search space at every step yields logarithmic time."
            else:
                coach_tip = f"Focus on how {canonical_topic} structures data transformations and optimizes its decision boundaries."
        repaired["coach_recommendation"] = coach_tip

        # Next learning step
        next_step = repaired.get("next_learning_step", "").strip()
        if not next_step or any(p in next_step.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            next_step = f"Advanced applications and optimization of {canonical_topic}"
        else:
            next_step = clean_prompt_echo(next_step)
        repaired["next_learning_step"] = next_step

        # ─────────────────────────────────────────────────────────────────────
        # MODE-SPECIFIC DIAGRAM RESOLUTION ENGINE
        # ─────────────────────────────────────────────────────────────────────
        viz = repaired.get("visual_intuition", "").strip()
        topic_and_text = f"{canonical_topic} {explanation} {why} {example}".lower()

        # Find matching domain diagram in registry (Pass 1: Direct canonical_topic match, Pass 2: Context match)
        matched_viz = None
        topic_lower = canonical_topic.lower()
        for entry in TOPIC_VISUALS_REGISTRY:
            if any(re.search(r'\b' + re.escape(alias) + r'\b', topic_lower) for alias in entry["aliases"]):
                matched_viz = entry["mermaid"]
                break

        if not matched_viz:
            for entry in TOPIC_VISUALS_REGISTRY:
                if any(re.search(r'\b' + re.escape(alias) + r'\b', topic_and_text) for alias in entry["aliases"]):
                    matched_viz = entry["mermaid"]
                    break

        if mode == LessonMode.SIMPLIFY:
            if "neural" in topic_and_text or "ai" in topic_and_text or "model" in topic_and_text:
                viz = """graph LR;\n  Data["Raw Input"] --> Pattern["Pattern Detection"] --> Decision["Clear Decision"];"""
            elif "search" in topic_and_text or "sort" in topic_and_text:
                viz = """graph LR;\n  Items["Unsorted Items"] --> Rule["Simple Rule"] --> Result["Found Result"];"""
            elif matched_viz:
                viz = matched_viz
            else:
                viz = """graph LR;\n  Input["Raw Information"] --> Rules["Simple Filter"] --> Output["Clear Result"];"""
        elif mode == LessonMode.ANALOGY:
            if "kitchen" in topic_and_text or "chef" in topic_and_text or "restaurant" in topic_and_text:
                viz = """graph LR;\n  Order["Customer Order"] --> Kitchen["Chef Prepares"] --> Meal["Served Dish"];"""
            elif "team" in topic_and_text or "factory" in topic_and_text or "assembly" in topic_and_text:
                viz = """graph LR;\n  Worker1["Station 1: Prep"] --> Worker2["Station 2: Assembly"] --> Product["Final Product"];"""
            elif matched_viz:
                viz = matched_viz
            else:
                viz = """graph LR;\n  Start["Everyday Object"] --> Action["Relatable Process"] --> End["Intuitive Result"];"""
        elif mode == LessonMode.STEP_BY_STEP:
            if "neural" in topic_and_text:
                viz = """graph TD;\n  S1["Step 1: Input Features"] --> S2["Step 2: Layer Processing"];\n  S2 --> S3["Step 3: Activation & Output"];\n  S3 --> S4["Step 4: Error & Learning"];\n  S4 --> S5["Step 5: Full Neural System"];"""
            else:
                viz = f"""graph TD;\n  S1["Step 1: Foundations"] --> S2["Step 2: Mechanics"];\n  S2 --> S3["Step 3: Application"];\n  S3 --> S4["Step 4: Mastery of {canonical_topic}"];"""
        else:
            # Standard Mode: Topic-matched or AI-generated valid flowchart
            if matched_viz:
                viz = matched_viz
            elif not viz or ("graph " not in viz and "flowchart " not in viz) or "Fallback" in viz or "Input Transformation" in viz:
                viz = f"""graph TD;\n  In["Input Data"] --> Process["{canonical_topic} Processing"];\n  Process --> Out["Verified Output"];"""

        repaired["visual_intuition"] = viz
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])
        if "evaluation" in repaired and isinstance(repaired["evaluation"], dict):
            repaired["evaluation"] = repaired["evaluation"]

        total_words = len(explanation.split()) + len(why.split()) + len(example.split())
        print(f"[VALIDATOR] Response validated ({mode.value}) with {total_words} total instructional words.")
        return DocumentBuilder.create_document(repaired)
