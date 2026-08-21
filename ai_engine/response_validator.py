import re
from typing import Dict, Any, Optional
from .schemas import TutorDocument, LessonMode
from .document_builder import DocumentBuilder

TOPIC_VISUALS_REGISTRY = [
    {
        "topic": "transformer",
        "aliases": ["transformer", "transformers", "bert", "gpt", "attention", "self-attention", "llm", "encoder", "decoder"],
        "mermaid": """graph TD;
  In["Tokens"] --> PE["Positional Encoding"];
  PE --> Attn["Self-Attention"];
  Attn --> AddNorm1["Add & Norm"];
  AddNorm1 --> FFN["Feed-Forward"];
  FFN --> AddNorm2["Add & Norm"];
  AddNorm2 --> Out["Softmax Logits"];"""
    },
    {
        "topic": "cnn",
        "aliases": ["cnn", "convolutional", "convolutional neural network", "computer vision", "pooling", "feature map"],
        "mermaid": """graph TD;
  Img["Input Image"] --> Conv["Convolution"];
  Conv --> Act["ReLU"];
  Act --> Pool["Pooling"];
  Pool --> FC["Dense Layers"];
  FC --> Class["Prediction"];"""
    },
    {
        "topic": "backpropagation",
        "aliases": ["backpropagation", "backprop", "chain rule", "gradient computation", "error signal", "gradient"],
        "mermaid": """graph TD;
  Fwd["Forward Pass"] --> OutGrad["Output Loss"];
  OutGrad --> Chain["Chain Rule"];
  Chain --> HiddenGrad["Layer Gradients"];
  HiddenGrad --> Optimizer["Optimizer Step"];
  Optimizer --> Updated["Updated Weights"];"""
    },
    {
        "topic": "gradient descent",
        "aliases": ["gradient descent", "optimizer", "adam", "sgd", "minima", "loss landscape"],
        "mermaid": """graph TD;
  Init["Initialize"] --> Eval["Compute Gradient"];
  Eval --> Step["Step Downhill"];
  Step --> Check{"Converged?"};
  Check -->|No| Eval;
  Check -->|Yes| Converged["Optimal Minima"];"""
    },
    {
        "topic": "activation",
        "aliases": ["activation", "activation function", "relu", "sigmoid", "tanh", "softmax", "leaky relu"],
        "mermaid": """graph TD;
  Sum["Weighted Sum z"] --> Act{"Activation"};
  Act -->|ReLU| NonLinear["ReLU: max(0,z)"];
  Act -->|Sigmoid| Probability["Sigmoid: 1/(1+e^-z)"];
  NonLinear --> Out["Neuron Output"];
  Probability --> Out;"""
    },
    {
        "topic": "neural network",
        "aliases": ["neural network", "neural networks", "neural", "perceptron", "deep learning", "multi-layer perceptron", "mlp", "ann", "weights", "bias", "layer", "neuron"],
        "mermaid": """graph TD;
  In["Input Features"] --> InLayer["Input Layer"];
  InLayer --> Hidden["Hidden Layers"];
  Hidden --> Act["Activation"];
  Act --> OutLayer["Output Layer"];
  OutLayer --> Loss["Loss Function"];
  Loss --> Backprop["Backpropagation"];
  Backprop --> WeightUpdate["Weight Update"];
  WeightUpdate -.->|Next Epoch| Hidden;"""
    },
    {
        "topic": "binary search",
        "aliases": ["binary search", "logarithmic search", "sorted array search", "divide and conquer search"],
        "mermaid": """graph TD;
  Arr["Sorted Array"] --> Mid["Compute Midpoint"];
  Mid --> Comp{"arr[Mid] == Target?"};
  Comp -->|Target < Mid| Left["Search Left Half"];
  Comp -->|Target > Mid| Right["Search Right Half"];
  Comp -->|Match| Found["Target Found"];"""
    },
    {
        "topic": "merge sort",
        "aliases": ["merge sort", "quick sort", "sorting algorithm", "divide and conquer", "quicksort"],
        "mermaid": """graph TD;
  Unsorted["Unsorted Array"] --> Split["Divide Array"];
  Split --> Recurse["Recursive Sort"];
  Recurse --> Merge["Merge Halves"];
  Merge --> Sorted["Sorted Array"];"""
    },
    {
        "topic": "linked list",
        "aliases": ["linked list", "pointer", "node", "doubly linked", "singly linked list"],
        "mermaid": """graph TD;
  Head["Head Node"] --> N1["Node 1"];
  N1 --> N2["Node 2"];
  N2 --> Null["NULL Pointer"];"""
    },
    {
        "topic": "hash table",
        "aliases": ["hash table", "hash map", "dictionary", "key value", "collision", "hash function"],
        "mermaid": """graph TD;
  Key["Input Key"] --> Hash["Hash Function"];
  Hash --> Index["Bucket Index"];
  Index --> Bucket["Bucket Chaining"];
  Bucket --> Value["O(1) Value"];"""
    },
    {
        "topic": "heap",
        "aliases": ["heap", "priority queue", "max heap", "min heap", "binary heap"],
        "mermaid": """graph TD;
  Root["Root Node"] --> L["Left Child"];
  Root --> R["Right Child"];
  L --> L1["Heap Invariant"];"""
    },
    {
        "topic": "graph",
        "aliases": ["graph", "bfs", "dfs", "dijkstra", "traversal", "shortest path", "adjacency"],
        "mermaid": """graph TD;
  Start["Start Vertex"] --> Visited["Visited State"];
  Visited --> Expand["Explore Neighbors"];
  Expand --> EdgeCheck{"Goal Reached?"};
  EdgeCheck -->|No| Visited;
  EdgeCheck -->|Yes| Path["Shortest Path"];"""
    },
    {
        "topic": "dynamic programming",
        "aliases": ["dynamic programming", "dp", "memoization", "tabulation", "subproblem", "optimal substructure"],
        "mermaid": """graph TD;
  Problem["Complex Problem"] --> Decompose["Subproblems"];
  Decompose --> Check{"In Memo Table?"};
  Check -->|Yes| Cached["Return Cached"];
  Check -->|No| Compute["Compute Recurrence"];
  Compute --> Combine["Optimal Solution"];"""
    },
    {
        "topic": "recursion",
        "aliases": ["recursion", "recursive", "call stack", "base case", "stack overflow"],
        "mermaid": """graph TD;
  Call["Function Call"] --> Base{"Base Case Met?"};
  Base -->|No| Recurse["Self-Call"];
  Base -->|Yes| Unwind["Unwind Stack"];
  Recurse --> Call;"""
    },
    {
        "topic": "tcp",
        "aliases": ["tcp", "3-way handshake", "syn ack", "socket", "packet", "transmission control protocol"],
        "mermaid": """graph TD;
  Client["Client"] -->|1. SYN| Server["Server"];
  Server -->|2. SYN-ACK| Client;
  Client -->|3. ACK| Server;
  Server --> Connected["Established Stream"];"""
    },
    {
        "topic": "dns",
        "aliases": ["dns", "domain name", "tld", "ip address lookup", "dns resolver"],
        "mermaid": """graph TD;
  Browser["Browser"] --> Resolv["DNS Resolver"];
  Resolv --> Root["Root Server"];
  Root --> TLD["TLD Server"];
  TLD --> Auth["Authoritative Server"];
  Auth --> IP["Resolved IP"];"""
    },
    {
        "topic": "http",
        "aliases": ["http", "https", "rest api", "endpoint", "gateway", "tls"],
        "mermaid": """graph TD;
  Client["Client App"] -->|HTTP Request| Gateway["API Gateway"];
  Gateway --> Service["Backend Service"];
  Service --> DB[("Database")];
  Service -->|JSON 200| Client;"""
    },
    {
        "topic": "paging",
        "aliases": ["paging", "virtual memory", "page table", "page fault", "segmentation", "mmu"],
        "mermaid": """graph TD;
  VA["Virtual Address"] --> TLB{"TLB Hit?"};
  TLB -->|Hit| Physical["Physical RAM"];
  TLB -->|Miss| PageTable["Page Table Walk"];
  PageTable --> Check{"Present Bit?"};
  Check -->|Yes| Physical;
  Check -->|No| Fault["Page Fault Handler"];"""
    },
    {
        "topic": "deadlock",
        "aliases": ["deadlock", "mutex", "concurrency", "race condition", "semaphore", "banker algorithm"],
        "mermaid": """graph TD;
  P1["Process 1 (Holds Lock A)"] -->|Requests| R2["Lock B"];
  R2 -->|Held by| P2["Process 2 (Holds Lock B)"];
  P2 -->|Requests| R1["Lock A"];
  R1 -->|Held by| P1;"""
    },
    {
        "topic": "sql",
        "aliases": ["sql", "join", "inner join", "relational database", "query", "postgresql", "index"],
        "mermaid": """graph TD;
  Query["SQL Query"] --> Parser["Parser & Planner"];
  Parser --> Optimizer["Query Optimizer"];
  Optimizer --> Exec["Execution Engine"];
  Exec --> Rows["Result Rows"];"""
    },
    {
        "topic": "acid",
        "aliases": ["acid", "transaction", "atomicity", "durability", "isolation", "consistency", "wal"],
        "mermaid": """graph TD;
  Tx["Transaction"] --> Atom["Atomicity (All/None)"];
  Tx --> Cons["Consistency (Rules)"];
  Tx --> Iso["Isolation (Concurrency)"];
  Tx --> Dur["Durability (WAL Log)"];"""
    }
]

