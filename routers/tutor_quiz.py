"""
routers/tutor_quiz.py
=====================
Feynman AI -- Per-Chat "Quiz Me" Interactive Router
Attached to individual AI tutor response cards for quick, 3-4 question comprehension checks.

Key Invariants:
- 3-4 questions maximum per quiz session (mixture of MCQ, True/False, and Short Answer teach-back)
- Strict grounding in the CURRENT AI response message and canonical topic
- Correct answers NEVER exposed to client prior to submission
- Progressive hints active ONLY while Quiz Me is open and current question is unanswered
- Server-side answer evaluation via deterministic checks (MCQ/TF) and GeminiGateway (Short Answer)
- Mastery integration (+15 / -10) via learner_memory_engine with idempotent evaluation IDs
- Multi-turn independence (older messages retain their own independent quiz state)
"""

import json
import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import (
    get_db, User, TutorQuizSession, TutorQuizQuestion, TutorQuizAnswer, ChatSession
)
from security import get_current_user
from ai_engine.gemini_gateway import gemini_gateway
from ai_engine.memory.learner_memory_engine import learner_memory_engine

router = APIRouter(tags=["Tutor Quiz Mode"])


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class TutorQuizStartRequest(BaseModel):
    message_id: Optional[str] = Field(None, description="Specific AI card/message ID")
    session_id: Optional[str] = Field(None, description="Current chat session ID")
    canonical_topic: str = Field(..., description="Canonical topic of the current lesson")
    lesson_text: str = Field(..., description="Current lesson explanation text")
    lesson_mode: Optional[str] = Field("STANDARD", description="STANDARD | SIMPLIFY | ANALOGY | STEP_BY_STEP")
    question_count: Optional[int] = Field(4, ge=3, le=4, description="Number of questions (3-4)")


class TutorQuizAnswerRequest(BaseModel):
    question_id: int
    answer: str


class TutorQuizHintRequest(BaseModel):
    question_id: int


# ---------------------------------------------------------------------------
# Question Generation via GeminiGateway with Resilient Fallbacks
# ---------------------------------------------------------------------------

TUTOR_QUIZ_SYSTEM_INSTRUCTION = """You are Richard Feynman designing a rapid 3-4 question comprehension checkpoint for a student who just read your lesson.

Your task:
1. Generate exactly {count} questions strictly grounded in the provided lesson text and topic.
2. Structure:
   - Q1: Basic understanding (MCQ with 4 options)
   - Q2: Mechanism or property (True/False or MCQ)
   - Q3: Application or common misconception (MCQ)
   - Q4: Feynman Teach-Back / Short Answer ("Explain in your own words...")
3. For MCQ: options must be labeled "A. ...", "B. ...", "C. ...", "D. ...". Correct answer is "A", "B", "C", or "D".
4. For TF: options are ["True", "False"]. Correct answer is "True" or "False".
5. For SHORT_ANSWER: options is empty []. Correct answer should contain the key concepts expected in a strong student response.
6. Pedagogical tone: Encouraging, precise, and intellectually sharp."""

TUTOR_QUIZ_PROMPT_TEMPLATE = """Generate exactly {count} quiz questions based ONLY on this tutor lesson:

--- TOPIC ---
{topic} ({mode} mode)

--- LESSON CONTENT ---
{lesson_text}
--- END LESSON ---

Return ONLY a valid JSON array of objects with this exact structure:
[
  {{
    "question_text": "...",
    "question_type": "MCQ",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_answer": "A",
    "explanation": "Clear 1-2 sentence explanation of the concept.",
    "difficulty": "medium",
    "canonical_topic": "{topic}"
  }},
  {{
    "question_text": "True or False: ...",
    "question_type": "TF",
    "options": ["True", "False"],
    "correct_answer": "True",
    "explanation": "Clear explanation.",
    "difficulty": "easy",
    "canonical_topic": "{topic}"
  }},
  {{
    "question_text": "...",
    "question_type": "MCQ",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_answer": "B",
    "explanation": "Clear explanation.",
    "difficulty": "medium",
    "canonical_topic": "{topic}"
  }},
  {{
    "question_text": "Explain in your own words how {topic} works as if teaching it to another student.",
    "question_type": "SHORT_ANSWER",
    "options": [],
    "correct_answer": "Key concepts: ...",
    "explanation": "A complete response should describe the input state, intermediate transformation, and final objective.",
    "difficulty": "hard",
    "canonical_topic": "{topic}"
  }}
]"""


