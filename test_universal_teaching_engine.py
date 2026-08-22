"""
test_universal_teaching_engine.py
==================================
Comprehensive Test Suite for Universal Feynman AI Teaching Engine & Clean Chat Contracts.

Validates:
1. Cross-Domain Verification (CS, Math, Physics, Biology, Chemistry, Economics, History).
2. Clean Chat Invariant: No trailing Active Recall / Checkpoint clutter in normal lesson cards.
3. Multi-Angle Presentation Strategy & Bounded Presentation Memory: Consecutive identical queries
   produce complementary pedagogical perspectives and matching diagrams.
4. Adaptive Visual Model Generation: Valid, non-empty, semantically matched Mermaid diagrams.
5. Assessment Isolation & Mutual Exclusivity: [Quiz Me] and PDF Quiz result sets are strictly disjoint.
6. Mode Invariants: STANDARD, SIMPLIFY, ANALOGY, STEP_BY_STEP preserve their distinct formats.
"""

import os
import re
import json
import unittest
from fastapi.testclient import TestClient

# Ensure test DB environment
os.environ["DATABASE_URL"] = "sqlite:///./test_universal.db"
os.environ["SECRET_KEY"] = "test-universal-secret-key-1234567890"

from main import app
from database import get_db, init_db, Base, engine, User, ChatSession, ChatMessage
from security import create_access_token
from ai_engine.teaching_engine import (
    PresentationVariant,
    DomainArchetype,
    infer_domain_archetype,
    generate_adaptive_diagram,
    presentation_memory
)
from ai_engine.orchestrator import feynman_engine
from ai_engine.response_validator import (
    extract_canonical_topic,
    clean_prompt_echo,
    synthesize_standard_lesson,
    synthesize_simplify_lesson,
    synthesize_analogy_lesson,
    synthesize_step_by_step_lesson
)
from routers.tutor_quiz import TutorQuizSession, TutorQuizQuestion, TutorQuizAnswer


class TestUniversalTeachingEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

        # Create test user
        db = next(get_db())
        test_user = db.query(User).filter(User.email == "universal_test@feynmantutor.com").first()
        if not test_user:
            test_user = User(
                email="universal_test@feynmantutor.com",
                hashed_password="hashed_test_password",
                name="Universal Learner",
                email_verified=True,
                xp=100
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        cls.user_id = test_user.id
        cls.token = create_access_token(data={"sub": test_user.email})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CROSS-DOMAIN SUBJECT INFERENCE & ARCHETYPE RECOGNITION
    # ─────────────────────────────────────────────────────────────────────────

    def test_cross_domain_archetype_inference(self):
        """Validates that the engine correctly infers domain archetypes across multiple disciplines."""
        test_cases = [
            ("Binary Search", DomainArchetype.COMPUTER_SCIENCE),
            ("Operating System Deadlock", DomainArchetype.COMPUTER_SCIENCE),
            ("Derivative", DomainArchetype.MATHEMATICS),
            ("Matrix Multiplication", DomainArchetype.MATHEMATICS),
            ("Newton's Second Law", DomainArchetype.PHYSICS),
            ("Thermodynamics", DomainArchetype.PHYSICS),
            ("Photosynthesis", DomainArchetype.BIOLOGY),
            ("Cellular Respiration", DomainArchetype.BIOLOGY),
            ("Chemical Bonding", DomainArchetype.CHEMISTRY),
            ("Le Chatelier's Principle", DomainArchetype.CHEMISTRY),
            ("Supply and Demand", DomainArchetype.ECONOMICS_BUSINESS),
            ("Inflation", DomainArchetype.ECONOMICS_BUSINESS),
            ("Industrial Revolution", DomainArchetype.HUMANITIES_HISTORY),
        ]
        for topic, expected_domain in test_cases:
            domain = infer_domain_archetype(topic)
            self.assertEqual(
                domain,
                expected_domain,
                f"Domain inference failed for topic '{topic}': got {domain}, expected {expected_domain}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. BOUNDED PRESENTATION MEMORY & MULTI-ANGLE VARIATION
    # ─────────────────────────────────────────────────────────────────────────

    def test_bounded_presentation_memory_rotates_strategies(self):
        """Validates that repeated queries on the same concept cycle through distinct presentation strategies."""
        topic = "Neural Networks"
        user_id = 9999

        v1 = presentation_memory.select_next_variant(user_id, topic, "STANDARD")
        presentation_memory.record_variant_used(user_id, topic, v1)

        v2 = presentation_memory.select_next_variant(user_id, topic, "STANDARD")
        presentation_memory.record_variant_used(user_id, topic, v2)

        v3 = presentation_memory.select_next_variant(user_id, topic, "STANDARD")
        presentation_memory.record_variant_used(user_id, topic, v3)

        self.assertNotEqual(v1, v2, "Second query should produce a different presentation strategy")
        self.assertNotEqual(v2, v3, "Third query should produce a different presentation strategy")

    def test_multi_angle_diagram_variation_for_same_topic(self):
        """Validates that different presentation strategies generate different, valid Mermaid diagrams."""
        topic = "Neural Networks"
        diag_arch = generate_adaptive_diagram(topic, PresentationVariant.ARCHITECTURE, "STANDARD")
        diag_train = generate_adaptive_diagram(topic, PresentationVariant.TRAINING_CYCLE, "STANDARD")
        diag_mech = generate_adaptive_diagram(topic, PresentationVariant.MECHANISM, "STANDARD")

        self.assertIn("graph", diag_arch.lower())
        self.assertIn("graph", diag_train.lower())
        self.assertIn("graph", diag_mech.lower())

        self.assertNotEqual(diag_arch, diag_train, "Architecture and Training diagrams must differ")
        self.assertNotEqual(diag_train, diag_mech, "Training and Mechanism diagrams must differ")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. CLEAN CHAT CONTRACT (NO REPETITIVE PEDAGOGICAL CLUTTER IN EXPLANATION)
    # ─────────────────────────────────────────────────────────────────────────

    def test_clean_chat_explanation_contains_no_checkpoint_clutter(self):
        """Validates that lesson explanations do not contain embedded checkpoint or recall challenge boxes."""
        topics = ["Derivative", "Photosynthesis", "Binary Search", "Newton's Second Law", "Supply and Demand"]
        
        for topic in topics:
            std = synthesize_standard_lesson(topic)
            simp = synthesize_simplify_lesson(topic)
            analogy = synthesize_analogy_lesson(topic)
            step = synthesize_step_by_step_lesson(topic)

            for mode_name, lesson in [("Standard", std), ("Simplify", simp), ("Analogy", analogy), ("StepByStep", step)]:
                exp = lesson["simple_explanation"]
                self.assertNotIn("> 🎯 **Step", exp, f"Embedded step checkpoint found in {mode_name} for {topic}")
                self.assertNotIn("> 🔍 **Analogy Checkpoint", exp, f"Embedded analogy checkpoint found in {mode_name} for {topic}")
                self.assertNotIn("> 🍲 **Analogy Checkpoint", exp, f"Embedded analogy checkpoint found in {mode_name} for {topic}")
                self.assertNotIn("Active Knowledge Checkpoint", exp, f"Checkpoint header found in {mode_name} for {topic}")
                self.assertNotIn("Feynman Active Recall Challenge", exp, f"Recall header found in {mode_name} for {topic}")
                self.assertNotIn("AI Tutor Coaching Tip", exp, f"Coaching header found in {mode_name} for {topic}")

    def test_clean_prompt_echo_strips_echoes_and_artifacts(self):
        """Validates prompt echo suppression and diagram code stripping."""
        raw_text = "Teach me step by step until I understand: Binary Search starts with dividing an array in half."
        cleaned = clean_prompt_echo(raw_text, is_explanation=True)
        self.assertFalse(cleaned.startswith("Teach me step by step"), "Prompt echo was not stripped")
        self.assertIn("Binary Search", cleaned)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. CROSS-DOMAIN FALLBACK & SYNTHESIS CONTRACTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_cross_domain_fallback_synthesis(self):
        """Validates that the fallback synthesizer produces valid contracts for Math, Physics, Bio, Chem, Econ."""
        cross_domain_prompts = [
            ("Explain Derivatives simply", "SIMPLIFY", "DERIVATIVE"),
            ("Give a real-world analogy for Photosynthesis", "ANALOGY", "PHOTOSYNTHESIS"),
            ("Teach me Newton's Second Law step by step", "STEP_BY_STEP", "NEWTON"),
            ("Explain Chemical Bonding", "STANDARD", "CHEMICAL BONDING"),
            ("Explain Supply and Demand", "STANDARD", "SUPPLY AND DEMAND"),
        ]

        for prompt, expected_mode, expected_topic in cross_domain_prompts:
            doc = feynman_engine.get_fallback_document(
                user_message=prompt,
                current_mastery=50,
                sources=[],
                session_topic=None
            )
            self.assertEqual(doc["lesson_mode"], expected_mode)
            self.assertTrue(expected_topic in doc["canonical_topic"].upper())
            self.assertTrue(len(doc["simple_explanation"]) > 50, "Explanation is too brief")
            self.assertTrue("graph " in doc["visual_intuition"] or "flowchart " in doc["visual_intuition"], "Invalid visual")

    # ─────────────────────────────────────────────────────────────────────────
    # 5. MUTUALLY EXCLUSIVE QUIZ RESULTS (ASSESSMENT LAYER ISOLATION)
    # ─────────────────────────────────────────────────────────────────────────

    def test_tutor_quiz_results_strict_mutual_exclusivity(self):
        """Validates that strong_topics and weak_topics in tutor quiz results are strictly disjoint."""
        db = next(get_db())
        quiz_id = f"test-quiz-{os.urandom(4).hex()}"
        
        quiz = TutorQuizSession(
            id=quiz_id,
            user_id=self.user_id,
            message_id="msg_123",
            session_id="sess_123",
            canonical_topic="Convolutional Neural Networks",
            lesson_mode="STANDARD",
            status="active",
            total_questions=3,
            answered_count=3,
            correct_count=2,
            score_percent=66.7,
            # Intentionally overlapping lists to simulate legacy bug
            strong_topics=json.dumps(["Convolutional Neural Networks", "Feature Extraction"]),
            weak_topics=json.dumps(["Convolutional Neural Networks", "Spatial Pooling"])
        )
        db.add(quiz)
        db.commit()

        # Call complete endpoint
        resp = self.client.post(f"/learner/tutor-quiz/{quiz_id}/complete/", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        strong = set(data["strong_topics"])
        weak = set(data["weak_topics"])

        self.assertTrue(
            strong.isdisjoint(weak),
            f"strong_topics ({strong}) and weak_topics ({weak}) must be strictly mutually exclusive!"
        )
        self.assertNotIn("Convolutional Neural Networks", strong, "Weak topic must not appear in strong concepts")
        self.assertIn("Convolutional Neural Networks", weak)
        self.assertIn("Feature Extraction", strong)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. ALL 4 PEDAGOGICAL MODES PRESERVED ACCURATELY
    # ─────────────────────────────────────────────────────────────────────────

    def test_all_four_modes_preserve_distinct_structure(self):
        """Validates that Simplify, Analogy, Step-by-Step, and Standard preserve distinct characteristics."""
        topic = "Binary Search"

        # Standard (~350-500 words across structured sections)
        std_doc = feynman_engine.get_fallback_document(f"Explain {topic}", 50, [])
        self.assertEqual(std_doc["lesson_mode"], "STANDARD")
        total_std_words = (
            len(std_doc["simple_explanation"].split()) +
            len(std_doc.get("why_it_works", "").split()) +
            len(std_doc.get("example", "").split())
        )
        self.assertTrue(total_std_words >= 150)

        # Simplify (~80-120 words ELI5 story)
        simp_doc = feynman_engine.get_fallback_document(f"Explain {topic} simply", 50, [])
        self.assertEqual(simp_doc["lesson_mode"], "SIMPLIFY")
        self.assertTrue(len(simp_doc["simple_explanation"].split()) >= 40)

        # Analogy (~120-180 words real-world metaphor)
        analogy_doc = feynman_engine.get_fallback_document(f"Give an analogy for {topic}", 50, [])
        self.assertEqual(analogy_doc["lesson_mode"], "ANALOGY")
        self.assertTrue(len(analogy_doc["simple_explanation"].split()) >= 50)

        # Step by Step (4-5 step sequence)
        step_doc = feynman_engine.get_fallback_document(f"Teach me {topic} step by step", 50, [])
        self.assertEqual(step_doc["lesson_mode"], "STEP_BY_STEP")
        self.assertIn("Step 1", step_doc["simple_explanation"])
        self.assertIn("Step 2", step_doc["simple_explanation"])
        self.assertIn("Step 3", step_doc["simple_explanation"])

    # ─────────────────────────────────────────────────────────────────────────
    # 7. CROSS-DOMAIN MULTI-TURN ROTATION VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────

    def test_cross_domain_multi_turn_rotation(self):
        """Validates that multi-turn repeat questions rotate strategies across CS, Math, Physics, Bio, Chem, Econ."""
        cross_domain_topics = [
            ("Binary Search", DomainArchetype.COMPUTER_SCIENCE),
            ("Derivative", DomainArchetype.MATHEMATICS),
            ("Newton's Second Law", DomainArchetype.PHYSICS),
            ("Photosynthesis", DomainArchetype.BIOLOGY),
            ("Chemical Bonding", DomainArchetype.CHEMISTRY),
            ("Supply and Demand", DomainArchetype.ECONOMICS_BUSINESS),
            ("Industrial Revolution", DomainArchetype.HUMANITIES_HISTORY),
        ]
        test_uid = 8888

        for topic, _ in cross_domain_topics:
            v1 = presentation_memory.select_next_variant(test_uid, topic, "STANDARD")
            presentation_memory.record_variant_used(test_uid, topic, v1)

            v2 = presentation_memory.select_next_variant(test_uid, topic, "STANDARD")
            presentation_memory.record_variant_used(test_uid, topic, v2)

            self.assertNotEqual(
                v1, v2,
                f"Multi-turn rotation failed for topic '{topic}': got same variant {v1} twice in a row"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # 8. TUTOR CHAT ENDPOINT CLEAN CONTRACT VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────

    def test_tutor_chat_endpoint_contract(self):
        """Validates that POST /tutor-chat/ returns a clean, strongly-typed tutor document."""
        db = next(get_db())
        session_id = f"test-sess-{os.urandom(4).hex()}"
        sess = ChatSession(
            id=session_id,
            user_id=self.user_id,
            title="Derivatives Study",
            mastery=50,
            has_doc=False,
            study_mode="STANDARD"
        )
        db.add(sess)
        # Add initial user message
        msg = ChatMessage(session_id=session_id, role="user", content="Explain Derivatives")
        db.add(msg)
        db.commit()

        resp = self.client.post(
            "/tutor-chat/",
            json={"session_id": session_id, "user_message": "Explain Derivatives"},
            headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("simple_explanation", data)
        self.assertIn("visual_intuition", data)
        self.assertTrue(len(data["simple_explanation"]) > 50)
        self.assertTrue("graph " in data["visual_intuition"] or "flowchart " in data["visual_intuition"])
        
        # Verify no unwanted checkpoint headers in explanation
        self.assertNotIn("Active Knowledge Checkpoint", data["simple_explanation"])
        self.assertNotIn("Feynman Active Recall Challenge", data["simple_explanation"])
        self.assertNotIn("AI Tutor Coaching Tip", data["simple_explanation"])


if __name__ == "__main__":
    unittest.main()