KNOWN_ACRONYMS = {
    "Cnn": "CNN", "Rnn": "RNN", "Llm": "LLM", "Gpt": "GPT", "Bert": "BERT", 
    "Sql": "SQL", "Tcp": "TCP", "Dns": "DNS", "Http": "HTTP", "Https": "HTTPS", 
    "Api": "API", "Ram": "RAM", "Cpu": "CPU", "Gpu": "GPU", "Acid": "ACID", 
    "Dp": "DP", "Bfs": "BFS", "Dfs": "DFS", "Ai": "AI", "Ml": "ML", "Ann": "ANN", "Mlp": "MLP"
}

def clean_prompt_echo(text: str, is_explanation: bool = False) -> str:
    """Removes user prompt echoes and any accidental diagram code from explanation opening strings."""
    if not text:
        return ""
    stripped = text.strip()
    # Strip any accidental Mermaid block leakage from text
    stripped = re.sub(r'```mermaid[\s\S]*?```', '', stripped, flags=re.IGNORECASE).strip()
    stripped = re.sub(r'^\s*graph\s+(LR|TD|TB|RL|BT)[\s\S]*?;', '', stripped, flags=re.IGNORECASE).strip()
    
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
# PREREQUISITE-AWARE NEXT LEARNING STEPS
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
    "linked list": "Doubly Linked Lists and Fast-and-Slow Pointer Cycles",
    "hash table": "Collision Resolution: Open Addressing vs Separate Chaining",
    "graph": "Breadth-First Search (BFS) vs Depth-First Search (DFS) Traversal",
    "dynamic programming": "Memoization vs Tabulation: The 0/1 Knapsack Problem"
}

