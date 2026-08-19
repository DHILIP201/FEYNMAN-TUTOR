"""
Feynman AI -- Interactive PDF Quiz Mode Router
"""

import uuid
import json
import os
import re
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, User, QuizSession, QuizQuestion, QuizAnswer, ChatSession
from security import get_current_user

router = APIRouter(tags=["Quiz Mode"])

class QuizStartRequest(BaseModel):
    session_id: str = Field(..., description="Chat session ID with uploaded PDF")
    question_count: int = Field(default=8, ge=3, le=15)
    difficulty: str = Field(default="adaptive")

class QuizAnswerRequest(BaseModel):
    question_id: int
    answer: str = Field(..., min_length=1, max_length=500)

class QuizHintRequest(BaseModel):
    question_id: int

QUIZ_GENERATION_PROMPT = """You are an expert educational assessment designer.

You have access to the following study material extracted from the student's uploaded PDF:

--- STUDY MATERIAL ---
{context}
--- END MATERIAL ---

Generate exactly {count} high-quality quiz questions based ONLY on the above material.

CRITICAL RULES:
- Every question must be answerable from the provided material.
- Include question_type: "MCQ" (4 options A/B/C/D) or "TF" (True/False).
- For MCQ: provide exactly 4 options as a list, with correct_answer being A, B, C, or D.
- For TF: provide options ["True", "False"], with correct_answer being "True" or "False".
- Each question must cite source_page (integer page number from the document).
- explanation must be 1-2 sentences explaining why the answer is correct.
- Vary difficulty: include ~30% easy, ~50% medium, ~20% hard.

Return ONLY a valid JSON array with this exact structure:
[
  {
    "question_text": "...",
    "question_type": "MCQ",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_answer": "A",
    "explanation": "...",
    "canonical_topic": "...",
    "source_page": 1,
    "difficulty": "medium"
  }
]

Return only the JSON array, no markdown fences, no preamble."""


def generate_quiz_questions(context: str, count: int, topic_hint: str) -> List[dict]:
    try:
        import google.generativeai as genai
        api_key = (os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY_2")
                   or os.getenv("GEMINI_API_KEY_3") or os.getenv("GEMINI_API_KEY") or "")
        if not api_key:
            raise ValueError("No Gemini API key available")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = QUIZ_GENERATION_PROMPT.format(context=context[:8000], count=count)
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        questions = json.loads(raw)
        if not isinstance(questions, list):
            raise ValueError("Expected JSON array")
        return questions[:count]
    except Exception as e:
        print(f"[QUIZ GEN ERROR] {e}")
        return [{
            "question_text": f"What is a key concept in this study material about {topic_hint}?",
            "question_type": "MCQ",
            "options": [
                "A. The material introduces core definitions and mechanisms",
                "B. The material is purely theoretical with no practical application",
                "C. The material covers unrelated topics",
                "D. The material is an index only"
            ],
            "correct_answer": "A",
            "explanation": "The uploaded study material introduces the core definitions and mechanisms of the topic.",
            "canonical_topic": topic_hint,
            "source_page": 1,
            "difficulty": "easy"
        }]


def fetch_rag_context(session_id: str, topic: str) -> str:
    try:
        from rag import get_relevant_chunks
        chunks = get_relevant_chunks(session_id, topic, top_k=12)
        if chunks:
            return "\n\n".join(
                c.get("content", c) if isinstance(c, dict) else c
                for c in chunks
            )
    except Exception as e:
        print(f"[QUIZ RAG] Could not fetch RAG context: {e}")
    return ""


HINT_LEVELS = [
    "Think about the core concept described in the study material for this topic.",
    "Consider what the material says about the mechanism or process involved.",
    "Review the relevant section of the PDF -- the answer relates to the key definition given.",
]

def get_hint_for_question(question: QuizQuestion, hints_used: int) -> str:
    level = min(hints_used, len(HINT_LEVELS) - 1)
    topic_hint = question.canonical_topic or "this concept"
    return f"Hint {hints_used + 1}: {HINT_LEVELS[level]} (Related topic: {topic_hint})"


def record_quiz_signal(db: Session, user_id: int, topic: str, is_correct: bool):
    try:
        from database import LearningEvent, TopicMastery
        event_type = "quiz_correct" if is_correct else "quiz_incorrect"
        db.add(LearningEvent(
            user_id=user_id,
            canonical_topic=topic,
            event_type=event_type,
            metadata_json=json.dumps({"source": "pdf_quiz"})
        ))
        mastery_row = db.query(TopicMastery).filter(
            TopicMastery.user_id == user_id,
            TopicMastery.canonical_topic == topic
        ).first()
        if not mastery_row:
            mastery_row = TopicMastery(
                user_id=user_id,
                canonical_topic=topic,
                mastery_score=0,
                confidence_score=0.5
            )
            db.add(mastery_row)
        if is_correct:
            mastery_row.mastery_score = min(100, mastery_row.mastery_score + 15)
            mastery_row.confidence_score = min(1.0, mastery_row.confidence_score + 0.10)
            mastery_row.correct_count += 1
        else:
            mastery_row.mastery_score = max(0, mastery_row.mastery_score - 10)
            mastery_row.confidence_score = max(0.0, mastery_row.confidence_score - 0.15)
            mastery_row.incorrect_count += 1
        mastery_row.attempt_count += 1
        mastery_row.last_studied_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        print(f"[QUIZ MASTERY ERROR] {e}")
        try:
            db.rollback()
        except Exception:
            pass


