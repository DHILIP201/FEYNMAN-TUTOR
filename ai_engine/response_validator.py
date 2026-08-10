import re
from typing import Dict, Any, Optional
from .schemas import TutorDocument, LessonMode
from .document_builder import DocumentBuilder

TOPIC_VISUALS_REGISTRY = [
    {
        "topic": "transformer",
        "aliases": ["transformer", "bert", "gpt", "attention", "llm", "encoder", "decoder"],
        "mermaid": "graph TD;\n  In[Input Embeddings] --> Attn[Multi-Head Self Attention];\n  Attn --> AddNorm1[Add & LayerNorm];\n  AddNorm1 --> FFN[Feed Forward Network];\n  FFN --> AddNorm2[Add & LayerNorm];\n  AddNorm2 --> Out[Logits / Next Token];"
    },
    {
        "topic": "cnn",
        "aliases": ["cnn", "convolutional", "computer vision", "pooling", "feature map"],
        "mermaid": "graph TD;\n  Img[Input Image Matrix] --> Conv[Convolution Feature Map];\n  Conv --> Pool[Max Pooling Reduction];\n  Pool --> FC[Fully Connected Dense Layer];\n  FC --> Class[Class Probabilities];"
    },
    {
        "topic": "backpropagation",
        "aliases": ["backpropagation", "backprop", "chain rule", "gradient computation", "error signal"],
        "mermaid": "graph TD;\n  Fwd[Forward Pass Prediction] --> Loss[Calculate Loss Error];\n  Loss --> Grad[Compute Gradients via Chain Rule];\n  Grad --> Upd[Update Weights & Biases];"
    },
    {
        "topic": "gradient descent",
        "aliases": ["gradient descent", "optimizer", "adam", "sgd", "minima"],
        "mermaid": "graph TD;\n  Init[Random Weight Init] --> Eval[Compute Gradient Slope];\n  Eval --> Step[Step Opposite Gradient];\n  Step --> Check{Minima Reached?};\n  Check -->|No| Eval;\n  Check -->|Yes| Converged[Optimal Weights];"
    },
    {
        "topic": "activation",
        "aliases": ["activation", "relu", "sigmoid", "tanh", "softmax", "leaky relu"],
        "mermaid": "graph TD;\n  Sum[Weighted Sum z = wx + b] --> Act{Activation Function};\n  Act -->|ReLU| NonLinear[max 0, z];\n  Act -->|Sigmoid| Probability[1 / 1 + e^-z];\n  NonLinear --> Out[Neuron Output];\n  Probability --> Out;"
    },
    {
        "topic": "neural network",
        "aliases": ["neural", "perceptron", "deep learning", "weights", "bias", "layer", "neuron"],
        "mermaid": "graph TD;\n  In[Input Features x] --> W[Weights & Biases wx + b];\n  W --> Act[Activation Function];\n  Act --> Out[Prediction Output y];"
    },
    {
        "topic": "binary search",
        "aliases": ["binary search", "logarithmic search", "sorted array search"],
        "mermaid": "graph TD;\n  Arr[Sorted Array] --> Mid[Find Mid Element];\n  Mid --> Comp{Is Mid == Target?};\n  Comp -->|Smaller| Left[Search Left Half];\n  Comp -->|Larger| Right[Search Right Half];\n  Comp -->|Match| Found[Return Index];"
    },
    {
        "topic": "merge sort",
        "aliases": ["merge sort", "quick sort", "sorting algorithm", "divide and conquer"],
        "mermaid": "graph TD;\n  Unsorted[Unsorted Array] --> Split[Divide Array in Halves];\n  Split --> Recurse[Sort Sub-Arrays];\n  Recurse --> Merge[Merge Sorted Sub-Arrays];\n  Merge --> Sorted[Sorted Output Array];"
    },
    {
        "topic": "linked list",
        "aliases": ["linked list", "pointer", "node", "doubly linked"],
        "mermaid": "graph TD;\n  Head[Head Node: Data|Next] --> N1[Node 1: Data|Next];\n  N1 --> N2[Node 2: Data|Next];\n  N2 --> Null[Tail -> NULL];"
    },
    {
        "topic": "hash table",
        "aliases": ["hash table", "hash map", "dictionary", "key value", "collision"],
        "mermaid": "graph TD;\n  Key[Input Key String] --> Hash[Hash Function];\n  Hash --> Index[Bucket Index Calculation];\n  Index --> Bucket[Bucket Storage / Chaining];"
    },
    {
        "topic": "heap",
        "aliases": ["heap", "priority queue", "max heap", "min heap"],
        "mermaid": "graph TD;\n  Root[Root Max/Min Element] --> L[Left Child <= Parent];\n  Root --> R[Right Child <= Parent];\n  L --> L1[Heap Property Preserved];"
    },
    {
        "topic": "graph",
        "aliases": ["graph", "bfs", "dfs", "dijkstra", "traversal"],
        "mermaid": "graph TD;\n  A[Node A] --> B[Node B];\n  A --> C[Node C];\n  B --> D[Node D];\n  C --> D;\n  D --> E[Traversed Goal Node];"
    },
    {
        "topic": "dynamic programming",
        "aliases": ["dynamic programming", "dp", "memoization", "tabulation", "subproblem"],
        "mermaid": "graph TD;\n  Problem[Original Subproblem] --> Check{In Memoization Table?};\n  Check -->|Yes| Cached[Return Stored Result];\n  Check -->|No| Compute[Solve & Store in DP Table];"
    },
    {
        "topic": "recursion",
        "aliases": ["recursion", "recursive", "call stack", "base case"],
        "mermaid": "graph TD;\n  Call[Function Call] --> Base{Base Case Met?};\n  Base -->|No| Recurse[Recursive Call];\n  Base -->|Yes| Return[Return Base Value];"
    },
    {
        "topic": "tcp",
        "aliases": ["tcp", "3-way handshake", "syn ack", "socket", "packet"],
        "mermaid": "graph TD;\n  Client[Client] -->|1. SYN| Server[Server];\n  Server -->|2. SYN-ACK| Client;\n  Client -->|3. ACK| Server;"
    },
    {
        "topic": "dns",
        "aliases": ["dns", "domain name", "tld", "ip address lookup"],
        "mermaid": "graph TD;\n  Browser[Client Browser] --> Resolv[DNS Resolver];\n  Resolv --> Root[Root Name Server];\n  Root --> TLD[TLD Server .com];\n  TLD --> Auth[Authoritative DNS Server];\n  Auth --> IP[Return IP Address];"
    },
    {
        "topic": "http",
        "aliases": ["http", "https", "rest api", "endpoint", "gateway"],
        "mermaid": "graph TD;\n  Client[Client Browser] -->|HTTP GET / API Request| Gateway[API Gateway / Proxy];\n  Gateway --> Service[Microservice Worker];\n  Service --> DB[(Database Query)];\n  Service -->|HTTP 200 OK JSON| Client;"
    },
    {
        "topic": "paging",
        "aliases": ["paging", "virtual memory", "page table", "page fault", "segmentation"],
        "mermaid": "graph TD;\n  Virtual[Virtual Address] --> PageTable[Page Table Lookup];\n  PageTable --> Check{Page in RAM?};\n  Check -->|Yes| Frame[Physical Memory Frame];\n  Check -->|No| Fault[Page Fault -> Disk Swap];"
    },
    {
        "topic": "deadlock",
        "aliases": ["deadlock", "mutex", "concurrency", "race condition", "semaphore"],
        "mermaid": "graph TD;\n  P1[Process 1] -->|Holds| R1[Resource 1];\n  R1 -->|Requested by| P2[Process 2];\n  P2 -->|Holds| R2[Resource 2];\n  R2 -->|Requested by| P1;"
    },
    {
        "topic": "sql",
        "aliases": ["sql", "join", "inner join", "relational database", "query"],
        "mermaid": "graph TD;\n  T1[Table A] --> Join[JOIN Key Match];\n  T2[Table B] --> Join;\n  Join --> Res[Combined Result Set];"
    },
    {
        "topic": "acid",
        "aliases": ["acid", "transaction", "atomicity", "durability", "isolation"],
        "mermaid": "graph TD;\n  Tx[Database Transaction] --> Atom[Atomicity: All or Nothing];\n  Tx --> Cons[Consistency: Valid Constraints];\n  Tx --> Iso[Isolation: Concurrent Locks];\n  Tx --> Dur[Durability: Write-Ahead Log WAL];"
    }
]