def get_prerequisite_next_step(canonical_topic: str) -> str:
    topic_lower = canonical_topic.lower()
    for key, step in TOPIC_NEXT_STEPS.items():
        if key in topic_lower:
            return step
    return f"Intermediate concepts and real-world implementations of {canonical_topic}"


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-FIDELITY STANDARD LESSON KNOWLEDGE REPOSITORY (350 - 500 WORDS)
# ─────────────────────────────────────────────────────────────────────────────
STANDARD_TOPIC_LESSONS = {
    "cnn": {
        "canonical_topic": "Convolutional Neural Networks",
        "simple_explanation": (
            "A **Convolutional Neural Network (CNN)** is a specialized deep learning architecture engineered specifically for grid-structured data such as images, audio spectrograms, and video streams. Unlike fully connected networks that flatten spatial dimensions into unstructured 1D arrays, CNNs exploit translation equivariance and parameter sharing to extract localized hierarchical features directly from raw input pixels.\n\n"
            "### 1. Convolutional Kernels & Feature Maps\n"
            "Rather than connecting every input pixel to every neuron, small parameterized matrices called **filters (kernels)** slide across the input with a fixed stride and padding. At each window position, the kernel computes a 2D cross-correlation against the receptive field:\n"
            "$$S(i, j) = (I * K)(i, j) = \\sum_m \\sum_n I(i+m, j+n) K(m, n)$$\n"
            "This sliding dot-product produces **Feature Maps** that detect invariant low-level visual features such as contrast edges, orientations, textures, and gradient shifts across the entire image.\n\n"
            "### 2. Non-Linear Activation & Rectified Linear Units\n"
            "Each scalar in the feature map passes through an activation function $\\text{ReLU}(z) = \\max(0, z)$. Clamping negative values to zero creates sparse representations, accelerates gradient descent convergence, and prevents mathematical collapse across stacked convolutional layers.\n\n"
            "### 3. Spatial Pooling & Downsampling\n"
            "To achieve translation invariance and shrink memory consumption, **Max Pooling** layers extract the maximum activation across small windows (e.g. $2 \\times 2$ with stride 2). This downsamples spatial resolution by 75% while preserving dominant structural features and expanding the effective receptive field of subsequent layers.\n\n"
            "### 4. Dense Classification & Softmax Output\n"
            "Final high-level feature maps are flattened into a 1D vector and fed into fully connected dense layers that synthesize abstract motifs into global reasoning. The output layer generates class probabilities using the Softmax function: $\\sigma(\\mathbf{z})_i = \\frac{e^{z_i}}{\\sum_j e^{z_j}}$."
        ),
        "why_it_works": "Parameter sharing across sliding kernels reduces parameter count exponentially compared to standard dense layers ($O(K^2)$ vs $O(H \\cdot W)$), eliminating catastrophic overfitting on high-resolution image matrices while preserving 2D spatial locality.",
        "example": "In autonomous driving systems, a CNN receives real-time camera frames: early layers isolate lane boundary contrast lines, intermediate layers recognize vehicle silhouettes and pedestrian postures, and dense layers trigger emergency braking actuations.",
        "common_mistake": "Believing that CNNs can only process 2D images. CNNs are widely utilized for 1D temporal sequences (audio waveforms, genetic DNA sequences) and 3D spatial grids (MRI scans and LiDAR point clouds).",
        "mini_quiz": "Why does parameter sharing in convolutional kernels make CNNs significantly more efficient than fully connected networks for processing large images?",
        "reflection_prompt": "Explain the difference between Convolutional layers extracting localized spatial features and Fully Connected layers performing global reasoning.",
        "coach_recommendation": "Track how the spatial height and width decrease through pooling while the channel depth increases across successive convolutional layers.",
        "next_learning_step": "Padding, Stride, and Spatial Downsampling with Pooling",
        "visual_intuition": 'graph TD;\n  Img["Input Image"] --> Conv["Convolution"];\n  Conv --> Act["ReLU"];\n  Act --> Pool["Pooling"];\n  Pool --> FC["Dense Layers"];\n  FC --> Class["Prediction"];'
    },
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
        "next_learning_step": "Convolutional Neural Networks and Spatial Features",
        "visual_intuition": 'graph TD;\n  In["Input Features"] --> InLayer["Input Layer"];\n  InLayer --> Hidden["Hidden Layers"];\n  Hidden --> Act["Activation"];\n  Act --> OutLayer["Output Layer"];\n  OutLayer --> Loss["Loss Function"];\n  Loss --> Backprop["Backpropagation"];\n  Backprop --> WeightUpdate["Weight Update"];\n  WeightUpdate -.->|Next Epoch| Hidden;'
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
        "next_learning_step": "Scaled Dot-Product Attention Mechanics and Multi-Head Projections",
        "visual_intuition": 'graph TD;\n  In["Tokens"] --> PE["Positional Encoding"];\n  PE --> Attn["Self-Attention"];\n  Attn --> AddNorm1["Add & Norm"];\n  AddNorm1 --> FFN["Feed-Forward"];\n  FFN --> AddNorm2["Add & Norm"];\n  AddNorm2 --> Out["Softmax Logits"];'
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
        "next_learning_step": "Binary Search on Monotonic Ranges and Lower Bound Search",
        "visual_intuition": 'graph TD;\n  Arr["Sorted Array"] --> Mid["Compute Midpoint"];\n  Mid --> Comp{"arr[Mid] == Target?"};\n  Comp -->|Target < Mid| Left["Search Left Half"];\n  Comp -->|Target > Mid| Right["Search Right Half"];\n  Comp -->|Match| Found["Target Found"];'
    }
}

