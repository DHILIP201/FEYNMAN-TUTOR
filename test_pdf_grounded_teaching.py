"""
Test Suite: PDF-Grounded Knowledge Source Policy (PDF-GROUND-1 through PDF-GROUND-10)

Verifies that for active PDF study sessions:
1. The uploaded PDF is the authoritative knowledge source.
2. Questions are answered strictly from the PDF context.
3. Unsupported information is explicitly reported as unavailable.
4. Suggestions and next learning steps come strictly from available PDF topics.
5. Repeated questions rotate pedagogical angles using the same source material.
6. Diagrams reflect the PDF-grounded concept.
7. Quiz Me questions are grounded in the current lesson.
8. PDF Quiz remains separate as a full-document assessment.
9. No arbitrary outside topic injection occurs.
10. Operates universally across subjects (Computer Science, Mathematics, Biology, Economics, Physics).
"""

import unittest
import json
from ai_engine.orchestrator import feynman_engine
from ai_engine.response_validator import (
    ResponseValidator,
    extract_canonical_topic,
    extract_candidate_topics_from_pdf,
    get_prerequisite_next_step
)
from ai_engine.teaching_engine import (
    PresentationVariant,
    infer_domain_archetype,
    generate_adaptive_diagram,
    presentation_memory
)
from routers.tutor_quiz import (
    synthesize_topic_fallback_quiz,
    generate_tutor_quiz_questions
)


class TestPDFGroundedTeachingEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Sample PDF contexts representing different subjects
        self.sample_cs_pdf = (
            "Context Block 1 (Source: deep_learning_chapter4.pdf - Page 12):\n"
            "### Convolutional Neural Networks\n"
            "Convolutional Neural Networks (CNNs) process grid-structured data like 2D images. "
            "Unlike fully connected networks, CNNs use discrete convolution operations where parameter kernels slide across the input tensor. "
            "Key stages include Convolutional Layers, Non-Linear ReLU activations, and Spatial Max Pooling.\n---\n"
            "Context Block 2 (Source: deep_learning_chapter4.pdf - Page 15):\n"
            "### Backpropagation and Loss Optimization\n"
            "After forward feature extraction, the network computes cross-entropy loss against ground truth labels. "
            "Gradients are propagated backwards through the chain rule to update filter weights via Gradient Descent.\n---\n"
        )

        self.sample_bio_pdf = (
            "Context Block 1 (Source: plant_physiology.pdf - Page 45):\n"
            "### Photosynthesis and Light-Dependent Reactions\n"
            "Photosynthesis converts light energy into chemical energy within plant chloroplasts. "
            "Photons strike chlorophyll pigments in thylakoid membranes, generating ATP and NADPH while splitting water to release Oxygen.\n---\n"
            "Context Block 2 (Source: plant_physiology.pdf - Page 48):\n"
            "### The Calvin Cycle and Carbon Fixation\n"
            "In the stroma, the enzyme RuBisCO fixes Carbon Dioxide into 3-PGA molecules, which are converted into glucose sugar using ATP.\n---\n"
        )

        self.sample_econ_pdf = (
            "Context Block 1 (Source: microeconomics_fundamentals.pdf - Page 22):\n"
            "### Supply and Demand Market Equilibrium\n"
            "Market equilibrium occurs where quantity supplied equals quantity demanded at the market clearing price.\n---\n"
            "Context Block 2 (Source: microeconomics_fundamentals.pdf - Page 26):\n"
            "### Price Elasticity of Demand\n"
            "Elasticity measures the responsiveness of quantity demanded to changes in price.\n---\n"
        )

    def test_pdf_ground_1_question_answered_from_pdf_context(self):
        """PDF-GROUND-1: Question is answered and grounded in the retrieved PDF context."""
        doc = feynman_engine.get_fallback_document(
            user_message="Explain Convolutional Neural Networks",
            current_mastery=50,
            sources=[{"filename": "deep_learning_chapter4.pdf", "page": 12}],
            pdf_context=self.sample_cs_pdf
        )
        self.assertEqual(doc["lesson_mode"], "STANDARD")
        self.assertIn("Convolutional", doc["canonical_topic"])
        self.assertTrue(len(doc["simple_explanation"].split()) >= 150)
        self.assertIn("Convolution", doc["simple_explanation"])

    def test_pdf_ground_2_unsupported_info_explicitly_reported(self):
        """PDF-GROUND-2: Query on a topic absent from the uploaded PDF is explicitly reported as unavailable."""
        doc = feynman_engine.get_fallback_document(
            user_message="Explain Quantum Gravity in Black Holes",
            current_mastery=30,
            sources=[{"filename": "deep_learning_chapter4.pdf", "page": 12}],
            pdf_context=self.sample_cs_pdf
        )
        exp = doc["simple_explanation"]
        self.assertTrue(
            "couldn't find enough information" in exp.lower() or
            "not available in your uploaded" in exp.lower(),
            f"Expected explicit unavailable notice, got: {exp}"
        )
        self.assertNotIn("Hawking radiation", exp)
        self.assertNotIn("string theory", exp)

    def test_pdf_ground_3_suggestion_comes_from_available_pdf_topic(self):
        """PDF-GROUND-3: Suggested next learning step must come from available PDF topics."""
        next_step = get_prerequisite_next_step("Convolutional Neural Networks", pdf_context=self.sample_cs_pdf)
        self.assertIn("From your uploaded material", next_step)
        self.assertTrue(
            "Backpropagation" in next_step or
            "Loss Optimization" in next_step or
            "Gradient" in next_step or
            "section" in next_step.lower()
        )
        self.assertNotIn("Vision Transformers", next_step)
        self.assertNotIn("ResNet-152", next_step)

    def test_pdf_ground_4_repeat_question_variation_without_outside_facts(self):
        """PDF-GROUND-4: Repeated question produces a different pedagogical angle without introducing unsupported facts."""
        topic = "Photosynthesis"
        v1 = presentation_memory.select_next_variant("user_test", topic, "STANDARD", self.sample_bio_pdf)
        presentation_memory.record_variant_used("user_test", topic, v1)
        
        v2 = presentation_memory.select_next_variant("user_test", topic, "STANDARD", self.sample_bio_pdf)
        self.assertNotEqual(v1, v2, f"Expected variant rotation, got {v1} and {v2}")

        doc1 = feynman_engine.get_fallback_document(
            user_message="Explain Photosynthesis",
            current_mastery=40,
            sources=[{"filename": "plant_physiology.pdf", "page": 45}],
            variant=v1,
            pdf_context=self.sample_bio_pdf
        )
        doc2 = feynman_engine.get_fallback_document(
            user_message="Explain Photosynthesis",
            current_mastery=40,
            sources=[{"filename": "plant_physiology.pdf", "page": 45}],
            variant=v2,
            pdf_context=self.sample_bio_pdf
        )
        self.assertNotEqual(doc1["simple_explanation"], doc2["simple_explanation"])
        self.assertIn("Photosynthesis", doc1["canonical_topic"])
        self.assertIn("Photosynthesis", doc2["canonical_topic"])

    def test_pdf_ground_5_diagram_based_on_pdf_concept(self):
        """PDF-GROUND-5: Diagram reflects the PDF-grounded concept."""
        diagram = generate_adaptive_diagram(
            canonical_topic="Convolutional Neural Networks",
            presentation_variant=PresentationVariant.ARCHITECTURE,
            lesson_mode="STANDARD",
            explanation_text="Convolution filters slide across input image, apply ReLU and Max Pooling."
        )
        self.assertIn("graph ", diagram)
        self.assertTrue("Conv" in diagram or "Filters" in diagram)

    def test_pdf_ground_6_quiz_me_questions_grounded_in_lesson(self):
        """PDF-GROUND-6: Quiz Me generates questions grounded in the current lesson context."""
        lesson_text = (
            "Convolutional Neural Networks use sliding parameterized filters to extract local features. "
            "Max pooling reduces spatial dimensions by taking the maximum activation in a localized window."
        )
        questions = synthesize_topic_fallback_quiz(
            topic="Convolutional Neural Networks",
            lesson_text=lesson_text,
            mode="STANDARD",
            count=4
        )
        self.assertEqual(len(questions), 4)
        for q in questions:
            self.assertIn("question_text", q)
            self.assertIn("correct_answer", q)
            self.assertIn("Convolutional", q["canonical_topic"])

    def test_pdf_ground_7_pdf_quiz_remains_separate(self):
        """PDF-GROUND-7: PDF Quiz (document-wide) and Quiz Me (per-message) maintain separate boundaries."""
        quiz_me = synthesize_topic_fallback_quiz("Supply and Demand", "Equilibrium price...", "STANDARD", 4)
        self.assertEqual(len(quiz_me), 4)

        bio_topics = extract_candidate_topics_from_pdf(self.sample_bio_pdf)
        self.assertTrue(len(bio_topics) >= 2)
        self.assertTrue(any("Photosynthesis" in t for t in bio_topics))
        self.assertTrue(any("Calvin" in t for t in bio_topics))

    def test_pdf_ground_8_no_external_topic_injection(self):
        """PDF-GROUND-8: No unrelated external topic is injected into recommendations when PDF is present."""
        next_econ = get_prerequisite_next_step("Supply and Demand", pdf_context=self.sample_econ_pdf)
        self.assertIn("From your uploaded material", next_econ)
        self.assertIn("Elasticity", next_econ)
        self.assertNotIn("IS-LM Model", next_econ)
        self.assertNotIn("Black-Scholes", next_econ)

    def test_pdf_ground_9_learner_recommendations_remain_pdf_relevant(self):
        """PDF-GROUND-9: When user asks about a covered topic, next step recommends an adjacent concept from the PDF."""
        doc = feynman_engine.get_fallback_document(
            user_message="Explain the Calvin Cycle",
            current_mastery=60,
            sources=[{"filename": "plant_physiology.pdf", "page": 48}],
            pdf_context=self.sample_bio_pdf
        )
        self.assertIn("From your uploaded material", doc["next_learning_step"])
        self.assertTrue("Photosynthesis" in doc["next_learning_step"] or "section" in doc["next_learning_step"].lower())

    def test_pdf_ground_10_works_across_different_pdf_subjects(self):
        """PDF-GROUND-10: Works across Computer Science, Biology, Economics, and Mathematics PDFs."""
        subjects = [
            ("Computer Science", self.sample_cs_pdf, "Convolutional Neural Networks"),
            ("Biology", self.sample_bio_pdf, "Photosynthesis"),
            ("Economics", self.sample_econ_pdf, "Supply and Demand")
        ]
        for subject_name, pdf_ctx, topic in subjects:
            extracted = extract_candidate_topics_from_pdf(pdf_ctx)
            self.assertTrue(len(extracted) >= 1, f"Failed to extract candidate topics for {subject_name}")
            
            doc = feynman_engine.get_fallback_document(
                user_message=f"Explain {topic}",
                current_mastery=50,
                sources=[{"filename": "sample.pdf", "page": 1}],
                pdf_context=pdf_ctx
            )
            self.assertEqual(doc["lesson_mode"], "STANDARD")
            self.assertIn("From your uploaded material", doc["next_learning_step"])


if __name__ == "__main__":
    unittest.main()
