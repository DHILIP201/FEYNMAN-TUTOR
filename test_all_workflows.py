"""Comprehensive programmatic integration test suite to verify every user workflow in Feynman AI Tutor backend."""
import sys
import os
import shutil
import time
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, User, ChatSession, ChatMessage
import json

client = TestClient(app)
TEST_EMAIL = "e2e_acceptance_test@domain.com"
TEST_PASS = "SecretPassword123!"
TEST_NAME = "E2E Acceptance Test Student"
TEST_SESSION_ID = "e2e-acceptance-session-id"

print("====================================================")
print("STARTING PROGRAMMATIC ACCEPTANCE TESTS (BACKEND)")
print("====================================================")

# Clean up existing test user if present
db = SessionLocal()
try:
    existing_user = db.query(User).filter(User.email == TEST_EMAIL).first()
    if existing_user:
        db.delete(existing_user)
        db.commit()
        print("[SETUP] Cleaned up existing test user.")
finally:
    db.close()

# ----------------------------------------------------
# 1. AUTHENTICATION WORKFLOWS
# ----------------------------------------------------
print("\n--- 1. Testing Authentication ---")

# A. Register
print("[TEST] Registering new user...")
r_reg = client.post('/auth/signup/', json={
    "name": TEST_NAME,
    "email": TEST_EMAIL,
    "password": TEST_PASS
})
assert r_reg.status_code == 200, f"Register failed: {r_reg.text}"
data_reg = r_reg.json()
assert "access_token" in data_reg, "No access token in registration response"
print("  [OK] Registration: PASS (Token received)")

# B. Duplicate Register Attempt (Should fail with 400)
print("[TEST] Verifying Duplicate Registration Guard...")
r_dup = client.post('/auth/signup/', json={
    "name": TEST_NAME,
    "email": TEST_EMAIL,
    "password": TEST_PASS
})
assert r_dup.status_code == 400, f"Duplicate signup did not return 400: {r_dup.text}"
print("  [OK] Duplicate Registration Guard: PASS (400 Email already registered)")

# C. Wrong Password Attempt (Should fail with 401)
print("[TEST] Verifying Wrong Password Guard...")
r_bad_pass = client.post('/auth/login/', json={
    "email": TEST_EMAIL,
    "password": "WrongPassword999!"
})
assert r_bad_pass.status_code == 401, f"Wrong password did not return 401: {r_bad_pass.text}"
print("  [OK] Wrong Password Guard: PASS (401 Unauthorized)")