def synthesize_standard_lesson(canonical_topic: str, partial_exp: str = "", partial_why: str = "", partial_example: str = "") -> Dict[str, str]:
    """
    Synthesizes a deep, pedagogical master lesson (350-500 words) for any topic.
    """
    topic_lower = canonical_topic.lower()
    if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
        return dict(STANDARD_TOPIC_LESSONS["cnn"])
    elif any(k in topic_lower for k in ["transformer", "attention", "self-attention", "bert", "gpt"]):
        return dict(STANDARD_TOPIC_LESSONS["transformer"])
    elif any(k in topic_lower for k in ["binary search"]):
        return dict(STANDARD_TOPIC_LESSONS["binary search"])
    elif any(k in topic_lower for k in ["neural", "perceptron", "deep learning", "ann", "mlp"]):
        return dict(STANDARD_TOPIC_LESSONS["neural network"])

    for key, lesson in STANDARD_TOPIC_LESSONS.items():
        if key in topic_lower or any(alias in topic_lower for alias in [key, key.replace(' ', '')]):
            return dict(lesson)

    opening = partial_exp if (partial_exp and len(partial_exp.split()) > 40) else (
        f"**{canonical_topic}** is a foundational concept engineered to solve critical computational and architectural challenges. "
        f"Understanding {canonical_topic} requires examining how state, data transformations, and decision boundaries interact within modern systems."
    )
    
    explanation = (
        f"{opening}\n\n"
        f"### 1. Architectural Foundations & Invariants\n"
        f"At its core, **{canonical_topic}** establishes a precise contract governing how raw inputs enter the computational pipeline. "
        f"By structuring state transitions into well-defined operations, it enforces deterministic behavior and eliminates ambiguous edge cases.\n\n"
        f"### 2. Intermediate Transformations & Core Mechanics\n"
        f"Data flowing through {canonical_topic} undergoes continuous refinement across discrete operational stages. "
        f"Each stage applies specialized transformations that convert complex raw inputs into structured intermediate representations optimized for downstream evaluation.\n\n"
        f"### 3. Decision Thresholds & Optimization Feedback\n"
        f"The final phase evaluates intermediate states against explicit decision rules to produce verified outputs. "
        f"Feedback loops continually refine performance, ensuring predictable latency bounds and robust execution across environments."
    )

    why = partial_why if (partial_why and len(partial_why.split()) > 20) else (
        f"Underlying mechanics of {canonical_topic} achieve optimal efficiency by decoupling interface contracts from execution pipelines."
    )

    ex = partial_example if (partial_example and len(partial_example.split()) > 15) else (
        f"In modern systems, {canonical_topic} orchestrates data flows, manages concurrent state, and optimizes computational throughput."
    )

    return {
        "canonical_topic": canonical_topic,
        "simple_explanation": explanation,
        "why_it_works": why,
        "example": ex,
        "common_mistake": f"Confusing the high-level interface of {canonical_topic} with its low-level execution mechanics and internal representations.",
        "mini_quiz": f"What is the primary architectural invariant maintained by {canonical_topic} during execution?",
        "reflection_prompt": f"How would you explain the core mechanism of {canonical_topic} and its primary operational trade-offs to a peer?",
        "coach_recommendation": f"Focus on how {canonical_topic} structures data transformations and optimizes its decision boundaries.",
        "next_learning_step": get_prerequisite_next_step(canonical_topic),
        "visual_intuition": f'graph TD;\n  In["Input Data"] --> Process["{canonical_topic} Core Logic"];\n  Process --> Out["Verified Output"];'
    }


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-FIDELITY ANALOGY KNOWLEDGE REPOSITORY (120 - 180 WORDS)
# ─────────────────────────────────────────────────────────────────────────────
ANALOGY_TOPIC_LESSONS = {
    "cnn": {
        "canonical_topic": "Convolutional Neural Networks",
        "simple_explanation": (
            "Think of a **Convolutional Neural Network (CNN)** like a team of detectives examining a large mystery photograph.\n\n"
            "• **Inspectors with Magnifying Glasses (Convolutional Filters):** Detectives slide small magnifying glasses across the photo patch by patch, hunting for basic local clues—a sharp edge, a color corner, or a curve.\n"
            "• **Clue Map Notepads (Feature Maps & ReLU):** Every time an inspector spots a clue, they highlight it on a summary notepad and ignore blank background space.\n"
            "• **Summary Index Cards (Pooling Layers):** A coordinator condenses large notepads into essential bullet points, keeping only the strongest clues so the team isn't overwhelmed.\n"
            "• **Lead Detective Conference (Fully Connected Layers):** The chief detective reviews all collected clue cards together and declares the final verdict: *\"This is a bicycle!\"*\n\n"
            "> 🔍 **Analogy Checkpoint:** In this detective team analogy, what real-world role corresponds to the Convolutional Filter scanning pixel patches?"
        ),
        "why_it_works": "The detective team analogy physically mirrors local receptive fields (inspectors), activation thresholding (highlighting), spatial pooling (summaries), and final dense classification (the lead detective).",
        "example": "A photo detective noticing whiskers, pointy ears, and a button nose before concluding the full image is a cat.",
        "common_mistake": "Thinking the lead detective looks at individual raw pixels rather than synthesized clue summaries.",
        "mini_quiz": "In the photo detective analogy, what corresponds to the pooling layer shrinking the feature map?",
        "reflection_prompt": "How would you adapt this detective analogy to explain how self-driving cars detect pedestrians?",
        "coach_recommendation": "Anchor your mental model on how local pattern clues combine into high-level object concepts.",
        "next_learning_step": "Padding, Stride, and Spatial Downsampling with Pooling",
        "visual_intuition": 'graph LR;\n  Photo["Photograph"] --> Inspectors["Filter Inspectors"] --> Clues["Pattern Clues"] --> Summary["Summary Notes"] --> Chief["Lead Detective"] --> Verdict["Final Identity"];'
    },
    "neural network": {
        "canonical_topic": "Neural Networks",
        "simple_explanation": (
            "Think of an **Artificial Neural Network** like a multi-station gourmet restaurant kitchen perfecting a signature recipe.\n\n"
            "• **Prep Station (Input Layer):** Raw ingredients arrive—chopped, measured, and organized like raw input features.\n"
            "• **Line Cook Stations (Hidden Layers & Weights):** Line cooks combine ingredients, adjusting spice and heat dials to balance recipe flavors.\n"
            "• **Head Chef Taste Test (Activation & Output):** The head chef tastes the dish against strict restaurant standards and serves it to the guest.\n"
            "• **Customer Review & Recipe Tweak (Loss & Backpropagation):** If a customer sends a dish back because it was too salty, the head chef traces the error backwards, instructing the line cook to reduce the salt ratio on the next order.\n\n"
            "> 🍲 **Analogy Checkpoint:** In the kitchen analogy, what real-world event corresponds to backpropagation updating parameter weights?"
        ),
        "why_it_works": "The kitchen analogy physically grounds forward propagation (cooking), loss quantification (customer feedback), and backpropagation (recipe adjustment).",
        "example": "Refining a pasta sauce recipe across 100 tastings until the acidity, salt, and sweetness reach absolute perfection.",
        "common_mistake": "Focusing solely on the food served rather than how customer feedback flows backward to adjust ingredient dials.",
        "mini_quiz": "In the restaurant kitchen analogy, what corresponds to the loss function?",
        "reflection_prompt": "Can you create another analogy for neural network training using sports coaching or musical rehearsals?",
        "coach_recommendation": "Notice how customer feedback directly mirrors error loss minimization.",
        "next_learning_step": "Convolutional Neural Networks and Spatial Features",
        "visual_intuition": 'graph LR;\n  Ingredients["Raw Ingredients"] --> LineCooks["Line Cooks Adjust Spices"] --> Chef["Head Chef Taste Test"] --> Feedback["Customer Feedback"] --> Refine["Recipe Refined"];'
    },
    "transformer": {
        "canonical_topic": "Transformers & Self-Attention",
        "simple_explanation": (
            "Think of the **Transformer** like a buzzing round-table conference of global experts working together on a complex document.\n\n"
            "• **Name Badges (Positional Encodings):** Every expert wears a badge showing where their paragraph sits in the document.\n"
            "• **Asking Questions (Query Vector $Q$):** Each expert asks: *\"Who has context on what I'm writing?\"*\n"
            "• **Expertise Tags (Key Vector $K$):** Other experts hold up tags declaring their specialized knowledge.\n"
            "• **Shared Knowledge (Value Vector $V$):** When an expert's question matches another's tag, they pass detailed notes simultaneously across the table, updating their understanding in parallel.\n\n"
            "> 💬 **Analogy Checkpoint:** In this conference analogy, why is it faster than passing a single notebook sequentially from person to person?"
        ),
        "why_it_works": "The round-table conference analogy illustrates parallel self-attention (note-passing), query-key compatibility matching, and collective contextual consensus.",
        "example": "A translator resolving what 'it' means in a sentence by instantly conferring with the expert holding the noun 'the street'.",
        "common_mistake": "Assuming experts must take turns speaking one by one instead of broadcasting and receiving notes simultaneously.",
        "mini_quiz": "In the conference analogy, what vector matches against the Query question?",
        "reflection_prompt": "Explain how multi-head attention is like having multiple teams of experts focusing on grammar, tone, and facts separately.",
        "coach_recommendation": "Visualize all experts passing notes concurrently rather than waiting in a queue.",
        "next_learning_step": "Scaled Dot-Product Attention Mechanics and Multi-Head Projections",
        "visual_intuition": 'graph LR;\n  Speakers["Conference Experts"] --> Matching["Query & Key Matching"] --> Notes["Shared Notes"] --> Consensus["Unified Understanding"];'
    },
    "binary search": {
        "canonical_topic": "Binary Search",
        "simple_explanation": (
            "Think of **Binary Search** like playing a high-low number guessing game for a secret number between 1 and 100.\n\n"
            "• **First Guess (Midpoint):** You don't guess 1, 2, 3 in order. You guess **50** right in the middle.\n"
            "• **The Clue (Comparison):** Your friend says *\"Higher!\"*\n"
            "• **Discarding the Half (Search Space Elimination):** In one second, you permanently throw away numbers 1 through 50. You now only have 51–100 to search.\n"
            "• **Next Guess (Repeat Halving):** You guess 75, then 88, pinpointing the exact secret number in at most 7 total guesses!\n\n"
            "> 🎯 **Analogy Checkpoint:** If the range was 1 to 1,000, why can you find any number in just 10 guesses?"
        ),
        "why_it_works": "The high-low guessing game intuitively demonstrates exponential reduction of the search space with every binary decision.",
        "example": "Flipping open a physical dictionary right to the middle letter 'M' to decide whether to search the front or back half.",
        "common_mistake": "Trying to play the high-low game when the pages or numbers are shuffled in random order.",
        "mini_quiz": "Why does the dictionary have to be sorted for the middle-flip strategy to work?",
        "reflection_prompt": "How would you adapt Binary Search to find the first occurrence of a duplicate value rather than any arbitrary index?",
        "coach_recommendation": "Remember that each single question cuts all remaining possibilities strictly in half.",
        "next_learning_step": "Binary Search on Monotonic Ranges and Lower Bound Search",
        "visual_intuition": 'graph LR;\n  Guess50["Guess Midpoint 50"] --> Higher["Friend Says Higher"] --> Discard["Discard 1 to 50"] --> Guess75["Guess 75"] --> Target["Secret Found"];'
    }
}

