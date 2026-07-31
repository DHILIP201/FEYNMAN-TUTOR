"""
Feynman Cognitive Engine — Response Validator & Repair Module
"""

from typing import Dict, Any
from .schemas import TutorDocument
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
        "aliases": ["backpropagation", "backprop", "chain rule", "gradient computation"],
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
        "aliases": ["neural", "perceptron", "deep learning", "weights", "bias", "layer"],
        "mermaid": "graph TD;\n  Img[Input Features] --> W[Weighted Sum & Bias];\n  W --> Act[Activation Function];\n  Act --> Out[Prediction Output];"
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

        # Semantic Topic Visual Engine Lookup
        if not viz or ("graph " not in viz and "flowchart " not in viz) or "Input Layer" in viz or "Hidden Processing Layers" in viz or "Fallback" in viz:
            matched_viz = None
            for entry in TOPIC_VISUALS_REGISTRY:
                if any(alias in exp_lower for alias in entry["aliases"]):
                    matched_viz = entry["mermaid"]
                    break
            if not matched_viz:
                matched_viz = f"graph TD;\n  Start[Input Context] --> Process[Socratic Breakdown & Mechanics];\n  Process --> Outcome[Mastered Concept];"
            viz = matched_viz

        repaired["visual_intuition"] = viz

        repaired.setdefault("next_learning_step", "Explore adjacent architectural topics")
        repaired.setdefault("estimated_study_time", 4)
        repaired.setdefault("mastery_score", default_mastery)
        repaired.setdefault("sources", [])

        print(f"[VALIDATOR] Response validated and structured with {len(explanation.split())} words.")
        return DocumentBuilder.create_document(repaired)