# D. Login with correct password
print("[TEST] Logging in with correct credentials...")
r_login = client.post('/auth/login/', json={
    "email": TEST_EMAIL,
    "password": TEST_PASS
})
assert r_login.status_code == 200, f"Login failed: {r_login.text}"
data_login = r_login.json()
assert "access_token" in data_login, "No access token in login response"
token = data_login["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("  [OK] Login: PASS")

# C. Guest Mode
print("[TEST] Verifying Guest Mode pre-seed...")
db = SessionLocal()
try:
    guest_user = db.query(User).filter(User.email == "guest@feynmantutor.local").first()
    assert guest_user is not None, "Guest user is not pre-seeded in the database"
    print("  [OK] Guest Mode Pre-seed: PASS")
finally:
    db.close()

# ----------------------------------------------------
# 2. PDF & RAG WORKFLOWS
# ----------------------------------------------------
print("\n--- 2. Testing PDF Upload & RAG Ingestion ---")

# Verify test_study_material.pdf exists
assert os.path.exists("test_study_material.pdf"), "test_study_material.pdf is missing from root"

# Upload PDF
print("[TEST] Ingesting test PDF...")
with open("test_study_material.pdf", "rb") as f:
    r_upload = client.post(
        "/upload-document/",
        data={"session_id": TEST_SESSION_ID},
        files={"file": ("test_study_material.pdf", f, "application/pdf")},
        headers=headers
    )

assert r_upload.status_code == 200, f"PDF upload failed: {r_upload.text}"
data_upload = r_upload.json()
assert "pages" in data_upload, "Pages missing in upload stats"
assert "chunks" in data_upload, "Chunks missing in upload stats"
assert data_upload["status"] == "Indexed successfully", "Status is not successfully indexed"
print(f"  [OK] Ingestion: PASS (Pages={data_upload['pages']}, Chunks={data_upload['chunks']})")

# Verify persistence of document flag in DB
db = SessionLocal()
try:
    sess = db.query(ChatSession).filter(ChatSession.id == TEST_SESSION_ID).first()
    assert sess is not None, "Chat session was not created in DB"
    assert sess.has_doc is True, "Session has_doc flag was not saved as True in DB"
    print("  [OK] Database Persistence: PASS (has_doc is True)")
finally:
    db.close()

# ----------------------------------------------------
# 3. AI PIPELINE & CITATIONS WORKFLOW
# ----------------------------------------------------
print("\n--- 3. Testing AI Chat Pipeline & RAG Citations ---")

print("[TEST] Sending message 'Explain recursion' (with retries for 503)...")
r_chat = None
for attempt in range(4):
    r_chat = client.post(
        "/tutor-chat/",
        json={
            "session_id": TEST_SESSION_ID,
            "user_message": "Explain recursion tree stack bounds.",
            "image_base64": None,
            "image_mime": None
        },
        headers=headers
    )
    if r_chat.status_code == 200:
        break
    elif r_chat.status_code == 500 and "503" in r_chat.text:
        print(f"  [WARN] Gemini returned 503 (high demand). Retrying in {5 + attempt * 5} seconds...")
        time.sleep(5 + attempt * 5)
    else:
        # Other type of error, fail fast
        break

assert r_chat.status_code == 200, f"Chat failed after retries: {r_chat.text}"
data_chat = r_chat.json()

# Verify response contract contains all required fields
required_keys = [
    "simple_explanation", "why_it_works", "visual_intuition", "example",
    "common_mistake", "mini_quiz", "reflection_prompt", "coach_recommendation",
    "next_learning_step", "estimated_study_time", "cognitive_trace", "mastery_score",
    "sources"
]

for key in required_keys:
    assert key in data_chat, f"Response missing contract key: '{key}'"

print("  [OK] AI Structured Contract: PASS")
print(f"  [OK] Cognitive Trace: {data_chat['cognitive_trace'][:100]}...")
print(f"  [OK] Mini Quiz: {data_chat['mini_quiz'][:100]}...")
print(f"  [OK] Mastery Score Updated: {data_chat['mastery_score']}%")

# Verify Citations (Sources should have at least one block if context was retrieved)
sources = data_chat["sources"]
assert len(sources) > 0, "No sources cited in RAG response!"
assert sources[0]["filename"] == "test_study_material.pdf", f"Source filename mismatch: {sources[0]['filename']}"
print(f"  [OK] RAG Citations: PASS (Source file cited: '{sources[0]['filename']}', Page: {sources[0]['page']})")

# ----------------------------------------------------
# 4. DASHBOARD STATS WORKFLOW
# ----------------------------------------------------
print("\n--- 4. Testing Dashboard Statistics & Timeline ---")

r_stats = client.get("/users/stats/", headers=headers)
assert r_stats.status_code == 200, f"Stats fetch failed: {r_stats.text}"
data_stats = r_stats.json()

assert data_stats["current_streak"] >= 1, f"Streak is missing or zero: {data_stats['current_streak']}"
assert data_stats["xp"] > 0, f"XP is zero: {data_stats['xp']}"
assert len(data_stats["timeline"]) > 0, "Timeline has no events"

print(f"  [OK] Current Streak: PASS ({data_stats['current_streak']} Days)")
print(f"  [OK] Total XP: PASS ({data_stats['xp']} XP)")
print(f"  [OK] Timeline Events: PASS ({len(data_stats['timeline'])} events logged)")

# ----------------------------------------------------
# 6. REGRESSION TESTS: CANONICAL TOPIC, 4 MODES & DIAGRAM PERSISTENCE
# ----------------------------------------------------
print("\n--- 6. Testing Canonical Topics, 4 Modes & Diagrams ---")

from ai_engine.response_validator import extract_canonical_topic, ResponseValidator
from ai_engine.orchestrator import feynman_engine
from ai_engine.schemas import LessonMode

# 6A: Canonical Topic Extraction Test
print("[TEST] Verifying Canonical Topic Extractor...")
test_prompts = [
    ("Teach me neural networks step by step", "Neural Networks"),
    ("Explain this concept even simpler", "Core Concept"),
    ("Give a real world analogy for binary search", "Binary Search"),
    ("Tell me about advanced applications of transformers", "Transformers"),
    ("Explain recursion tree stack bounds", "Recursion Tree Stack Bounds")
]

for raw_p, expected_t in test_prompts:
    extracted = extract_canonical_topic(raw_p)
    assert extracted == expected_t, f"Topic extraction failed for '{raw_p}': got '{extracted}', expected '{expected_t}'"
print("  [OK] Canonical Topic Extraction: PASS (100% clean)")

# 6B: Verify All 4 Lesson Modes & Mode-Specific Diagrams
print("[TEST] Verifying 4 Lesson Modes & Mode-Specific Diagrams...")

# 1. Standard Mode
doc_std = feynman_engine.get_fallback_document("Explain neural networks", 0, [])
assert doc_std["lesson_mode"] in (LessonMode.STANDARD, "STANDARD"), f"Expected STANDARD mode, got {doc_std['lesson_mode']}"
assert "weights" in doc_std["visual_intuition"].lower() or "input" in doc_std["visual_intuition"].lower(), "Standard diagram missing neural network mechanics"
assert "teach me" not in doc_std["reflection_prompt"].lower(), "Reflection prompt leaked prompt string"
print("  [OK] Mode 1: STANDARD (Diagram: Mechanism Flowchart) -> PASS")

# 2. Simplify Mode
doc_simp = feynman_engine.get_fallback_document("Explain this concept even simpler", 0, [])
assert doc_simp["lesson_mode"] in (LessonMode.SIMPLIFY, "SIMPLIFY"), f"Expected SIMPLIFY mode, got {doc_simp['lesson_mode']}"
assert "graph " in doc_simp["visual_intuition"] or doc_simp["visual_intuition"] == "", "Simplify diagram invalid"
assert "explain this concept" not in doc_simp["reflection_prompt"].lower(), "Reflection prompt leaked prompt string"
print("  [OK] Mode 2: SIMPLIFY (Diagram: Minimal Pipeline) -> PASS")

# 3. Analogy Mode
doc_analogy = feynman_engine.get_fallback_document("Give a real world analogy", 0, [])
assert doc_analogy["lesson_mode"] in (LessonMode.ANALOGY, "ANALOGY"), f"Expected ANALOGY mode, got {doc_analogy['lesson_mode']}"
assert "graph " in doc_analogy["visual_intuition"] or doc_analogy["visual_intuition"] == "", "Analogy diagram invalid"
assert "chef" in doc_analogy["simple_explanation"].lower() or "kitchen" in doc_analogy["simple_explanation"].lower(), "Analogy explanation missing concrete story"
print("  [OK] Mode 3: ANALOGY (Diagram: Analogy Workflow) -> PASS")

# 4. Step-by-Step Mode
doc_step = feynman_engine.get_fallback_document("Teach me neural networks step by step", 0, [])
assert doc_step["lesson_mode"] in (LessonMode.STEP_BY_STEP, "STEP_BY_STEP"), f"Expected STEP_BY_STEP mode, got {doc_step['lesson_mode']}"
assert "### Step 1" in doc_step["simple_explanation"], "Step 1 missing from Step-by-Step explanation"
assert "### Step 2" in doc_step["simple_explanation"], "Step 2 missing from Step-by-Step explanation"
assert "### Step 3" in doc_step["simple_explanation"], "Step 3 missing from Step-by-Step explanation"
assert "### Step 4" in doc_step["simple_explanation"], "Step 4 missing from Step-by-Step explanation"
assert "Checkpoint" in doc_step["simple_explanation"], "Checkpoints missing from Step-by-Step explanation"
assert "S1[" in doc_step["visual_intuition"] and "S2[" in doc_step["visual_intuition"], "Step-by-step diagram not sequential"
print("  [OK] Mode 4: STEP_BY_STEP (4 Steps + Checkpoints + Step Diagram) -> PASS")

# 6C: Verify Sequential Multi-Turn Message Integrity
print("[TEST] Verifying Sequential Multi-Turn Integrity...")
turn_1 = feynman_engine.get_fallback_document("Explain neural networks", 0, [])
turn_2 = feynman_engine.get_fallback_document("Explain this concept even simpler", 10, [])
turn_3 = feynman_engine.get_fallback_document("Give a real world analogy", 20, [])
turn_4 = feynman_engine.get_fallback_document("Teach me neural networks step by step", 30, [])

assert turn_1["lesson_mode"] in (LessonMode.STANDARD, "STANDARD") and turn_1["visual_intuition"] != ""
assert turn_2["lesson_mode"] in (LessonMode.SIMPLIFY, "SIMPLIFY")
assert turn_3["lesson_mode"] in (LessonMode.ANALOGY, "ANALOGY")
assert turn_4["lesson_mode"] in (LessonMode.STEP_BY_STEP, "STEP_BY_STEP") and "Step 1" in turn_4["simple_explanation"]

# Verify no prompt pollution in active recall or next steps
for turn in [turn_1, turn_2, turn_3, turn_4]:
    assert not any(bad in turn["reflection_prompt"].lower() for bad in ["teach me", "explain this concept even simpler", "give a real world analogy"])
    assert not any(bad in turn["next_learning_step"].lower() for bad in ["teach me", "explain this concept even simpler", "give a real world analogy"])

print("  [OK] Multi-Turn Message State Integrity & Zero Prompt Leakage: PASS")

print("\n====================================================")
print("ALL PROGRAMMATIC WORKFLOW TESTS COMPLETED SUCCESSFULLY!")
print("====================================================")
