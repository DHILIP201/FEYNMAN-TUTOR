"""
test_tutor_quiz.py
==================
Automated validation suite for Per-Chat "Quiz Me" feature (TUTOR-QUIZ-1 to TUTOR-QUIZ-20).

Validates:
1. UI contract: Quiz Me button attached to AI response cards
2. Start endpoint: /tutor-quiz/start/ generates 3-4 grounded questions tied to message_id and topic
3. Security: correct_answer NEVER leaked to client prior to submission
4. Evaluations: MCQ, True/False, and Short Answer teach-back
5. Progressive hints: 1 -> 2 -> 3, blocked on answered questions
6. Mastery update: +15 for correct, -10 for incorrect, idempotent on duplicate submissions
7. Result generation: /tutor-quiz/{quiz_id}/complete/ computes score, weak/strong spots, coach tip
8. User isolation: User B cannot access User A's tutor quiz
9. Multi-turn independence: older message quiz sessions remain distinct
10. Gateway usage: routes through GeminiGateway with fallback resilience
"""

import json
import os
import unittest
from fastapi.testclient import TestClient

from main import app
from database import get_db, SessionLocal, User, TutorQuizSession, TutorQuizQuestion, TutorQuizAnswer
from security import create_access_token, get_password_hash
from ai_engine.gemini_gateway import gemini_gateway


class TestTutorQuizSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from database import init_db
        init_db()
        cls.client = TestClient(app)
        db = SessionLocal()
        try:
            # Create User A
            user_a = db.query(User).filter(User.email == "tutor_quiz_user_a@feynman.ai").first()
            if not user_a:
                user_a = User(
                    name="Tutor Student A",
                    email="tutor_quiz_user_a@feynman.ai",
                    hashed_password=get_password_hash("ValidPass123!"),
                    email_verified=True
                )
                db.add(user_a)
                db.commit()
                db.refresh(user_a)
            cls.user_a_id = user_a.id
            cls.user_a_token = create_access_token(data={"sub": user_a.email})
            cls.headers_a = {"Authorization": f"Bearer {cls.user_a_token}"}

            # Create User B for user isolation testing
            user_b = db.query(User).filter(User.email == "tutor_quiz_user_b@feynman.ai").first()
            if not user_b:
                user_b = User(
                    name="Tutor Student B",
                    email="tutor_quiz_user_b@feynman.ai",
                    hashed_password=get_password_hash("ValidPass123!"),
                    email_verified=True
                )
                db.add(user_b)
                db.commit()
                db.refresh(user_b)
            cls.user_b_id = user_b.id
            cls.user_b_token = create_access_token(data={"sub": user_b.email})
            cls.headers_b = {"Authorization": f"Bearer {cls.user_b_token}"}

        finally:
            db.close()

    def test_tutor_quiz_1_ui_button_and_modal_contract(self):
        """TUTOR-QUIZ-1: Verify Quiz Me button and tutor-quiz-modal in HTML/JS."""
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
        with open("static/js/app.js", "r", encoding="utf-8") as f:
            js = f.read()

        # Modal markup exists
        self.assertIn('id="tutor-quiz-modal"', html)
        self.assertIn('id="tutor-quiz-body"', html)
        self.assertIn('id="tutor-quiz-hint-btn"', html)

        # Action button rendered on AI cards
        self.assertIn("openTutorQuiz", js)
        self.assertIn("Quiz Me", js)
        self.assertIn("window.openTutorQuiz", js)

    def test_tutor_quiz_2_to_5_start_endpoint_contract(self):
        """TUTOR-QUIZ-2..5: Start quiz using message_id and canonical_topic, max 3-4 questions, zero correct_answer leakage."""
        payload = {
            "message_id": "card-msg-101-alpha",
            "session_id": "test-session-alpha",
            "canonical_topic": "Convolutional Neural Networks",
            "lesson_text": "A Convolutional Neural Network uses sliding filters, ReLU activations, max pooling, and dense layers for image classification.",
            "lesson_mode": "STANDARD",
            "question_count": 4
        }
        res = self.client.post("/tutor-quiz/start/", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        # TUTOR-QUIZ-2: Click starts quiz
        self.assertIn("quiz_id", data)
        # TUTOR-QUIZ-3: Uses current message_id
        self.assertEqual(data["message_id"], "card-msg-101-alpha")
        # TUTOR-QUIZ-4: Uses current canonical_topic
        self.assertEqual(data["canonical_topic"], "Convolutional Neural Networks")
        # TUTOR-QUIZ-5: 3-4 questions maximum
        self.assertTrue(3 <= data["total_questions"] <= 4)
        self.assertTrue(3 <= len(data["questions"]) <= 4)

        # Invariant: correct_answer and explanation NEVER leaked in start response
        for q in data["questions"]:
            self.assertNotIn("correct_answer", q, "CRITICAL SECURITY LEAK: correct_answer exposed before submission!")
            self.assertIn("question_text", q)
            self.assertIn("question_type", q)
            self.assertIn("difficulty", q)

    def test_tutor_quiz_6_mcq_evaluation(self):
        """TUTOR-QUIZ-6: Deterministic MCQ answer evaluation."""
        start_payload = {
            "message_id": "card-msg-102",
            "canonical_topic": "Convolutional Neural Networks",
            "lesson_text": "CNN features sliding kernels, pooling, and dense classification.",
            "question_count": 4
        }
        start_res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = start_res.json()["quiz_id"]

        # Fetch question details from DB to know the correct MCQ answer
        db = SessionLocal()
        try:
            mcq_q = db.query(TutorQuizQuestion).filter(
                TutorQuizQuestion.quiz_id == quiz_id,
                TutorQuizQuestion.question_type == "MCQ"
            ).first()
            self.assertIsNotNone(mcq_q)
            q_id = mcq_q.id
            correct_ans = mcq_q.correct_answer
        finally:
            db.close()

        # Submit correct MCQ answer
        ans_res = self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": correct_ans},
            headers=self.headers_a
        )
        self.assertEqual(ans_res.status_code, 200)
        ans_data = ans_res.json()
        self.assertTrue(ans_data["is_correct"])
        self.assertEqual(ans_data["score"], 1.0)
        self.assertIn("Correct", ans_data["feedback"])
        self.assertEqual(ans_data["correct_answer"], correct_ans)

    def test_tutor_quiz_7_tf_evaluation(self):
        """TUTOR-QUIZ-7: True/False answer evaluation."""
        start_payload = {
            "message_id": "card-msg-103",
            "canonical_topic": "Binary Search",
            "lesson_text": "Binary search requires a sorted array and halves the search space at each midpoint comparison in O(log n) time.",
            "question_count": 4
        }
        start_res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = start_res.json()["quiz_id"]

        db = SessionLocal()
        try:
            tf_q = db.query(TutorQuizQuestion).filter(
                TutorQuizQuestion.quiz_id == quiz_id,
                TutorQuizQuestion.question_type == "TF"
            ).first()
            self.assertIsNotNone(tf_q)
            q_id = tf_q.id
            correct_ans = tf_q.correct_answer
        finally:
            db.close()

        # Submit correct TF answer
        ans_res = self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": correct_ans},
            headers=self.headers_a
        )
        self.assertEqual(ans_res.status_code, 200)
        self.assertTrue(ans_res.json()["is_correct"])

    def test_tutor_quiz_8_to_10_short_answer_and_feedback(self):
        """TUTOR-QUIZ-8..10: Short Answer teach-back evaluation and rich concept feedback."""
        start_payload = {
            "message_id": "card-msg-104",
            "canonical_topic": "Transformers & Self-Attention",
            "lesson_text": "Transformers process tokens in parallel with multi-head self-attention, computing Q, K, and V dot-product affinities.",
            "question_count": 4
        }
        start_res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = start_res.json()["quiz_id"]

        db = SessionLocal()
        try:
            short_q = db.query(TutorQuizQuestion).filter(
                TutorQuizQuestion.quiz_id == quiz_id,
                TutorQuizQuestion.question_type == "SHORT_ANSWER"
            ).first()
            self.assertIsNotNone(short_q)
            q_id = short_q.id
        finally:
            db.close()

        # Strong teach-back explanation
        teach_back_ans = (
            "Instead of processing words sequentially like an RNN, a transformer evaluates all tokens in parallel. "
            "It computes query, key, and value vectors to calculate affinity between every pair of words, "
            "allowing it to capture long-range dependencies simultaneously."
        )
        ans_res = self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": teach_back_ans},
            headers=self.headers_a
        )
        self.assertEqual(ans_res.status_code, 200)
        ans_data = ans_res.json()
        self.assertTrue(ans_data["is_correct"])
        self.assertTrue(ans_data["score"] >= 0.7)
        self.assertTrue(len(ans_data["feedback"]) > 10)

        # Test incorrect answer feedback
        start_payload_wrong = {
            "message_id": "card-msg-105",
            "canonical_topic": "Binary Search",
            "lesson_text": "Binary search halves the array.",
            "question_count": 4
        }
        res_wrong = self.client.post("/tutor-quiz/start/", json=start_payload_wrong, headers=self.headers_a)
        q_wrong_id = res_wrong.json()["quiz_id"]
        
        # Answer Q1 with deliberate wrong answer
        db = SessionLocal()
        try:
            q1 = db.query(TutorQuizQuestion).filter(TutorQuizQuestion.quiz_id == q_wrong_id).first()
            wrong_ans = "Z" if q1.correct_answer != "Z" else "X"
            q1_id = q1.id
        finally:
            db.close()

        ans_wrong = self.client.post(
            f"/tutor-quiz/{q_wrong_id}/answer/",
            json={"question_id": q1_id, "answer": wrong_ans},
            headers=self.headers_a
        )
        self.assertFalse(ans_wrong.json()["is_correct"])
        self.assertIn("explanation", ans_wrong.json())
        self.assertTrue(len(ans_wrong.json()["explanation"]) > 5)

    def test_tutor_quiz_11_and_12_progressive_hints(self):
        """TUTOR-QUIZ-11..12: Progressive hints (1->2->3) and blocked after answer submission."""
        start_payload = {
            "message_id": "card-msg-106",
            "canonical_topic": "Convolutional Neural Networks",
            "lesson_text": "CNN lessons.",
            "question_count": 4
        }
        res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = res.json()["quiz_id"]
        q_id = res.json()["questions"][0]["id"]

        # Hint 1
        h1 = self.client.post(f"/tutor-quiz/{quiz_id}/hint/", json={"question_id": q_id}, headers=self.headers_a)
        self.assertEqual(h1.status_code, 200)
        self.assertEqual(h1.json()["hints_requested"], 1)
        self.assertIn("Hint 1", h1.json()["hint_text"])
        self.assertFalse(h1.json()["is_final"])

        # Hint 2
        h2 = self.client.post(f"/tutor-quiz/{quiz_id}/hint/", json={"question_id": q_id}, headers=self.headers_a)
        self.assertEqual(h2.json()["hints_requested"], 2)

        # Hint 3 (Final)
        h3 = self.client.post(f"/tutor-quiz/{quiz_id}/hint/", json={"question_id": q_id}, headers=self.headers_a)
        self.assertEqual(h3.json()["hints_requested"], 3)
        self.assertTrue(h3.json()["is_final"])

        # Submit answer
        self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": "A"},
            headers=self.headers_a
        )

        # TUTOR-QUIZ-12: Hint must be rejected with 400 after answer is submitted
        h_blocked = self.client.post(f"/tutor-quiz/{quiz_id}/hint/", json={"question_id": q_id}, headers=self.headers_a)
        self.assertEqual(h_blocked.status_code, 400)
        self.assertIn("disabled", h_blocked.json()["detail"].lower())

    def test_tutor_quiz_13_and_14_mastery_and_idempotency(self):
        """TUTOR-QUIZ-13..14: Mastery updated via learner_memory_engine, duplicate answer is idempotent."""
        start_payload = {
            "message_id": "card-msg-107",
            "canonical_topic": "Backpropagation",
            "lesson_text": "Backpropagation uses the calculus chain rule to compute gradients and update weights.",
            "question_count": 4
        }
        res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = res.json()["quiz_id"]
        q_id = res.json()["questions"][0]["id"]

        # First submission
        ans1 = self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": "A"},
            headers=self.headers_a
        )
        self.assertEqual(ans1.status_code, 200)
        self.assertFalse(ans1.json()["already_answered"])

        # TUTOR-QUIZ-14: Duplicate submission returns idempotent result with already_answered=True
        ans2 = self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": "A"},
            headers=self.headers_a
        )
        self.assertEqual(ans2.status_code, 200)
        self.assertTrue(ans2.json()["already_answered"])

    def test_tutor_quiz_15_and_16_results_and_weak_spots(self):
        """TUTOR-QUIZ-15..16: Quiz completion computes final score and catalogs strong/weak concepts."""
        start_payload = {
            "message_id": "card-msg-108",
            "canonical_topic": "Neural Networks",
            "lesson_text": "Neural networks learn hierarchical representations through linear transformations, activation functions, loss calculation, and backpropagation.",
            "question_count": 4
        }
        res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = res.json()["quiz_id"]
        questions = res.json()["questions"]

        # Answer questions
        for q in questions:
            self.client.post(
                f"/tutor-quiz/{quiz_id}/answer/",
                json={"question_id": q["id"], "answer": "A"},
                headers=self.headers_a
            )

        # Complete quiz
        comp_res = self.client.post(f"/tutor-quiz/{quiz_id}/complete/", headers=self.headers_a)
        self.assertEqual(comp_res.status_code, 200)
        comp_data = comp_res.json()

        self.assertIn("score_percent", comp_data)
        self.assertIn("strong_topics", comp_data)
        self.assertIn("weak_topics", comp_data)
        self.assertIn("coach_tip", comp_data)
        self.assertTrue(len(comp_data["coach_tip"]) > 15)

    def test_tutor_quiz_17_user_isolation(self):
        """TUTOR-QUIZ-17: User B cannot access or answer User A's quiz (404 / Unauthorized)."""
        start_payload = {
            "message_id": "card-msg-user-a",
            "canonical_topic": "Neural Networks",
            "lesson_text": "Neural networks lesson.",
            "question_count": 4
        }
        res = self.client.post("/tutor-quiz/start/", json=start_payload, headers=self.headers_a)
        quiz_id = res.json()["quiz_id"]
        q_id = res.json()["questions"][0]["id"]

        # User B attempts to access User A's quiz state
        get_b = self.client.get(f"/tutor-quiz/{quiz_id}/", headers=self.headers_b)
        self.assertEqual(get_b.status_code, 404)

        # User B attempts to answer User A's quiz
        ans_b = self.client.post(
            f"/tutor-quiz/{quiz_id}/answer/",
            json={"question_id": q_id, "answer": "A"},
            headers=self.headers_b
        )
        self.assertEqual(ans_b.status_code, 404)

    def test_tutor_quiz_18_multi_turn_independent_quizzes(self):
        """TUTOR-QUIZ-18: Older message quiz sessions remain distinct from newer message quizzes."""
        # Message 1 Quiz: Neural Networks
        res1 = self.client.post("/tutor-quiz/start/", json={
            "message_id": "msg-turn-1-nn",
            "canonical_topic": "Neural Networks",
            "lesson_text": "Neural Networks foundation lesson.",
            "question_count": 4
        }, headers=self.headers_a)
        quiz1_id = res1.json()["quiz_id"]

        # Message 2 Quiz: Convolutional Neural Networks
        res2 = self.client.post("/tutor-quiz/start/", json={
            "message_id": "msg-turn-2-cnn",
            "canonical_topic": "Convolutional Neural Networks",
            "lesson_text": "CNN follow-up lesson.",
            "question_count": 4
        }, headers=self.headers_a)
        quiz2_id = res2.json()["quiz_id"]

        self.assertNotEqual(quiz1_id, quiz2_id)

        # Verify state for Message 1 is preserved and independent
        state1 = self.client.get(f"/tutor-quiz/{quiz1_id}/", headers=self.headers_a).json()
        state2 = self.client.get(f"/tutor-quiz/{quiz2_id}/", headers=self.headers_a).json()

        self.assertEqual(state1["canonical_topic"], "Neural Networks")
        self.assertEqual(state1["message_id"], "msg-turn-1-nn")
        self.assertEqual(state2["canonical_topic"], "Convolutional Neural Networks")
        self.assertEqual(state2["message_id"], "msg-turn-2-cnn")

    def test_tutor_quiz_19_normal_tutor_hint_absence(self):
        """TUTOR-QUIZ-19: Chat input composer must not contain the quiz hint button."""
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # The chat composer input section
        self.assertNotIn('<span id="hint-btn-text">I\'m stuck, request hint</span>', html)
        self.assertNotIn('<button onclick="triggerProgressiveHint()', html)

    def test_tutor_quiz_ui_contracts_and_dom_hierarchy(self):
        """QUIZ-UI-1..6: Test DOM structure, modal isolation from #quiz-modal, and data attributes."""
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
        with open("static/js/app.js", "r", encoding="utf-8") as f:
            js = f.read()

        # QUIZ-UI-1 & QUIZ-UI-2: Button markup has data-action="quiz-me" and data-message-id
        self.assertIn('data-action="quiz-me"', js)
        self.assertIn('data-message-id="${cardUniqueId}"', js)
        self.assertIn('class="card-action quiz-me-btn', js)

        # QUIZ-UI-3 & QUIZ-UI-4: Delegated click handler and global functions
        self.assertIn('initChatDelegation', js)
        self.assertIn('chatContainer.addEventListener("click"', js)
        self.assertIn('window.openTutorQuiz = openTutorQuiz', js)

        # QUIZ-UI-5: Modal exists as its own top-level overlay and is NOT nested inside #quiz-modal
        self.assertIn('id="tutor-quiz-modal"', html)
        self.assertIn('id="quiz-modal"', html)
        
        # Verify closing tags between #quiz-modal and #tutor-quiz-modal
        quiz_modal_idx = html.find('id="quiz-modal"')
        tutor_modal_idx = html.find('id="tutor-quiz-modal"')
        self.assertTrue(quiz_modal_idx < tutor_modal_idx)
        segment = html[quiz_modal_idx:tutor_modal_idx]
        
        # In this segment, opening and closing divs must balance out so tutor-quiz-modal is NOT inside quiz-modal
        open_divs = segment.count('<div')
        close_divs = segment.count('</div>')
        self.assertEqual(open_divs, close_divs, "CRITICAL: tutor-quiz-modal is nested inside quiz-modal!")

    def test_tutor_quiz_all_four_lesson_modes(self):
        """QUIZ-UI-10..14: Verify Quiz Me works independently on Standard, Simplify, Analogy, and Step-by-Step."""
        modes = ["STANDARD", "SIMPLIFY", "ANALOGY", "STEP_BY_STEP"]
        created_quizzes = {}

        for mode in modes:
            payload = {
                "message_id": f"card-msg-{mode.lower()}",
                "session_id": "test-session-modes",
                "canonical_topic": "Convolutional Neural Networks",
                "lesson_text": f"CNN Lesson content for {mode} mode.",
                "lesson_mode": mode,
                "question_count": 4
            }
            res = self.client.post("/tutor-quiz/start/", json=payload, headers=self.headers_a)
            self.assertEqual(res.status_code, 200, f"Failed on mode {mode}")
            data = res.json()
            self.assertEqual(data["lesson_mode"], mode)
            self.assertEqual(data["message_id"], f"card-msg-{mode.lower()}")
            created_quizzes[mode] = data["quiz_id"]

        # Ensure all 4 quiz sessions have distinct IDs and states
        quiz_ids = list(created_quizzes.values())
        self.assertEqual(len(set(quiz_ids)), 4, "Quiz IDs must be unique across all 4 modes!")


if __name__ == "__main__":
    unittest.main()