def clean_prompt_echo(text: str) -> str:
    """Removes user prompt echoes from generated content strings."""
    if not text:
        return ""
    cleaned = re.sub(
        r'^(Teach me step by step until I understand|Teach me\s+(.+?)\s+step by step|Explain this concept even simpler|Explain this simpler|Explain\s+(.+?)\s+in simple terms|Give a real[- ]world analogy for|Give a real[- ]world analogy|Tell me about advanced applications of|Tell me about|Understanding how the|Understanding|Explain what is|Explain|What is)\s+',
        '',
        text.strip(),
        flags=re.IGNORECASE
    ).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned or text.strip()

def extract_canonical_topic(text: str) -> str:
    """Isolates the clean canonical subject topic from raw user prompts."""
    if not text:
        return "this concept"
    cleaned = re.sub(
        r'^(Teach me step by step until I understand|Teach me\s+|Explain this concept even simpler|Explain this simpler|Explain\s+|Give a real[- ]world analogy for|Give a real[- ]world analogy|Tell me about advanced applications of|Tell me about|Understanding how the|Understanding|Explain what is|What is|How does\s+)\s*',
        '',
        text.strip(),
        flags=re.IGNORECASE
    ).strip()
    # Strip trailing "step by step" or question marks
    cleaned = re.sub(r'\s+step by step[\?!.]*$', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[\?\.!\s]+$', '', cleaned).strip()
    
    if not cleaned or len(cleaned) < 2:
        cleaned = "Core Concept"
    return cleaned.title() if len(cleaned.split()) <= 4 else (cleaned[0].upper() + cleaned[1:])

class ResponseValidator:
    @staticmethod
    def validate_and_repair(data: Dict[str, Any], default_mastery: int = 0) -> TutorDocument:
        """
        Validates contract response dictionary and enforces mode-specific diagrams and clean canonical topics.
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
        elif "analogy" in cognitive_trace_lower or "analogy" in str(repaired.get("lesson_mode", "")).lower():
            mode = LessonMode.ANALOGY
        else:
            mode = LessonMode.STANDARD
        repaired["lesson_mode"] = mode

        # Clean prompt echo from explanation opening
        explanation = clean_prompt_echo(explanation)
        repaired["simple_explanation"] = explanation

        # Extract clean canonical topic from context
        full_text = f"{explanation} {why} {example}"
        canonical_topic = extract_canonical_topic(repaired.get("canonical_topic") or explanation[:60])

        repaired.setdefault("why_it_works", clean_prompt_echo(why) or "Underlying conceptual mechanics.")
        repaired.setdefault("example", clean_prompt_echo(example) or "Illustrative real-world example.")
        repaired.setdefault("common_mistake", "Confusing foundational parameters with output predictions.")

        # Sanitize Active Recall and Quiz to always reference clean topic
        mini_quiz = repaired.get("mini_quiz", "").strip()
        if not mini_quiz or any(p in mini_quiz.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            mini_quiz = f"What is the primary objective when working with {canonical_topic}?"
        repaired["mini_quiz"] = clean_prompt_echo(mini_quiz)

        reflection = repaired.get("reflection_prompt", "").strip()
        if not reflection or any(p in reflection.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            reflection = f"How would you explain the core mechanism of {canonical_topic} to a peer?"
        repaired["reflection_prompt"] = clean_prompt_echo(reflection)

        # Topic-Aware Coaching Tip (conditional)
        coach_tip = repaired.get("coach_recommendation", "").strip()
        if not coach_tip or any(p in coach_tip.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            if "backprop" in full_text.lower():
                coach_tip = "Trace the error signal backward layer by layer to see how each weight adjusts."
            elif "neural" in full_text.lower() or "perceptron" in full_text.lower():
                coach_tip = "Think about how each layer transforms raw input features into higher-level representations."
            elif "binary search" in full_text.lower():
                coach_tip = "Focus on why eliminating half the search space at every step yields logarithmic time."
            else:
                coach_tip = f"Focus on the underlying flow of data and mechanics across {canonical_topic}."
        repaired["coach_recommendation"] = coach_tip

        # Next learning step
        next_step = repaired.get("next_learning_step", "").strip()
        if not next_step or any(p in next_step.lower() for p in ["teach me step by step", "explain this concept even simpler", "give a real world analogy"]):
            next_step = f"Advanced applications of {canonical_topic}"
        else:
            next_step = clean_prompt_echo(next_step)
        repaired["next_learning_step"] = next_step

        # Mode-Specific Diagram Generation Engine
        viz = repaired.get("visual_intuition", "").strip()
        exp_lower = full_text.lower()

        # Find matching domain diagram in registry
        matched_viz = None
        for entry in TOPIC_VISUALS_REGISTRY:
            if any(alias in exp_lower for alias in entry["aliases"]):
                matched_viz = entry["mermaid"]
                break

        if mode == LessonMode.SIMPLIFY:
            # Streamlined 3-node conceptual pipeline for Simplify
            if "neural" in exp_lower or "ai" in exp_lower or "model" in exp_lower:
                viz = "graph LR;\n  Data[Raw Input] --> Pattern[Pattern Detection] --> Decision[Clear Decision];"
            elif "search" in exp_lower or "sort" in exp_lower:
                viz = "graph LR;\n  Items[Unsorted Items] --> Rule[Simple Rule] --> Result[Found Result];"
            elif matched_viz:
                viz = matched_viz
            else:
                viz = "graph LR;\n  Input[Raw Information] --> Rules[Simple Filter] --> Output[Clear Result];"
        elif mode == LessonMode.ANALOGY:
            # Real-world analogy process flow
            if "kitchen" in exp_lower or "chef" in exp_lower or "restaurant" in exp_lower:
                viz = "graph LR;\n  Order[Customer Order] --> Kitchen[Chef Prepares] --> Meal[Served Dish];"
            elif "team" in exp_lower or "factory" in exp_lower or "assembly" in exp_lower:
                viz = "graph LR;\n  Worker1[Station 1: Prep] --> Worker2[Station 2: Assembly] --> Product[Final Product];"
            elif matched_viz:
                viz = matched_viz
            else:
                viz = "graph LR;\n  Start[Everyday Object] --> Action[Relatable Process] --> End[Intuitive Result];"
        elif mode == LessonMode.STEP_BY_STEP:
            # Sequential Step-by-Step learning progression flowchart
            if "neural" in exp_lower:
                viz = "graph TD;\n  S1[Step 1: Input Features] --> S2[Step 2: Layer Processing];\n  S2 --> S3[Step 3: Activation & Output];\n  S3 --> S4[Step 4: Error & Learning];\n  S4 --> S5[Step 5: Full Neural System];"
            else:
                viz = f"graph TD;\n  S1[Step 1: Foundations] --> S2[Step 2: Mechanics];\n  S2 --> S3[Step 3: Application];\n  S3 --> S4[Step 4: Mastery of {canonical_topic}];"
        else:
            # Standard Mode: Topic-matched or AI-generated valid flowchart
            if matched_viz:
                viz = matched_viz
            elif not viz or ("graph " not in viz and "flowchart " not in viz) or "Fallback" in viz or "Input Transformation" in viz:
                # If no topic-specific diagram is safely generated, hide it cleanly rather than showing generic placeholder
                viz = ""

        repaired["visual_intuition"] = viz
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])
        if "evaluation" in repaired and isinstance(repaired["evaluation"], dict):
            repaired["evaluation"] = repaired["evaluation"]

        print(f"[VALIDATOR] Response validated ({mode.value}) with {len(explanation.split())} words.")
        return DocumentBuilder.create_document(repaired)