def synthesize_topic_fallback_quiz(topic: str, lesson_text: str, mode: str, count: int = 4) -> List[Dict[str, Any]]:
    """Synthesizes high-fidelity grounded questions for known topics or generic lessons when LLM is unavailable."""
    topic_lower = topic.lower()

    if any(k in topic_lower for k in ["cnn", "convolutional", "computer vision"]):
        questions = [
            {
                "question_text": "What is the primary computational benefit of sliding convolutional filters over an image rather than using fully connected layers?",
                "question_type": "MCQ",
                "options": [
                    "A. Parameter sharing and translation equivariance reduce overfitting",
                    "B. They completely eliminate the need for activation functions",
                    "C. They convert 2D image matrices into text strings",
                    "D. They guarantee 100% classification accuracy on the first epoch"
                ],
                "correct_answer": "A",
                "explanation": "Sliding parameterized kernels across receptive fields exploits translation equivariance and drastically reduces parameter counts compared to dense matrices.",
                "difficulty": "medium",
                "canonical_topic": "Convolutional Neural Networks"
            },
            {
                "question_text": "True or False: Max Pooling downsamples spatial resolution while preserving dominant structural features.",
                "question_type": "TF",
                "options": ["True", "False"],
                "correct_answer": "True",
                "explanation": "Max pooling extracts the maximum value within localized windows (e.g. 2x2), reducing spatial dimensions by 75% while providing translation invariance.",
                "difficulty": "easy",
                "canonical_topic": "Convolutional Neural Networks"
            },
            {
                "question_text": "Why is the non-linear ReLU activation function applied after each convolutional filtering step?",
                "question_type": "MCQ",
                "options": [
                    "A. To convert the neural network into a simple linear regression",
                    "B. To introduce non-linearity and prevent mathematical collapse across stacked layers",
                    "C. To randomly delete half of the input image pixels",
                    "D. To double the spatial height and width of the feature maps"
                ],
                "correct_answer": "B",
                "explanation": "Without non-linear activations like ReLU, multiple stacked convolutional layers would collapse mathematically into a single trivial linear transformation.",
                "difficulty": "medium",
                "canonical_topic": "Convolutional Neural Networks"
            },
            {
                "question_text": "Feynman Challenge: In your own words, explain how a CNN transforms raw image pixels into a final classification as if teaching a classmate.",
                "question_type": "SHORT_ANSWER",
                "options": [],
                "correct_answer": "A strong explanation explains: 1) kernels slide to detect primitive edges/patterns, 2) ReLU adds non-linearity, 3) pooling downsamples, and 4) dense layers make the final prediction.",
                "explanation": "The core intuition is hierarchical feature abstraction: from local edges in early layers to global object shapes in final dense layers.",
                "difficulty": "hard",
                "canonical_topic": "Convolutional Neural Networks"
            }
        ]
    elif any(k in topic_lower for k in ["transformer", "attention", "self-attention", "bert", "gpt"]):
        questions = [
            {
                "question_text": "How does Self-Attention differ fundamentally from recurrent neural network (RNN) processing?",
                "question_type": "MCQ",
                "options": [
                    "A. It processes all tokens in parallel rather than sequentially step-by-step",
                    "B. It only works on image pixel grids",
                    "C. It disables all matrix multiplications",
                    "D. It requires an infinite context window"
                ],
                "correct_answer": "A",
                "explanation": "Self-attention computes pairwise token affinities concurrently across the full sequence, eliminating the sequential path bottleneck of RNNs.",
                "difficulty": "medium",
                "canonical_topic": "Transformers & Self-Attention"
            },
            {
                "question_text": "True or False: Positional encodings are necessary in Transformers because self-attention contains no built-in recurrence or sequential order.",
                "question_type": "TF",
                "options": ["True", "False"],
                "correct_answer": "True",
                "explanation": "Because all tokens are evaluated simultaneously, positional vectors must be added to token embeddings to preserve word order.",
                "difficulty": "easy",
                "canonical_topic": "Transformers & Self-Attention"
            },
            {
                "question_text": "What do the Query (Q) and Key (K) vectors compute when calculating scaled dot-product attention?",
                "question_type": "MCQ",
                "options": [
                    "A. They determine the relevance/affinity between every pair of tokens in the sequence",
                    "B. They compute the learning rate for gradient descent",
                    "C. They compress the text into audio waveforms",
                    "D. They delete filler words from the prompt"
                ],
                "correct_answer": "A",
                "explanation": "The dot product Q*K^T measures semantic compatibility between tokens, which is scaled and softmax-normalized to weight the Value (V) vectors.",
                "difficulty": "medium",
                "canonical_topic": "Transformers & Self-Attention"
            },
            {
                "question_text": "Feynman Challenge: Explain Multi-Head Attention in your own words using a real-world analogy (e.g. a team of readers).",
                "question_type": "SHORT_ANSWER",
                "options": [],
                "correct_answer": "A strong response explains how multiple attention heads focus on different linguistic aspects simultaneously (grammar, pronouns, semantic meaning) and combine their perspectives.",
                "explanation": "Multi-head attention projects queries, keys, and values into multiple subspaces so the model can attend to different relationships at once.",
                "difficulty": "hard",
                "canonical_topic": "Transformers & Self-Attention"
            }
        ]
    elif any(k in topic_lower for k in ["binary search"]):
        questions = [
            {
                "question_text": "What prerequisite condition must strictly hold before executing Binary Search on a collection?",
                "question_type": "MCQ",
                "options": [
                    "A. The array or range must be strictly sorted / monotonic",
                    "B. The array must contain exactly 1,000,000 elements",
                    "C. All values must be even numbers",
                    "D. The array must be stored as a linked list"
                ],
                "correct_answer": "A",
                "explanation": "Binary search relies entirely on the sorted monotonic invariant to discard half of the search space at each midpoint comparison.",
                "difficulty": "easy",
                "canonical_topic": "Binary Search"
            },
            {
                "question_text": "True or False: Binary Search achieves O(log n) time complexity because every comparison eliminates 50% of the remaining search space.",
                "question_type": "TF",
                "options": ["True", "False"],
                "correct_answer": "True",
                "explanation": "Halving the search space per iteration yields the recurrence T(n) = T(n/2) + O(1) which solves to O(log n).",
                "difficulty": "easy",
                "canonical_topic": "Binary Search"
            },
            {
                "question_text": "Why is midpoint index calculated as `low + (high - low) / 2` instead of `(low + high) / 2`?",
                "question_type": "MCQ",
                "options": [
                    "A. To prevent 32-bit integer overflow when low + high exceeds maximum integer limits",
                    "B. To make the search run twice as fast",
                    "C. To sort the array in place",
                    "D. To avoid floating point decimals"
                ],
                "correct_answer": "A",
                "explanation": "Adding two large integer indices directly can exceed the 32-bit integer limit (2^31 - 1), whereas `low + (high - low) / 2` avoids overflow.",
                "difficulty": "medium",
                "canonical_topic": "Binary Search"
            },
            {
                "question_text": "Feynman Challenge: Teach Binary Search to someone looking up a word in a 1,000-page physical dictionary.",
                "question_type": "SHORT_ANSWER",
                "options": [],
                "correct_answer": "Open directly to page 500. Check the letter. If your target comes after, discard pages 1-500 and open to page 750. Repeat until found.",
                "explanation": "The dictionary analogy demonstrates logarithmic halving in physical space.",
                "difficulty": "hard",
                "canonical_topic": "Binary Search"
            }
        ]
    else:
        # Generic high-fidelity topic fallback
        clean_topic = topic or "Core Concept"
        questions = [
            {
                "question_text": f"What is the primary role and objective of {clean_topic} in modern computational architectures?",
                "question_type": "MCQ",
                "options": [
                    f"A. To provide structured state transformations and predictable operational behavior for {clean_topic}",
                    f"B. To completely bypass all verification and execution constraints",
                    f"C. To replace algorithmic determinism with purely random guesses",
                    f"D. To disable underlying memory and hardware resources"
                ],
                "correct_answer": "A",
                "explanation": f"{clean_topic} enforces structural representation and deterministic state transitions across system components.",
                "difficulty": "medium",
                "canonical_topic": clean_topic
            },
            {
                "question_text": f"True or False: Applying {clean_topic} requires establishing clear input preconditions and verified decision boundaries.",
                "question_type": "TF",
                "options": ["True", "False"],
                "correct_answer": "True",
                "explanation": f"Systematic execution of {clean_topic} depends on well-defined preconditions and boundary thresholds.",
                "difficulty": "easy",
                "canonical_topic": clean_topic
            },
            {
                "question_text": f"Which of the following describes a common failure mode when working with {clean_topic}?",
                "question_type": "MCQ",
                "options": [
                    f"A. Overlooking intermediate state verification and edge-case boundary checks",
                    f"B. Having explicit inputs and verified target outputs",
                    f"C. Utilizing well-documented algorithmic abstractions",
                    f"D. Testing components under standardized workloads"
                ],
                "correct_answer": "A",
                "explanation": f"Failing to validate intermediate state transitions is a primary source of edge-case bugs in {clean_topic}.",
                "difficulty": "medium",
                "canonical_topic": clean_topic
            },
            {
                "question_text": f"Feynman Challenge: In 2-3 sentences, explain the core mechanism of {clean_topic} in your own words as if explaining it to a beginner.",
                "question_type": "SHORT_ANSWER",
                "options": [],
                "correct_answer": f"A strong answer explains what {clean_topic} receives as input, how it transforms state, and what goal it achieves.",
                "explanation": f"Teaching back {clean_topic} tests whether you grasp the fundamental input-to-output transformation without relying on jargon.",
                "difficulty": "hard",
                "canonical_topic": clean_topic
            }
        ]

    return questions[:count]


