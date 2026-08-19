"""
Feynman AI -- Dedicated Interactive PDF Quiz Mode Test Runner (QUIZ-1 to QUIZ-16)
"""

import sys
import os
import uuid
import json
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from main import app
from database import get_db, SessionLocal, User, ChatSession, QuizSession, QuizQuestion, QuizAnswer, TopicMastery
from security import create_access_token, get_password_hash
from ai_engine.memory.learner_memory_engine import LearnerMemoryEngine

client = TestClient(app)
db = SessionLocal()
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} -- {detail}")
        failed += 1

print("=" * 70)
print("FEYNMAN AI -- INTERACTIVE PDF QUIZ MODE TEST SUITE (QUIZ-1 to QUIZ-16)")
print("=" * 70)

# Setup users
user_a = db.query(User).filter(User.email == "quiz_runner_a@test.com").first()
if not user_a:
    user_a = User(
        name="Student A",
        email="quiz_runner_a@test.com",
        hashed_password=get_password_hash("Password123!"),
        email_verified=True
    )
    db.add(user_a)
    db.commit()
    db.refresh(user_a)

user_b = db.query(User).filter(User.email == "quiz_runner_b@test.com").first()
if not user_b:
    user_b = User(
        name="Student B",
        email="quiz_runner_b@test.com",
        hashed_password=get_password_hash("Password123!"),
        email_verified=True
    )
    db.add(user_b)
    db.commit()
    db.refresh(user_b)

token_a = create_access_token(data={"sub": user_a.email})
token_b = create_access_token(data={"sub": user_b.email})
headers_a = {"Authorization": f"Bearer {token_a}"}
headers_b = {"Authorization": f"Bearer {token_b}"}

sess_id = f"doc_sess_{uuid.uuid4().hex[:8]}"
doc_session = ChatSession(
    id=sess_id,
    user_id=user_a.id,
    title="Neural Networks Mastery PDF",
    has_doc=True,
    mastery=25
)
db.add(doc_session)
db.commit()

# Helper to build mock quiz
def create_quiz(db, user_id, doc_id):
    qid = f"quiz_{uuid.uuid4().hex[:8]}"
    q = QuizSession(id=qid, user_id=user_id, document_session_id=doc_id, status="active", total_questions=3, weak_topics="[]")
    db.add(q)
    db.flush()
    q1 = QuizQuestion(
        quiz_id=qid,
        question_text="What is the role of an activation function?",
        question_type="MCQ",
        options_json=json.dumps(["A. Non-linearity", "B. Weight storage", "C. Pixel scaling", "D. Network routing"]),
        correct_answer="A",
        explanation="Activation functions introduce non-linear expressiveness.",
        canonical_topic="Activation Functions",
        source_page=2,
        difficulty="medium",
        order_index=0,
        hints_requested=0
    )
    q2 = QuizQuestion(
        quiz_id=qid,
        question_text="Backpropagation applies the calculus chain rule.",
        question_type="TF",
        options_json=json.dumps(["True", "False"]),
        correct_answer="True",
        explanation="Chain rule decomposes gradients layer by layer.",
        canonical_topic="Backpropagation",
        source_page=5,
        difficulty="easy",
        order_index=1,
        hints_requested=0
    )
    q3 = QuizQuestion(
        quiz_id=qid,
        question_text="Which optimizer uses both momentum and adaptive scaling?",
        question_type="MCQ",
        options_json=json.dumps(["A. Basic SGD", "B. Adam Optimizer", "C. Linear Regression", "D. Depth First Search"]),
        correct_answer="B",
        explanation="Adam combines first and second moment estimations.",
        canonical_topic="Optimizers",
        source_page=9,
        difficulty="hard",
        order_index=2,
        hints_requested=0
    )
    db.add_all([q1, q2, q3])
    db.commit()
    db.refresh(q)
    return q

# QUIZ-1
no_doc_id = f"nodoc_{uuid.uuid4().hex[:8]}"
db.add(ChatSession(id=no_doc_id, user_id=user_a.id, title="No Doc", has_doc=False))
db.commit()
r1 = client.post("/quiz/start/", json={"session_id": no_doc_id, "question_count": 5}, headers=headers_a)
check("QUIZ-1: Start quiz on session without PDF is rejected with 400", r1.status_code == 400 and "No study document" in r1.json().get("detail", ""))

# QUIZ-2 & QUIZ-3 & QUIZ-15
quiz = create_quiz(db, user_a.id, sess_id)
r2 = client.get(f"/quiz/{quiz.id}/", headers=headers_a)
d2 = r2.json()
has_correct = any("correct_answer" in q for q in d2.get("questions", []))
check("QUIZ-2: Grounded question schema and properties returned", r2.status_code == 200 and len(d2.get("questions", [])) == 3)
check("QUIZ-3: Valid source_page citations and canonical topics present", d2["questions"][0].get("source_page") == 2 and d2["questions"][0].get("canonical_topic") == "Activation Functions")
check("QUIZ-15: Correct answer NEVER leaked before submission / completion", not has_correct)