def synthesize_analogy_lesson(canonical_topic: str) -> Dict[str, str]:
    """
    Synthesizes a pure real-world analogy lesson (120-180 words) with explicit mapping and analogy diagram.
    """
    topic_lower = canonical_topic.lower()
    for key, lesson in ANALOGY_TOPIC_LESSONS.items():
        if key in topic_lower or any(alias in topic_lower for alias in [key, key.replace(' ', '')]):
            return dict(lesson)

    explanation = (
        f"Think of **{canonical_topic}** like a specialized airport luggage sorting terminal.\n\n"
        f"• **Check-In Counter (Input Intake):** Bags arrive with luggage tags indicating their weight and destination.\n"
        f"• **Automated Conveyor Scanners (Intermediate Processing):** High-speed barcode scanners read labels, routing bags through specialized sorter gates.\n"
        f"• **Quality Inspection (Decision Thresholds):** Security sensors verify tag accuracy before loading onto the correct flight.\n"
        f"• **System Re-routing (Feedback Adjustments):** If a bag is misdirected, the central routing computer recalibrates its switch timers for all subsequent bags.\n\n"
        f"> ✈️ **Analogy Checkpoint:** In this airport luggage terminal analogy, what real-world action represents processing and routing the inputs?"
    )

    return {
        "canonical_topic": canonical_topic,
        "simple_explanation": explanation,
        "why_it_works": f"The airport sorting terminal provides a physical mental model for how {canonical_topic} ingests, processes, and optimizes its operational flow.",
        "example": f"Luggage seamlessly reaching the correct departure gate through automated scanner coordination.",
        "common_mistake": f"Thinking baggage handlers inspect every bag manually rather than relying on automated conveyor routing.",
        "mini_quiz": f"In the sorting terminal analogy, how does the system recover when an item is misdirected?",
        "reflection_prompt": f"Can you map the components of {canonical_topic} to another real-world logistics or transportation system?",
        "coach_recommendation": f"Focus on how tag routing and feedback adjustment mirror the internal mechanism of {canonical_topic}.",
        "next_learning_step": get_prerequisite_next_step(canonical_topic),
        "visual_intuition": f'graph LR;\n  Arrival["Luggage Arrives"] --> Scanners["Barcode Scanners"] --> Gates["Sorter Gates"] --> Flight["Correct Flight"];'
    }


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-FIDELITY SIMPLIFY KNOWLEDGE REPOSITORY (80 - 120 WORDS)
# ─────────────────────────────────────────────────────────────────────────────
def synthesize_simplify_lesson(canonical_topic: str) -> Dict[str, str]:
    """
    Synthesizes a concise, jargon-free ELI5 explanation (80-120 words) with simplified diagram.
    """
    topic_lower = canonical_topic.lower()
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
    else:
        exp = (
            f"Think of {canonical_topic} like an assembly line where each station performs one simple, clear task. "
            f"Raw materials come in at the beginning, get cleaned and shaped in the middle, and exit as a finished product. "
            f"If something looks off, a supervisor tunes the machines so the next product comes out even better."
        )
        viz = f'graph LR;\n  Input["Raw Input"] --> Process["{canonical_topic}"] --> Result["Clean Result"];'

    return {
        "canonical_topic": canonical_topic,
        "simple_explanation": exp,
        "why_it_works": f"Simplifying {canonical_topic} captures the intuitive flow from raw input to verified result without unnecessary jargon.",
        "example": f"Building complex solutions from simple, verifiable stages.",
        "common_mistake": f"Thinking {canonical_topic} is mysterious magic rather than small, predictable adjustments.",
        "mini_quiz": f"In simple terms, what is the main goal of {canonical_topic}?",
        "reflection_prompt": f"How would you explain the core idea of {canonical_topic} to a 10-year-old?",
        "coach_recommendation": f"Keep the simple mental model in mind before diving into mathematical formulas.",
        "next_learning_step": get_prerequisite_next_step(canonical_topic),
        "visual_intuition": viz
    }


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-FIDELITY STEP-BY-STEP KNOWLEDGE REPOSITORY (450 - 600 WORDS)
# ─────────────────────────────────────────────────────────────────────────────
def synthesize_step_by_step_lesson(canonical_topic: str) -> Dict[str, str]:
    """
    Synthesizes a 5-step structured lesson with mini-examples and checkpoints (450-600 words).
    """
    topic_lower = canonical_topic.lower()
    if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
        exp = (
            f"### Step 1 — Input Matrix Ingestion\n"
            f"A CNN receives a raw image represented as a 3D numerical matrix of shape Height $\\times$ Width $\\times$ Channels (RGB values from 0 to 255).\n\n"
            f"*Mini-Example:* A $28 \\times 28$ grayscale handwritten digit is ingested as a matrix of 784 pixel intensity values normalized between 0.0 and 1.0.\n\n"
            f"> 🎯 **Step 1 Checkpoint:** Why do we normalize pixel intensities from [0, 255] to [0.0, 1.0] before feeding them into the network?\n\n"
            f"### Step 2 — Convolutional Filtering & Feature Extraction\n"
            f"Small learnable filters (e.g. $3 \\times 3$) slide across the image matrix, computing dot-products to generate 2D Feature Maps that highlight spatial patterns like lines, curves, and textures.\n\n"
            f"*Mini-Example:* A vertical edge filter responds strongly when sliding over the sharp boundary between a dark pupil and a bright iris.\n\n"
            f"> 🎯 **Step 2 Checkpoint:** What is the advantage of sliding small $3 \\times 3$ filters across an image instead of connecting each pixel directly to a hidden neuron?\n\n"
            "### Step 3 — Non-Linear Rectification (ReLU)\n"
            "Each value in the feature map passes through $\\text{ReLU}(z) = \\max(0, z)$. Negative activations are clamped to zero, creating sparse activations and enabling non-linear decision boundaries.\n\n"
            "*Mini-Example:* An activation value of $-0.85$ becomes $0.0$, while $+2.40$ passes through unchanged.\n\n"
            "> 🎯 **Step 3 Checkpoint:** Why would deep CNN layers fail to learn curved object boundaries if we removed the non-linear ReLU activation?\n\n"
            "### Step 4 — Spatial Max Pooling\n"
            "Max pooling slides a small window (e.g. $2 \\times 2$ with stride 2) over the feature map, keeping only the maximum value. This reduces spatial dimensions by 75% while maintaining translation invariance.\n\n"
            "*Mini-Example:* A $2 \\times 2$ block containing $[1.2, 0.4, 3.8, 2.1]$ is condensed to the single dominant value $3.8$.\n\n"
            "> 🎯 **Step 4 Checkpoint:** How does max pooling help a CNN recognize an object even if it is shifted or slightly rotated in the photograph?\n\n"
            "### Step 5 — Dense Classification & Softmax Output\n"
            "The pooled feature maps are flattened into a 1D vector and fed into fully connected dense layers. The final Softmax layer converts raw logits into normalized class probabilities summing to 1.0.\n\n"
            "*Mini-Example:* Output logits $[2.1, 0.3, 8.4]$ are converted by Softmax into $[0.2\\%, 0.1\\%, 99.7\\%]$ probability for class 'Dog'.\n\n"
            "> 🎯 **Step 5 Checkpoint (Feynman Challenge):** In your own words, trace how raw pixels transform from primitive lines in Step 2 to a final class decision in Step 5."
        )
        viz = 'graph TD;\n  S1["Step 1: Input Matrix"] --> S2["Step 2: Convolution Filters"];\n  S2 --> S3["Step 3: ReLU Activation"];\n  S3 --> S4["Step 4: Max Pooling"];\n  S4 --> S5["Step 5: Dense Softmax"];'
    else:
        exp = (
            f"### Step 1 — Input Ingestion & State Representation\n"
            f"At the start, {canonical_topic} ingests raw input data and structures it into a well-defined numerical state space where every feature represents a measurable attribute.\n\n"
            f"*Mini-Example:* Raw measurements are transformed into a normalized vector $X = [x_1, x_2, \\dots, x_n]$.\n\n"
            f"> 🎯 **Step 1 Checkpoint:** What would happen if input state features were unnormalized or missing?\n\n"
            f"### Step 2 — Parameterized Linear Transformation\n"
            f"Incoming signals are multiplied by adjustable weight parameters and combined with a bias term ($z = \\mathbf{{w}}^T \\mathbf{{x}} + b$) to amplify critical patterns.\n\n"
            f"*Mini-Example:* High weights amplify correlated signals while low weights suppress irrelevant background noise.\n\n"
            f"> 🎯 **Step 2 Checkpoint:** Why is the scalar bias term necessary alongside the multiplying weights?\n\n"
            f"### Step 3 — Non-Linear Activation & Feature Synthesis\n"
            f"The combined signal passes through a non-linear activation function, granting the network the capacity to learn non-linear patterns across multi-layer stacks.\n\n"
            f"*Mini-Example:* ReLU clamps negative values to zero while passing positive signal strengths through.\n\n"
            f"> 🎯 **Step 3 Checkpoint:** What happens to deep network capacity if all layer transformations are purely linear?\n\n"
            f"### Step 4 — Prediction & Loss Evaluation\n"
            f"The system produces a prediction $\\hat{{y}}$ and compares it against ground truth $y$ using a Loss Function to quantify error magnitude.\n\n"
            f"*Mini-Example:* Mean Squared Error computes the squared difference between the predicted value and the target label.\n\n"
            f"> 🎯 **Step 4 Checkpoint:** Why do we square the prediction error in regression loss functions?\n\n"
            f"### Step 5 — Backpropagation & Parameter Update\n"
            f"Using the calculus chain rule, the algorithm computes partial derivatives ($\\frac{{\\partial L}}{{\\partial w}}$) and updates parameters via gradient descent ($w \\leftarrow w - \\eta \\frac{{\\partial L}}{{\\partial w}}$).\n\n"
            f"*Mini-Example:* Parameters responsible for large errors receive proportional corrective adjustments.\n\n"
            f"> 🎯 **Step 5 Checkpoint (Feynman Challenge):** In your own words, why must error propagation flow in the reverse direction of the forward pass?"
        )
        viz = f'graph TD;\n  S1["Step 1: Input Ingestion"] --> S2["Step 2: Linear Weights"];\n  S2 --> S3["Step 3: Activation"];\n  S3 --> S4["Step 4: Loss Evaluation"];\n  S4 --> S5["Step 5: Backpropagation"];'

    return {
        "canonical_topic": canonical_topic,
        "simple_explanation": exp,
        "why_it_works": f"Breaking {canonical_topic} into 5 sequential steps isolates cognitive load and reinforces each intermediate state transition.",
        "example": f"Executing progressive state transitions from raw input ingestion to parameter optimization.",
        "common_mistake": f"Skipping intermediate validation checkpoints when analyzing the step sequence of {canonical_topic}.",
        "mini_quiz": f"Why does Step 3 require a non-linear activation function in {canonical_topic}?",
        "reflection_prompt": f"Can you summarize how all 5 steps of {canonical_topic} connect together into a unified learning cycle?",
        "coach_recommendation": f"Focus on how error signals calculated in Step 5 directly adjust the parameter weights introduced in Step 2.",
        "next_learning_step": get_prerequisite_next_step(canonical_topic),
        "visual_intuition": viz
    }


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL RESPONSE VALIDATOR & STATE ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class ResponseValidator:
    @staticmethod
    def validate_and_repair(data: Dict[str, Any], default_mastery: int = 0, fallback_topic: Optional[str] = None) -> TutorDocument:
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

        # Determine explicit pedagogical mode — STRICTLY from explicit lesson_mode field
        explicit_mode = str(repaired.get("lesson_mode", "")).upper().strip()
        if explicit_mode in ("STEP_BY_STEP", "SIMPLIFY", "ANALOGY", "STANDARD"):
            mode = LessonMode(explicit_mode)
        else:
            mode = LessonMode.STANDARD
        repaired["lesson_mode"] = mode

        # Extract clean canonical topic from context with fallback inheritance
        raw_topic = repaired.get("canonical_topic") or fallback_topic or explanation[:60]
        canonical_topic = extract_canonical_topic(raw_topic, fallback_topic=fallback_topic)
        repaired["canonical_topic"] = canonical_topic

        # Clean prompt echo from explanation opening
        explanation = clean_prompt_echo(explanation, is_explanation=True)

        # ─────────────────────────────────────────────────────────────────────
        # MODE ENFORCEMENT & HIGH-FIDELITY SYNTHESIS
        # ─────────────────────────────────────────────────────────────────────
        if mode == LessonMode.ANALOGY:
            # Enforce pure real-world analogy: must not have textbook step headers, must be analogy-driven
            has_textbook_headers = "### 1." in explanation or "The Artificial Neuron" in explanation or "Architectural Foundations" in explanation
            word_count = len(explanation.split())
            if has_textbook_headers or word_count > 260 or word_count < 60 or "analogy" not in explanation.lower() and "like a" not in explanation.lower() and "think of" not in explanation.lower():
                print(f"[VALIDATOR] Repairing ANALOGY response for '{canonical_topic}' with pure real-world analogy lesson...")
                synth = synthesize_analogy_lesson(canonical_topic)
                explanation = synth["simple_explanation"]
                why = synth["why_it_works"]
                example = synth["example"]
                repaired["common_mistake"] = synth["common_mistake"]
                repaired["mini_quiz"] = synth["mini_quiz"]
                repaired["reflection_prompt"] = synth["reflection_prompt"]
                repaired["coach_recommendation"] = synth["coach_recommendation"]
                repaired["next_learning_step"] = synth["next_learning_step"]
                repaired["visual_intuition"] = synth["visual_intuition"]

        elif mode == LessonMode.SIMPLIFY:
            # Enforce concise ELI5 explanation: 80 - 120 words
            has_textbook_headers = "### 1." in explanation or "Architectural Foundations" in explanation
            word_count = len(explanation.split())
            if has_textbook_headers or word_count > 160 or word_count < 40:
                print(f"[VALIDATOR] Repairing SIMPLIFY response for '{canonical_topic}' with concise ELI5 breakdown...")
                synth = synthesize_simplify_lesson(canonical_topic)
                explanation = synth["simple_explanation"]
                why = synth["why_it_works"]
                example = synth["example"]
                repaired["common_mistake"] = synth["common_mistake"]
                repaired["mini_quiz"] = synth["mini_quiz"]
                repaired["reflection_prompt"] = synth["reflection_prompt"]
                repaired["coach_recommendation"] = synth["coach_recommendation"]
                repaired["next_learning_step"] = synth["next_learning_step"]
                repaired["visual_intuition"] = synth["visual_intuition"]

        elif mode == LessonMode.STEP_BY_STEP:
            # Enforce 5 sequential steps with checkpoints
            has_5_steps = "Step 1" in explanation and "Step 2" in explanation and "Step 3" in explanation and "Step 4" in explanation and "Step 5" in explanation
            word_count = len(explanation.split())
            if not has_5_steps or word_count < 280:
                print(f"[VALIDATOR] Repairing STEP_BY_STEP response for '{canonical_topic}' with 5-stage progression...")
                synth = synthesize_step_by_step_lesson(canonical_topic)
                explanation = synth["simple_explanation"]
                why = synth["why_it_works"]
                example = synth["example"]
                repaired["common_mistake"] = synth["common_mistake"]
                repaired["mini_quiz"] = synth["mini_quiz"]
                repaired["reflection_prompt"] = synth["reflection_prompt"]
                repaired["coach_recommendation"] = synth["coach_recommendation"]
                repaired["next_learning_step"] = synth["next_learning_step"]
                repaired["visual_intuition"] = synth["visual_intuition"]

        else:
            # STANDARD MODE (350 - 500 words)
            word_count = len(explanation.split())
            if word_count < 220:
                print(f"[VALIDATOR] Standard lesson word count ({word_count} words) below threshold (<220). Enriching to full-depth master lesson...")
                synth = synthesize_standard_lesson(canonical_topic, explanation, why, example)
                explanation = synth["simple_explanation"]
                why = synth["why_it_works"]
                example = synth["example"]
                repaired["common_mistake"] = synth["common_mistake"]
                repaired["mini_quiz"] = synth["mini_quiz"]
                repaired["reflection_prompt"] = synth["reflection_prompt"]
                repaired["coach_recommendation"] = synth["coach_recommendation"]
                repaired["next_learning_step"] = synth["next_learning_step"]
                repaired["visual_intuition"] = synth["visual_intuition"]

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
            elif "cnn" in canonical_topic.lower() or "vision" in canonical_topic.lower():
                coach_tip = "Notice how convolutional filters detect local patterns that combine into global shapes."
            elif "binary search" in canonical_topic.lower():
                coach_tip = "Focus on why eliminating half the search space at every step yields logarithmic time."
            else:
                coach_tip = f"Focus on how {canonical_topic} structures data transformations and optimizes its decision boundaries."
        repaired["coach_recommendation"] = coach_tip

        # Next learning step (prerequisite-aware)
        next_step = repaired.get("next_learning_step", "").strip()
        if not next_step or any(p in next_step.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            next_step = get_prerequisite_next_step(canonical_topic)
        else:
            next_step = clean_prompt_echo(next_step)
        repaired["next_learning_step"] = next_step

        # ─────────────────────────────────────────────────────────────────────
        # MODE-SPECIFIC DIAGRAM RESOLUTION ENGINE
        # ─────────────────────────────────────────────────────────────────────
        viz = repaired.get("visual_intuition", "").strip()
        topic_and_text = f"{canonical_topic} {explanation} {why} {example}".lower()
        topic_lower = canonical_topic.lower()

        # Find matching domain diagram in registry
        matched_viz = None
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
            if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
                viz = 'graph LR;\n  Image["Input Image"] --> Simple["Simple Edges"] --> Complex["Complex Shapes"] --> Object["Object Decision"];'
            elif any(k in topic_lower for k in ["neural", "perceptron", "deep learning", "mlp", "ann"]):
                viz = 'graph LR;\n  Input["Input Data"] --> NN["Neural Network Layers"] --> Learn["Learn Patterns"] --> Pred["Prediction"];'
            elif any(k in topic_lower for k in ["backprop", "gradient", "chain rule"]):
                viz = 'graph LR;\n  Loss["Calculate Loss"] --> Grad["Compute Gradients"] --> Update["Update Weights"];'
            elif any(k in topic_lower for k in ["transformer", "attention", "bert", "gpt"]):
                viz = 'graph LR;\n  Token["Input Tokens"] --> Attn["Self-Attention"] --> Out["Contextual Output"];'
            elif any(k in topic_lower for k in ["binary search", "search"]):
                viz = 'graph LR;\n  Array["Sorted Array"] --> Mid["Check Midpoint"] --> Discard["Discard Half"] --> Target["Target Found"];'
            elif any(k in topic_lower for k in ["sort", "merge sort", "quicksort"]):
                viz = 'graph LR;\n  Unsorted["Unsorted Data"] --> Split["Divide"] --> Sorted["Sorted Output"];'
            elif matched_viz:
                viz = matched_viz
            else:
                viz = f'graph LR;\n  Input["{canonical_topic} Input"] --> Process["{canonical_topic} Core Logic"] --> Output["Result"];'

        elif mode == LessonMode.ANALOGY:
            text_lower = f"{canonical_topic} {explanation}".lower()
            if any(k in text_lower for k in ["cnn", "convolutional", "computer vision", "detective", "inspector", "photo", "magnifying"]):
                viz = 'graph LR;\n  Photo["Photograph"] --> Inspectors["Filter Inspectors"] --> Clues["Pattern Clues"] --> Summary["Summary Notes"] --> Chief["Lead Detective"] --> Verdict["Final Identity"];'
            elif any(k in text_lower for k in ["neural", "perceptron", "kitchen", "chef", "cooking", "recipe"]):
                viz = 'graph LR;\n  Ingredients["Raw Ingredients"] --> LineCooks["Line Cooks Adjust Spices"] --> Chef["Head Chef Taste Test"] --> Feedback["Customer Feedback"] --> Refine["Recipe Refined"];'
            elif any(k in text_lower for k in ["transformer", "attention", "conference", "expert"]):
                viz = 'graph LR;\n  Speakers["Conference Experts"] --> Matching["Query & Key Matching"] --> Notes["Shared Notes"] --> Consensus["Unified Understanding"];'
            elif any(k in text_lower for k in ["binary search", "game", "guess", "higher"]):
                viz = 'graph LR;\n  Guess50["Guess Midpoint 50"] --> Higher["Friend Says Higher"] --> Discard["Discard 1 to 50"] --> Guess75["Guess 75"] --> Target["Secret Found"];'
            elif any(k in text_lower for k in ["airport", "luggage", "terminal"]):
                viz = 'graph LR;\n  Arrival["Luggage Arrives"] --> Scanners["Barcode Scanners"] --> Gates["Sorter Gates"] --> Flight["Correct Flight"];'
            else:
                t = canonical_topic
                viz = f'graph LR;\n  RealWorld["Familiar Concept"] --> Mapping["{t} Parallel"] --> Insight["{t} Understood"];'

        elif mode == LessonMode.STEP_BY_STEP:
            if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
                viz = 'graph TD;\n  S1["Step 1: Input Matrix"] --> S2["Step 2: Convolution Filters"];\n  S2 --> S3["Step 3: ReLU Activation"];\n  S3 --> S4["Step 4: Max Pooling"];\n  S4 --> S5["Step 5: Dense Softmax"];'
            elif any(k in topic_lower for k in ["neural", "perceptron", "deep learning", "mlp"]):
                viz = 'graph TD;\n  S1["Step 1: Understand Neurons & Weights"] --> S2["Step 2: Forward Pass Predictions"];\n  S2 --> S3["Step 3: Measure Loss Error"];\n  S3 --> S4["Step 4: Backpropagate Gradients"];\n  S4 --> S5["Step 5: Optimizer Weight Update"];'
            elif any(k in topic_lower for k in ["backprop", "gradient", "chain rule"]):
                viz = 'graph TD;\n  S1["Step 1: Forward Pass Output"] --> S2["Step 2: Output Layer Loss"];\n  S2 --> S3["Step 3: Chain Rule Gradients"];\n  S3 --> S4["Step 4: Accumulate Derivatives"];\n  S4 --> S5["Step 5: Optimizer Parameter Update"];'
            elif any(k in topic_lower for k in ["transformer", "attention", "bert", "gpt"]):
                viz = 'graph TD;\n  S1["Step 1: Tokenize & Embed"] --> S2["Step 2: Positional Encoding"];\n  S2 --> S3["Step 3: Compute Q, K, V"];\n  S3 --> S4["Step 4: Multi-Head Attention"];\n  S4 --> S5["Step 5: Feed-Forward & Norm"];'
            elif any(k in topic_lower for k in ["binary search"]):
                viz = 'graph TD;\n  S1["Step 1: Set Low & High Pointers"] --> S2["Step 2: Calculate Midpoint"];\n  S2 --> S3["Step 3: Compare Mid with Target"];\n  S3 --> S4["Step 4: Eliminate Half Array"];\n  S4 --> S5["Step 5: Return Found Index"];'
            elif any(k in topic_lower for k in ["sort", "merge sort", "quicksort"]):
                viz = 'graph TD;\n  S1["Step 1: Divide Array in Halves"] --> S2["Step 2: Recursively Sort Left"];\n  S2 --> S3["Step 3: Recursively Sort Right"];\n  S3 --> S4["Step 4: Merge Sorted Halves"];\n  S4 --> S5["Step 5: Return Sorted Array"];'
            elif matched_viz:
                viz = matched_viz
            else:
                t = canonical_topic
                viz = f'graph TD;\n  S1["Step 1: {t} Foundations"] --> S2["Step 2: Core Mechanism"];\n  S2 --> S3["Step 3: Practical Example"];\n  S3 --> S4["Step 4: Edge Cases"];\n  S4 --> S5["Step 5: Master In Practice"];'

        else:
            # Standard Mode
            if matched_viz:
                viz = matched_viz
            elif not viz or ("graph " not in viz and "flowchart " not in viz) or "Fallback" in viz or "Input Transformation" in viz:
                viz = f'graph TD;\n  In["Input Data"] --> Process["{canonical_topic} Processing"];\n  Process --> Out["Verified Output"];'

        repaired["visual_intuition"] = viz
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])
        if "evaluation" in repaired and isinstance(repaired["evaluation"], dict):
            repaired["evaluation"] = repaired["evaluation"]

        total_words = len(explanation.split()) + len(why.split()) + len(example.split())
        print(f"[VALIDATOR] Response validated ({mode.value}) with {total_words} total instructional words.")
        return DocumentBuilder.create_document(repaired)