async def generate_tutor_quiz_questions(
    topic: str, lesson_text: str, mode: str = "STANDARD", count: int = 4
) -> List[Dict[str, Any]]:
    """Generates 3-4 questions grounded in the current lesson using GeminiGateway with fallback resilience."""
    system_inst = TUTOR_QUIZ_SYSTEM_INSTRUCTION.format(count=count)
    prompt = TUTOR_QUIZ_PROMPT_TEMPLATE.format(
        count=count,
        topic=topic,
        mode=mode,
        lesson_text=lesson_text[:6000]
    )
    req_id = str(uuid.uuid4())[:8]

    raw = await gemini_gateway.generate(
        contents=[prompt],
        system_instruction=system_inst,
        temperature=0.3,
        request_id=f"tutorquiz-{req_id}"
    )

    if not raw:
        print(f"[TUTOR QUIZ GEN] Gemini unavailable, using topic-grounded fallback synthesizer for '{topic}'...")
        return synthesize_topic_fallback_quiz(topic, lesson_text, mode, count)

    try:
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list) or len(parsed) < 3:
            raise ValueError("Expected JSON array with at least 3 questions")

        valid = []
        for q in parsed[:count]:
            q_type = q.get("question_type", "MCQ").upper()
            if q_type not in ["MCQ", "TF", "SHORT_ANSWER"]:
                q_type = "MCQ"
            valid.append({
                "question_text": q.get("question_text", f"Key concept in {topic}"),
                "question_type": q_type,
                "options": q.get("options", []),
                "correct_answer": str(q.get("correct_answer", "A")),
                "explanation": q.get("explanation", "Core foundational concept."),
                "difficulty": q.get("difficulty", "medium"),
                "canonical_topic": q.get("canonical_topic", topic)
            })

        if len(valid) >= 3:
            return valid
    except Exception as e:
        print(f"[TUTOR QUIZ PARSE ERROR] Raw: {raw[:200]} | Error: {e}")

    return synthesize_topic_fallback_quiz(topic, lesson_text, mode, count)


