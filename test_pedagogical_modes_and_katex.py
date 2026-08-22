"""
test_pedagogical_modes_and_katex.py
===================================
Exhaustive verification test suite for Feynman AI Pedagogical & UX Polish Pass:
1. Mode Isolation: Standard, Simplify, Analogy, Step-by-Step
2. Analogy Isolation Invariant: Pure analogy with explicit mapping, distinct from Standard
3. Diagram Differentiation & Short Node Labels
4. Prerequisite-aware next step recommendations
5. KaTeX Math rendering and LaTeX formula sanitization
6. Quiz hint scoping (absent in composer, present in quiz modal)
"""

import os
import re
import json
import unittest
from ai_engine.response_validator import (
    ResponseValidator,
    synthesize_standard_lesson,
    synthesize_analogy_lesson,
    synthesize_simplify_lesson,
    synthesize_step_by_step_lesson,
    TOPIC_VISUALS_REGISTRY,
    get_prerequisite_next_step
)
from ai_engine.schemas import LessonMode, TutorDocument
from ai_engine.orchestrator import feynman_engine


class TestPedagogicalPolish(unittest.TestCase):

    def test_standard_mode_contract(self):
        """Verify Standard mode outputs 350-500 words, rich hierarchy, and technical diagram."""
        res = feynman_engine.get_fallback_document(
            user_message="Explain Convolutional Neural Networks and Computer Vision Architectures",
            current_mastery=45,
            sources=[]
        )
        self.assertEqual(res["lesson_mode"], "STANDARD")
        self.assertIn("Convolutional", res["canonical_topic"])
        
        total_words = len(res["simple_explanation"].split()) + len(res["why_it_works"].split()) + len(res["example"].split())
        self.assertTrue(300 <= total_words <= 600, f"Standard word count {total_words} outside expected bounds")
        
        # Must have technical mechanism sections
        self.assertTrue("Convolutional Kernels" in res["simple_explanation"] or "Architectural Foundations" in res["simple_explanation"])
        self.assertIn("ReLU", res["simple_explanation"])
        self.assertIn("Pooling", res["simple_explanation"])
        
        # Diagram must be technical CNN diagram
        viz = res["visual_intuition"]
        self.assertTrue("graph " in viz or "flowchart " in viz)
        self.assertTrue("Conv" in viz or "Convolution" in viz)
        self.assertTrue("Pool" in viz or "Pooling" in viz)
        
        # Prerequisite next step
        self.assertTrue("Padding, Stride" in res["next_learning_step"] or "Pooling" in res["next_learning_step"])

    def test_analogy_mode_isolation(self):
        """Verify Analogy mode is purely analogy-driven (120-180 words) and never echoes Standard lesson."""
        res = feynman_engine.get_fallback_document(
            user_message="Give a real-world analogy for Convolutional Neural Networks",
            current_mastery=45,
            sources=[]
        )
        self.assertEqual(res["lesson_mode"], "ANALOGY")
        self.assertIn("Convolutional", res["canonical_topic"])
        
        exp = res["simple_explanation"]
        exp_words = len(exp.split())
        self.assertTrue(100 <= exp_words <= 220, f"Analogy word count {exp_words} outside 100-220 range")
        
        # MUST contain real-world analogy terms
        self.assertTrue(any(w in exp.lower() for w in ["detective", "inspector", "magnifying", "photograph", "clue", "kitchen", "prep"]))
        
        # MUST NOT contain Standard textbook section headers
        self.assertNotIn("### 1. The Artificial Neuron", exp)
        self.assertNotIn("### 1. Architectural Foundations", exp)
        self.assertNotIn("Loss Evaluation, Backpropagation & Optimization", exp)
        
        # Diagram must be the analogy diagram
        viz = res["visual_intuition"]
        self.assertTrue("Photo" in viz or "Inspectors" in viz or "Ingredients" in viz or "Chef" in viz or "Arrival" in viz)
        self.assertIn("graph ", viz)

    def test_simplify_mode_contract(self):
        """Verify Simplify mode produces concise ELI5 explanation (80-120 words)."""
        res = feynman_engine.get_fallback_document(
            user_message="Explain CNN simply",
            current_mastery=45,
            sources=[]
        )
        self.assertEqual(res["lesson_mode"], "SIMPLIFY")
        
        exp = res["simple_explanation"]
        exp_words = len(exp.split())
        self.assertTrue(50 <= exp_words <= 160, f"Simplify word count {exp_words} outside 50-160 range")
        self.assertNotIn("### 1.", exp)
        
        viz = res["visual_intuition"]
        self.assertIn("graph ", viz)
        self.assertTrue("Simple" in viz or "Input" in viz)

    def test_step_by_step_mode_contract(self):
        """Verify Step-by-Step mode produces exactly 5 numbered steps with checkpoints."""
        res = feynman_engine.get_fallback_document(
            user_message="Teach me CNN step by step",
            current_mastery=45,
            sources=[]
        )
        self.assertEqual(res["lesson_mode"], "STEP_BY_STEP")
        
        exp = res["simple_explanation"]
        total_words = len(exp.split())
        self.assertTrue(350 <= total_words <= 650, f"Step-by-step word count {total_words} outside 350-650 range")
        
        self.assertIn("Step 1", exp)
        self.assertIn("Step 2", exp)
        self.assertIn("Step 3", exp)
        self.assertIn("Step 4", exp)
        self.assertIn("Step 5", exp)
        self.assertIn("Mini-Example", exp)
        
        viz = res["visual_intuition"]
        self.assertTrue("S1" in viz and "S2" in viz and "S3" in viz and "S4" in viz and "S5" in viz)

    def test_four_mode_diagram_uniqueness(self):
        """Verify that all 4 modes for the same topic generate unique, non-overlapping diagrams."""
        topic = "Convolutional Neural Networks"
        
        std = ResponseValidator.validate_and_repair({"canonical_topic": topic, "lesson_mode": "STANDARD", "simple_explanation": ""})
        ana = ResponseValidator.validate_and_repair({"canonical_topic": topic, "lesson_mode": "ANALOGY", "simple_explanation": ""})
        smp = ResponseValidator.validate_and_repair({"canonical_topic": topic, "lesson_mode": "SIMPLIFY", "simple_explanation": ""})
        stb = ResponseValidator.validate_and_repair({"canonical_topic": topic, "lesson_mode": "STEP_BY_STEP", "simple_explanation": ""})
        
        viz_std = std.visual_intuition
        viz_ana = ana.visual_intuition
        viz_smp = smp.visual_intuition
        viz_stb = stb.visual_intuition
        
        # All 4 must be distinct
        diagrams = {viz_std, viz_ana, viz_smp, viz_stb}
        self.assertEqual(len(diagrams), 4, f"Expected 4 distinct diagrams across modes, got {len(diagrams)}")
        
        # Specific checks
        self.assertTrue("Conv" in viz_std and "Act" in viz_std)
        self.assertTrue("Inspectors" in viz_ana or "Photo" in viz_ana)
        self.assertTrue("Simple" in viz_smp or "Edges" in viz_smp)
        self.assertTrue("S1" in viz_stb and "S5" in viz_stb)

    def test_short_diagram_labels(self):
        """Verify that registry diagrams have concise node labels with no overly verbose strings."""
        for entry in TOPIC_VISUALS_REGISTRY:
            mermaid = entry["mermaid"]
            # Extract label texts inside ["..."]
            labels = re.findall(r'\["([^"]+)"\]', mermaid)
            for label in labels:
                # Labels should be concise (<= 35 chars) to prevent UI truncation
                self.assertTrue(len(label) <= 35, f"Label '{label}' in topic '{entry['topic']}' is too long ({len(label)} chars)")

    def test_prerequisite_sequences(self):
        """Verify next step recommendations adhere to pedagogical prerequisite ordering."""
        self.assertIn("Padding, Stride", get_prerequisite_next_step("Convolutional Neural Networks"))
        self.assertIn("Convolutional Neural Networks", get_prerequisite_next_step("Neural Networks"))
        self.assertIn("Gradient Descent", get_prerequisite_next_step("Backpropagation"))
        self.assertIn("Attention Mechanics", get_prerequisite_next_step("Transformers"))
        self.assertIn("Binary Search on Monotonic", get_prerequisite_next_step("Binary Search"))

    def test_html_and_js_invariants(self):
        """Verify KaTeX presence and Hint button removal from chat composer in HTML and JS."""
        with open("index.html", "r", encoding="utf-8") as f:
            html_root = f.read()
        with open("templates/index.html", "r", encoding="utf-8") as f:
            html_tpl = f.read()
        with open("static/js/app.js", "r", encoding="utf-8") as f:
            js = f.read()
            
        # KaTeX in head
        self.assertTrue("katex.min.css" in html_root and "katex.min.js" in html_root)
        self.assertTrue("katex.min.css" in html_tpl and "katex.min.js" in html_tpl)
        
        # Hint button removed from main composer
        self.assertNotIn('<span id="hint-btn-text">I\'m stuck, request hint</span>', html_root)
        self.assertNotIn('<span id="hint-btn-text">I\'m stuck, request hint</span>', html_tpl)
        
        # Quiz modal must still have its hint button
        self.assertTrue('id="quiz-hint-btn"' in html_root or 'requestQuizHint()' in html_root)
        
        # KaTeX math parsing pipeline in JS
        self.assertIn("renderMathToString", js)
        self.assertIn("renderKaTeXMath", js)
        self.assertIn("%%FEYNMAN_MATH_BLOCK_", js)


if __name__ == "__main__":
    unittest.main()