# QUIZ-4: Correct MCQ answer
q1 = quiz.questions[0]
r4 = client.post(f"/quiz/{quiz.id}/answer/", json={"question_id": q1.id, "answer": "A"}, headers=headers_a)
d4 = r4.json()
check("QUIZ-4: MCQ correct answer evaluated with positive feedback and page citation", d4.get("is_correct") is True and d4.get("source_page") == 2 and "Activation functions" in d4.get("explanation", ""))

# QUIZ-5: Incorrect MCQ answer
quiz5 = create_quiz(db, user_a.id, sess_id)
q1_5 = quiz5.questions[0]
r5 = client.post(f"/quiz/{quiz5.id}/answer/", json={"question_id": q1_5.id, "answer": "C"}, headers=headers_a)
d5 = r5.json()
db.refresh(quiz5)
weak = json.loads(quiz5.weak_topics or "[]")
check("QUIZ-5: MCQ incorrect answer returns correction and tracks weak topic", d5.get("is_correct") is False and "Activation Functions" in weak)

# QUIZ-6: True/False evaluation
q2 = quiz.questions[1]
r6 = client.post(f"/quiz/{quiz.id}/answer/", json={"question_id": q2.id, "answer": "True"}, headers=headers_a)
check("QUIZ-6: True/False answer evaluated correctly", r6.status_code == 200 and r6.json().get("is_correct") is True)

# QUIZ-7 & QUIZ-8: Progressive hints in active quiz
quiz8 = create_quiz(db, user_a.id, sess_id)
q3_8 = quiz8.questions[2]
h1 = client.post(f"/quiz/{quiz8.id}/hint/", json={"question_id": q3_8.id}, headers=headers_a).json()
h2 = client.post(f"/quiz/{quiz8.id}/hint/", json={"question_id": q3_8.id}, headers=headers_a).json()
h3 = client.post(f"/quiz/{quiz8.id}/hint/", json={"question_id": q3_8.id}, headers=headers_a).json()
check("QUIZ-7: Hint requests succeed during active unanswered quiz question", "hint" in h1)
check("QUIZ-8: Hints progress sequentially (1 -> 2 -> 3 final)", h1.get("hint_number") == 1 and h2.get("hint_number") == 2 and h3.get("is_final_hint") is True)

# QUIZ-9: Hint blocked on answered question
r9 = client.post(f"/quiz/{quiz.id}/hint/", json={"question_id": q1.id}, headers=headers_a)
check("QUIZ-9: Hint rejected on already-answered question with 400", r9.status_code == 400 and "already been answered" in r9.json().get("detail", ""))

# QUIZ-10: Idempotency
r10_1 = client.post(f"/quiz/{quiz.id}/answer/", json={"question_id": q1.id, "answer": "A"}, headers=headers_a)
check("QUIZ-10: Duplicate answer submission is idempotent and does not fail", r10_1.status_code == 200 and r10_1.json().get("already_answered") is True)

# QUIZ-11: User isolation
r11_get = client.get(f"/quiz/{quiz.id}/", headers=headers_b)
r11_ans = client.post(f"/quiz/{quiz.id}/answer/", json={"question_id": q1.id, "answer": "A"}, headers=headers_b)
check("QUIZ-11: User isolation strictly enforced (User B cannot access User A quiz)", r11_get.status_code == 404 and r11_ans.status_code == 404)

# QUIZ-12 & QUIZ-13 & QUIZ-14: Completion, results, weak spots, recommendations
q3 = quiz.questions[2]
client.post(f"/quiz/{quiz.id}/answer/", json={"question_id": q3.id, "answer": "B"}, headers=headers_a)
r12_comp = client.post(f"/quiz/{quiz.id}/complete/", headers=headers_a)
r12_res = client.get(f"/quiz/{quiz.id}/results/", headers=headers_a)
d12 = r12_res.json()
check("QUIZ-12: Quiz completion computes final score percentage", r12_comp.status_code == 200 and d12.get("score_percent") == 100.0)
check("QUIZ-13: Topic masteries and review items properly cataloged in results", "strong_topics" in d12 and "weak_topics" in d12)
check("QUIZ-14: Pedagogical AI Coach recommendation returned", "recommendation" in d12 and len(d12["recommendation"]) > 10)

# QUIZ-16: Learner history
r16 = client.get("/learner/quiz-history/", headers=headers_a)
d16 = r16.json()
check("QUIZ-16: Learner quiz history returns completed assessments list", r16.status_code == 200 and len(d16.get("quizzes", [])) >= 1)

db.close()

print("=" * 70)
print(f"QUIZ MODE TEST RESULTS: {passed} PASSED, {failed} FAILED")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