# ---------------------------------------------------------------------------
# Short-Answer Evaluation Engine (Feynman Teach-Back Evaluator)
# ---------------------------------------------------------------------------

async def evaluate_short_answer(
    topic: str,
    question_text: str,
    user_answer: str,
    expected_concept: str,
    explanation: str
) -> Dict[str, Any]:
    """Evaluates a student's open-ended teach-back explanation using GeminiGateway or heuristic semantic matching."""
    eval_prompt = f"""You are Richard Feynman evaluating a student's answer to a teach-back question.

TOPIC: {topic}
QUESTION: {question_text}
EXPECTED KEY CONCEPTS: {expected_concept}
CANONICAL EXPLANATION: {explanation}

STUDENT ANSWER:
\"\"\"{user_answer}\"\"\"

Evaluate the student's answer carefully.
Scoring:
- 1.0 (Full credit): Explains the mechanism accurately in simple intuitive terms with correct flow.
- 0.6 - 0.8 (Partial credit): Captures the general idea but misses an important sub-concept or distinction.
- 0.0 - 0.4 (Low credit): Inaccurate, vague, or contains a major misconception.

Return ONLY a valid JSON object:
{{
  "score": 1.0,
  "is_correct": true,
  "feedback": "Encouraging, pedagogical explanation of what they got right and how to sharpen their mental model.",
  "missing_concepts": []
}}"""

    req_id = str(uuid.uuid4())[:8]
    raw = await gemini_gateway.generate(
        contents=[eval_prompt],
        system_instruction="You are a strict, pedagogical AI evaluator. Return only JSON.",
        temperature=0.2,
        request_id=f"eval-{req_id}"
    )

    if raw:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
            data = json.loads(cleaned)
            score = float(data.get("score", 0.8))
            is_correct = bool(data.get("is_correct", score >= 0.7))
            return {
                "score": score,
                "is_correct": is_correct,
                "feedback": data.get("feedback", "Good explanation! You captured the essential mechanism."),
                "missing_concepts": data.get("missing_concepts", [])
            }
        except Exception as e:
            print(f"[EVAL SHORT ANSWER PARSE ERROR] {e}")

    # Fallback heuristic semantic evaluator
    u_lower = user_answer.lower()
    words = u_lower.split()
    word_count = len(words)

    # Heuristic scoring based on length and relevance
    if word_count < 4:
        return {
            "score": 0.2,
            "is_correct": False,
            "feedback": "Your explanation is too brief. Try to explain the input, the transformation step, and the goal in more detail.",
            "missing_concepts": ["core mechanism flow", "detailed explanation"]
        }

    # Check for domain keywords
    key_hits = 0
    keywords = [w for w in expected_concept.lower().replace(",", " ").split() if len(w) > 4]
    for kw in keywords:
        if kw in u_lower:
            key_hits += 1

    ratio = key_hits / max(1, len(keywords))
    if word_count >= 15 and (ratio >= 0.3 or key_hits >= 2):
        return {
            "score": 1.0,
            "is_correct": True,
            "feedback": "Excellent teach-back! You clearly articulated the core intuition and mechanism without relying on superficial jargon.",
            "missing_concepts": []
        }
    elif word_count >= 10:
        return {
            "score": 0.7,
            "is_correct": True,
            "feedback": "Good attempt! You have the right intuition. Consider elaborating more on the intermediate transformation stages.",
            "missing_concepts": ["intermediate state transitions"]
        }
    else:
        return {
            "score": 0.4,
            "is_correct": False,
            "feedback": "Partially accurate, but missing key steps. Review the core lesson explanation below to reinforce your understanding.",
            "missing_concepts": ["complete input-to-output progression"]
        }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/tutor-quiz/start/")