@router.post("/quiz/start/")
async def start_quiz(
    req: QuizStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chat_session = db.query(ChatSession).filter(
        ChatSession.id == req.session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found or access denied.")
    if not chat_session.has_doc:
        raise HTTPException(status_code=400, detail="No study document found. Please upload a PDF first.")

    topic_hint = chat_session.title or "the uploaded study material"
    context = fetch_rag_context(req.session_id, topic_hint)
    if not context:
        context = f"Study material about {topic_hint}."

    raw_questions = generate_quiz_questions(context, req.question_count, topic_hint)

    quiz_id = str(uuid.uuid4())
    quiz = QuizSession(
        id=quiz_id,
        user_id=current_user.id,
        document_session_id=req.session_id,
        status="active",
        total_questions=len(raw_questions)
    )
    db.add(quiz)
    db.flush()

    for idx, q in enumerate(raw_questions):
        db.add(QuizQuestion(
            quiz_id=quiz_id,
            question_text=q.get("question_text", ""),
            question_type=q.get("question_type", "MCQ"),
            options_json=json.dumps(q.get("options", [])),
            correct_answer=q.get("correct_answer", "A"),
            explanation=q.get("explanation", ""),
            canonical_topic=q.get("canonical_topic", topic_hint),
            source_page=q.get("source_page"),
            difficulty=q.get("difficulty", "medium"),
            order_index=idx
        ))

    db.commit()
    db.refresh(quiz)

    questions_safe = [
        {
            "id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": json.loads(q.options_json),
            "canonical_topic": q.canonical_topic,
            "source_page": q.source_page,
            "difficulty": q.difficulty,
            "order_index": q.order_index
        }
        for q in sorted(quiz.questions, key=lambda x: x.order_index)
    ]

    return {
        "quiz_id": quiz_id,
        "status": "active",
        "total_questions": quiz.total_questions,
        "topic": topic_hint,
        "questions": questions_safe
    }


@router.get("/quiz/{quiz_id}/")
async def get_quiz_state(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    answered_map = {}
    for q in quiz.questions:
        for a in q.answers:
            answered_map[q.id] = {"is_correct": a.is_correct, "user_answer": a.user_answer}

    questions_safe = [
        {
            "id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": json.loads(q.options_json),
            "canonical_topic": q.canonical_topic,
            "source_page": q.source_page,
            "difficulty": q.difficulty,
            "order_index": q.order_index,
            "answered": q.id in answered_map,
            "is_correct": answered_map[q.id]["is_correct"] if q.id in answered_map else None,
            "user_answer": answered_map[q.id]["user_answer"] if q.id in answered_map else None,
        }
        for q in sorted(quiz.questions, key=lambda x: x.order_index)
    ]

    return {
        "quiz_id": quiz_id,
        "status": quiz.status,
        "total_questions": quiz.total_questions,
        "answered_count": quiz.answered_count,
        "correct_count": quiz.correct_count,
        "score_percent": quiz.score_percent,
        "questions": questions_safe
    }


@router.post("/quiz/{quiz_id}/answer/")
async def submit_answer(
    quiz_id: str,
    req: QuizAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    if quiz.status != "active":
        raise HTTPException(status_code=400, detail="Quiz is already completed.")

    question = db.query(QuizQuestion).filter(
        QuizQuestion.id == req.question_id,
        QuizQuestion.quiz_id == quiz_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this quiz.")

    existing_answer = db.query(QuizAnswer).filter(
        QuizAnswer.quiz_id == quiz_id,
        QuizAnswer.question_id == req.question_id
    ).first()
    if existing_answer:
        return {
            "is_correct": existing_answer.is_correct,
            "user_answer": existing_answer.user_answer,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
            "source_page": question.source_page,
            "feedback": "Correct!" if existing_answer.is_correct else "Not quite.",
            "already_answered": True
        }

    user_ans = req.answer.strip().upper()
    correct_ans = question.correct_answer.strip().upper()
    if question.question_type == "TF":
        is_correct = user_ans in ("TRUE", "FALSE") and user_ans == correct_ans
    else:
        user_letter = user_ans[0] if user_ans else ""
        is_correct = user_letter == correct_ans[0]

    try:
        db.add(QuizAnswer(
            quiz_id=quiz_id,
            question_id=req.question_id,
            user_answer=req.answer,
            is_correct=is_correct,
            hints_used=0
        ))
        quiz.answered_count += 1
        if is_correct:
            quiz.correct_count += 1
        else:
            quiz.incorrect_count += 1
        if quiz.total_questions > 0:
            quiz.score_percent = round((quiz.correct_count / quiz.total_questions) * 100, 1)
        db.commit()
        record_quiz_signal(db, current_user.id, question.canonical_topic or "Study Material", is_correct)
    except Exception as e:
        db.rollback()
        if "uq_quiz_question_answer" not in str(e) and "UNIQUE constraint" not in str(e):
            print(f"[QUIZ ANSWER ERROR] {e}")
            raise HTTPException(status_code=500, detail="Failed to record answer.")

    if not is_correct and question.canonical_topic:
        try:
            weak = json.loads(quiz.weak_topics or "[]")
            if question.canonical_topic not in weak:
                weak.append(question.canonical_topic)
                quiz.weak_topics = json.dumps(weak)
                db.commit()
        except Exception:
            pass

    return {
        "is_correct": is_correct,
        "user_answer": req.answer,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "source_page": question.source_page,
        "feedback": "Correct! Great job." if is_correct else "Not quite. Review the explanation below.",
        "already_answered": False,
        "quiz_progress": {
            "answered": quiz.answered_count,
            "total": quiz.total_questions,
            "score_percent": quiz.score_percent
        }
    }


@router.post("/quiz/{quiz_id}/hint/")
async def get_hint(
    quiz_id: str,
    req: QuizHintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    if quiz.status != "active":
        raise HTTPException(status_code=400, detail="Hints are only available during an active quiz.")

    question = db.query(QuizQuestion).filter(
        QuizQuestion.id == req.question_id,
        QuizQuestion.quiz_id == quiz_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    existing = db.query(QuizAnswer).filter(
        QuizAnswer.quiz_id == quiz_id,
        QuizAnswer.question_id == req.question_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Question already answered. Hints are for unanswered questions only.")

    return {
        "hint": get_hint_for_question(question, 0),
        "question_id": req.question_id
    }


@router.post("/quiz/{quiz_id}/complete/")
async def complete_quiz(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    quiz.status = "completed"
    quiz.completed_at = datetime.utcnow()
    if quiz.total_questions > 0:
        quiz.score_percent = round((quiz.correct_count / quiz.total_questions) * 100, 1)
    db.commit()
    return {"message": "Quiz completed.", "quiz_id": quiz_id, "score_percent": quiz.score_percent}


@router.get("/quiz/{quiz_id}/results/")
async def get_quiz_results(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == current_user.id
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    strong_topics = set()
    weak_topics = json.loads(quiz.weak_topics or "[]")
    question_results = []

    for q in sorted(quiz.questions, key=lambda x: x.order_index):
        answered = db.query(QuizAnswer).filter(
            QuizAnswer.quiz_id == quiz_id,
            QuizAnswer.question_id == q.id
        ).first()
        question_results.append({
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": json.loads(q.options_json),
            "user_answer": answered.user_answer if answered else None,
            "correct_answer": q.correct_answer,
            "is_correct": answered.is_correct if answered else False,
            "explanation": q.explanation,
            "canonical_topic": q.canonical_topic,
            "source_page": q.source_page
        })
        if answered and answered.is_correct and q.canonical_topic:
            strong_topics.add(q.canonical_topic)

    score = quiz.score_percent
    if score >= 80:
        recommendation = "Excellent! Strong mastery. Consider attempting the advanced quiz."
    elif score >= 60:
        weak_str = ", ".join(weak_topics[:3]) if weak_topics else "highlighted topics"
        recommendation = f"Good progress! Review: {weak_str} before your next session."
    else:
        weak_str = ", ".join(weak_topics[:3]) if weak_topics else "the core concepts"
        recommendation = f"More review needed. Focus on: {weak_str} using the Feynman tutor before retaking."

    return {
        "quiz_id": quiz_id,
        "status": quiz.status,
        "total_questions": quiz.total_questions,
        "correct_count": quiz.correct_count,
        "incorrect_count": quiz.incorrect_count,
        "score_percent": quiz.score_percent,
        "mastery_change": round(quiz.correct_count * 15 - quiz.incorrect_count * 10, 1),
        "strong_topics": list(strong_topics - set(weak_topics)),
        "weak_topics": weak_topics,
        "recommendation": recommendation,
        "question_results": question_results,
        "completed_at": quiz.completed_at.isoformat() if quiz.completed_at else None
    }


@router.get("/learner/quiz-history/")
async def get_quiz_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quizzes = db.query(QuizSession).filter(
        QuizSession.user_id == current_user.id
    ).order_by(QuizSession.started_at.desc()).limit(20).all()

    return {
        "quizzes": [
            {
                "quiz_id": q.id,
                "status": q.status,
                "total_questions": q.total_questions,
                "correct_count": q.correct_count,
                "score_percent": q.score_percent,
                "weak_topics": json.loads(q.weak_topics or "[]"),
                "started_at": q.started_at.isoformat() if q.started_at else None,
                "completed_at": q.completed_at.isoformat() if q.completed_at else None
            }
            for q in quizzes
        ]
    }