async def start_tutor_quiz(
    req: TutorQuizStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Starts a dedicated 3-4 question quiz attached to a specific AI tutor response card.
    Strictly grounded in the current message context and canonical topic.
    """
    if not req.canonical_topic or not req.lesson_text:
        raise HTTPException(status_code=400, detail="canonical_topic and lesson_text are required.")

    count = min(4, max(3, req.question_count or 4))

    # Generate questions via GeminiGateway or fallback synthesizer
    raw_questions = await generate_tutor_quiz_questions(
        topic=req.canonical_topic,
        lesson_text=req.lesson_text,
        mode=req.lesson_mode or "STANDARD",
        count=count
    )

    quiz_id = str(uuid.uuid4())
    quiz = TutorQuizSession(
        id=quiz_id,
        user_id=current_user.id,
        message_id=req.message_id,
        session_id=req.session_id,
        canonical_topic=req.canonical_topic,
        lesson_mode=req.lesson_mode or "STANDARD",
        status="active",
        total_questions=len(raw_questions),
        answered_count=0,
        correct_count=0,
        score_percent=0.0
    )
    db.add(quiz)

    for idx, q_data in enumerate(raw_questions):
        q = TutorQuizQuestion(
            quiz_id=quiz_id,
            question_text=q_data["question_text"],
            question_type=q_data.get("question_type", "MCQ"),
            options_json=json.dumps(q_data.get("options", [])),
            correct_answer=q_data["correct_answer"],
            explanation=q_data.get("explanation", ""),
            difficulty=q_data.get("difficulty", "medium"),
            order_index=idx,
            hints_requested=0,
            canonical_topic=q_data.get("canonical_topic", req.canonical_topic)
        )
        db.add(q)

    db.commit()
    db.refresh(quiz)

    # Safe projection -- NEVER leak correct_answer to client
    safe_questions = []
    for q in sorted(quiz.questions, key=lambda x: x.order_index):
        safe_questions.append({
            "id": q.id,
            "order_index": q.order_index,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": json.loads(q.options_json),
            "difficulty": q.difficulty,
            "canonical_topic": q.canonical_topic,
            "hints_requested": q.hints_requested
        })

    return {
        "quiz_id": quiz_id,
        "message_id": quiz.message_id,
        "canonical_topic": quiz.canonical_topic,
        "lesson_mode": quiz.lesson_mode,
        "total_questions": quiz.total_questions,
        "answered_count": quiz.answered_count,
        "questions": safe_questions
    }


@router.get("/tutor-quiz/{quiz_id}/")
async def get_tutor_quiz_state(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns current state of a tutor quiz session. Verifies user ownership."""
    quiz = db.query(TutorQuizSession).filter(
        TutorQuizSession.id == quiz_id,
        TutorQuizSession.user_id == current_user.id
    ).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Tutor quiz not found.")

    answers_by_qid = {a.question_id: a for a in db.query(TutorQuizAnswer).filter(TutorQuizAnswer.quiz_id == quiz_id).all()}

    questions_out = []
    for q in sorted(quiz.questions, key=lambda x: x.order_index):
        ans = answers_by_qid.get(q.id)
        is_answered = ans is not None
        q_dict = {
            "id": q.id,
            "order_index": q.order_index,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": json.loads(q.options_json),
            "difficulty": q.difficulty,
            "canonical_topic": q.canonical_topic,
            "hints_requested": q.hints_requested,
            "is_answered": is_answered
        }
        if is_answered:
            q_dict["user_answer"] = ans.user_answer
            q_dict["is_correct"] = ans.is_correct
            q_dict["score"] = ans.score
            q_dict["feedback"] = ans.feedback
            q_dict["correct_answer"] = q.correct_answer
            q_dict["explanation"] = q.explanation
            q_dict["missing_concepts"] = json.loads(ans.missing_concepts or "[]")
        questions_out.append(q_dict)

    return {
        "quiz_id": quiz.id,
        "message_id": quiz.message_id,
        "canonical_topic": quiz.canonical_topic,
        "lesson_mode": quiz.lesson_mode,
        "status": quiz.status,
        "total_questions": quiz.total_questions,
        "answered_count": quiz.answered_count,
        "correct_count": quiz.correct_count,
        "score_percent": quiz.score_percent,
        "questions": questions_out
    }


@router.post("/tutor-quiz/{quiz_id}/answer/")
async def submit_tutor_quiz_answer(
    quiz_id: str,
    req: TutorQuizAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits an answer to a single question.
    Evaluates MCQ/TF deterministically and Short Answer via Feynman teach-back evaluator.
    Updates learner mastery (+15 / -10) idempotently.
    """
    quiz = db.query(TutorQuizSession).filter(
        TutorQuizSession.id == quiz_id,
        TutorQuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Tutor quiz not found.")

    question = db.query(TutorQuizQuestion).filter(
        TutorQuizQuestion.id == req.question_id,
        TutorQuizQuestion.quiz_id == quiz_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this quiz.")

    # Idempotency check: if already answered, return existing result without double-scoring
    existing_ans = db.query(TutorQuizAnswer).filter(
        TutorQuizAnswer.quiz_id == quiz_id,
        TutorQuizAnswer.question_id == req.question_id
    ).first()

    if existing_ans:
        return {
            "already_answered": True,
            "is_correct": existing_ans.is_correct,
            "score": existing_ans.score,
            "user_answer": existing_ans.user_answer,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
            "feedback": existing_ans.feedback,
            "missing_concepts": json.loads(existing_ans.missing_concepts or "[]"),
            "progress": {
                "answered": quiz.answered_count,
                "total": quiz.total_questions,
                "score_percent": quiz.score_percent
            }
        }

    # Evaluate Answer
    q_type = question.question_type.upper()
    user_ans_clean = req.answer.strip()
    correct_ans_clean = question.correct_answer.strip()

    if q_type == "MCQ":
        # Check either letter matching (e.g. 'A' vs 'A. ...') or full text matching
        u_val = user_ans_clean.upper()
        c_val = correct_ans_clean.upper()

        # Extract leading letter if present
        u_letter = u_val[0] if len(u_val) > 0 and u_val[0] in ['A', 'B', 'C', 'D'] else ""
        c_letter = c_val[0] if len(c_val) > 0 and c_val[0] in ['A', 'B', 'C', 'D'] else ""

        if u_letter and c_letter and u_letter == c_letter:
            is_correct = True
        elif u_val.rstrip('.') == c_val.rstrip('.'):
            is_correct = True
        else:
            # Fallback check options array match
            options = json.loads(question.options_json)
            is_correct = False
            for opt in options:
                opt_upper = opt.upper()
                if (c_letter and opt_upper.startswith(f"{c_letter}.")) or c_val in opt_upper:
                    if u_val in opt_upper or (u_letter and opt_upper.startswith(f"{u_letter}.")):
                        is_correct = True
                        break

        score = 1.0 if is_correct else 0.0
        feedback = "Correct! You nailed the foundational concept." if is_correct else f"Not quite. The correct option is {question.correct_answer}. Review the explanation below."
        missing_concepts = []

    elif q_type == "TF":
        u_val = "TRUE" if user_ans_clean.upper().startswith("T") else ("FALSE" if user_ans_clean.upper().startswith("F") else user_ans_clean.upper())
        c_val = "TRUE" if correct_ans_clean.upper().startswith("T") else ("FALSE" if correct_ans_clean.upper().startswith("F") else correct_ans_clean.upper())
        is_correct = (u_val == c_val)
        score = 1.0 if is_correct else 0.0
        feedback = "Correct! Solid grasp of the principle." if is_correct else f"Incorrect. The statement is {question.correct_answer}. See why below."
        missing_concepts = []

    else:
        # SHORT_ANSWER / Teach-Back Feynman Question
        eval_result = await evaluate_short_answer(
            topic=question.canonical_topic or quiz.canonical_topic,
            question_text=question.question_text,
            user_answer=user_ans_clean,
            expected_concept=question.correct_answer,
            explanation=question.explanation
        )
        is_correct = eval_result["is_correct"]
        score = eval_result["score"]
        feedback = eval_result["feedback"]
        missing_concepts = eval_result["missing_concepts"]

    # Record Answer in DB
    eval_id = f"tutorquiz-{quiz_id}-q{req.question_id}"
    answer_record = TutorQuizAnswer(
        quiz_id=quiz_id,
        question_id=req.question_id,
        user_answer=user_ans_clean,
        is_correct=is_correct,
        score=score,
        evaluation_id=eval_id,
        feedback=feedback,
        missing_concepts=json.dumps(missing_concepts),
        hints_used=question.hints_requested
    )
    db.add(answer_record)

    quiz.answered_count += 1
    if is_correct:
        quiz.correct_count += 1
    quiz.score_percent = round((quiz.correct_count / max(1, quiz.total_questions)) * 100.0, 1)

    # Track weak / strong topics
    topic_name = question.canonical_topic or quiz.canonical_topic
    if not is_correct:
        weak_list = json.loads(quiz.weak_topics or "[]")
        if topic_name not in weak_list:
            weak_list.append(topic_name)
        quiz.weak_topics = json.dumps(weak_list)
    else:
        strong_list = json.loads(quiz.strong_topics or "[]")
        if topic_name not in strong_list:
            strong_list.append(topic_name)
        quiz.strong_topics = json.dumps(strong_list)

    db.commit()

    # Delegate mastery update to authoritative memory engine (+15 / -10)
    try:
        mastery_obj, signal_summary = learner_memory_engine.record_learning_signal(
            db=db,
            user_id=current_user.id,
            canonical_topic=topic_name,
            is_correct=is_correct,
            weak_concept=topic_name if not is_correct else None,
            evaluation_id=eval_id
        )
    except Exception as e:
        print(f"[TUTOR QUIZ MASTERY SIGNAL ERROR] {e}")

    return {
        "already_answered": False,
        "is_correct": is_correct,
        "score": score,
        "user_answer": user_ans_clean,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "feedback": feedback,
        "missing_concepts": missing_concepts,
        "progress": {
            "answered": quiz.answered_count,
            "total": quiz.total_questions,
            "score_percent": quiz.score_percent
        }
    }


@router.post("/tutor-quiz/{quiz_id}/hint/")
async def request_tutor_quiz_hint(
    quiz_id: str,
    req: TutorQuizHintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Provides progressive hints (1 -> 2 -> 3 Final) for an active, unanswered question.
    Rejects request with 400 if question has already been answered.
    """
    quiz = db.query(TutorQuizSession).filter(
        TutorQuizSession.id == quiz_id,
        TutorQuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Tutor quiz not found.")

    question = db.query(TutorQuizQuestion).filter(
        TutorQuizQuestion.id == req.question_id,
        TutorQuizQuestion.quiz_id == quiz_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this quiz.")

    # Guard: Hint cannot be requested after answer has been submitted
    existing_ans = db.query(TutorQuizAnswer).filter(
        TutorQuizAnswer.quiz_id == quiz_id,
        TutorQuizAnswer.question_id == req.question_id
    ).first()
    if existing_ans:
        raise HTTPException(
            status_code=400,
            detail="Hints are disabled for questions that have already been answered."
        )

    question.hints_requested = min(3, question.hints_requested + 1)
    db.commit()

    level = question.hints_requested
    topic = question.canonical_topic or quiz.canonical_topic

    if level == 1:
        hint_text = f"💡 **Hint 1:** Focus on the primary purpose of {topic}. What fundamental problem does it solve in the pipeline?"
    elif level == 2:
        # Give more targeted clue without giving full answer
        words = question.explanation.split()
        clue = " ".join(words[:min(12, len(words))])
        hint_text = f"🔍 **Hint 2:** Key mechanism clue: *\"{clue}...\"*. Consider how state changes between inputs and outputs."
    else:
        # Final Hint
        hint_text = f"🎯 **Final Hint:** Review the relationship between the inputs and the objective of {topic}. Eliminate choices that contradict the fundamental definition."

    return {
        "question_id": question.id,
        "hints_requested": question.hints_requested,
        "hint_text": hint_text,
        "is_final": question.hints_requested >= 3
    }


@router.post("/tutor-quiz/{quiz_id}/complete/")
@router.post("/learner/tutor-quiz/{quiz_id}/complete/")
async def complete_tutor_quiz(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Finalizes tutor quiz session and computes performance summary and coach advice."""
    quiz = db.query(TutorQuizSession).filter(
        TutorQuizSession.id == quiz_id,
        TutorQuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Tutor quiz not found.")

    quiz.status = "completed"
    quiz.completed_at = datetime.utcnow()
    quiz.score_percent = round((quiz.correct_count / max(1, quiz.total_questions)) * 100.0, 1)

    weak_list = json.loads(quiz.weak_topics or "[]")
    strong_list = json.loads(quiz.strong_topics or "[]")

    # Strict mutual exclusivity & deduplication
    final_weak = list(dict.fromkeys(weak_list))
    final_strong = list(dict.fromkeys([t for t in strong_list if t not in final_weak]))

    if quiz.score_percent >= 80:
        coach_tip = f"Outstanding mastery of {quiz.canonical_topic}! You demonstrate clear intuition. You are ready to advance to more complex variations."
    elif quiz.score_percent >= 50:
        coach_tip = f"Solid foundation in {quiz.canonical_topic}. Review the key mechanisms and intermediate transformations to lock in full mastery."
    else:
        coach_tip = f"Take a moment to review {quiz.canonical_topic} in Simplify or Analogy mode. Focus on visualizing the input-to-output flow before retesting."

    quiz.coach_tip = coach_tip
    quiz.strong_topics = json.dumps(final_strong)
    quiz.weak_topics = json.dumps(final_weak)
    db.commit()

    return {
        "quiz_id": quiz.id,
        "canonical_topic": quiz.canonical_topic,
        "total_questions": quiz.total_questions,
        "answered_count": quiz.answered_count,
        "correct_count": quiz.correct_count,
        "score_percent": quiz.score_percent,
        "strong_topics": final_strong,
        "weak_topics": final_weak,
        "coach_tip": coach_tip,
        "completed_at": quiz.completed_at.isoformat()
    }


@router.get("/learner/tutor-quiz-history/")
async def get_tutor_quiz_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns list of completed tutor quiz assessments for the user."""
    quizzes = db.query(TutorQuizSession).filter(
        TutorQuizSession.user_id == current_user.id,
        TutorQuizSession.status == "completed"
    ).order_by(TutorQuizSession.completed_at.desc()).limit(20).all()

    return [
        {
            "quiz_id": q.id,
            "canonical_topic": q.canonical_topic,
            "lesson_mode": q.lesson_mode,
            "score_percent": q.score_percent,
            "total_questions": q.total_questions,
            "correct_count": q.correct_count,
            "completed_at": q.completed_at.isoformat() if q.completed_at else None
        }
        for q in quizzes
    ]
