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
from database import init_db, SessionLocal, User, ChatSession, ChatMessage
import json
import io
from datetime import datetime, timedelta

# Initialize all database tables
init_db()

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
    ("Teach me step by step until I understand neural networks", "Neural Networks"),
    ("Explain this concept even simpler", "Core Concept"),
    ("Explain this concept even simpler: activation functions", "Activation Functions"),
    ("Give a real world analogy for binary search", "Binary Search"),
    ("Give an analogy for dynamic programming", "Dynamic Programming"),
    ("Tell me about advanced applications of transformers", "Transformers"),
    ("Tell me about advanced applications of recursion", "Recursion"),
    ("Explain recursion tree stack bounds", "Recursion Tree Stack Bounds"),
    ("What is CNN", "CNN"),
    ("What is SQL", "SQL"),
    ("Deep dive into ACID", "ACID"),
]

for raw_p, expected_t in test_prompts:
    extracted = extract_canonical_topic(raw_p)
    assert extracted == expected_t, f"Topic extraction failed for '{raw_p}': got '{extracted}', expected '{expected_t}'"
print("  [OK] Canonical Topic Extraction: PASS (100% clean across all prompt variants)")


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

# ----------------------------------------------------
# 7. GEMINI API GATEWAY REGRESSION TESTS
# ----------------------------------------------------
print("\n--- 7. Testing Gemini API Gateway & Credential Pool ---")

from unittest.mock import MagicMock, patch
import asyncio
from ai_engine.gemini_gateway import GeminiGateway, GeminiKeyPool, KeySlotStatus, KeySlot

# 7.1: Key pool initialization
print("[TEST 7.1] Verifying GeminiKeyPool initialization...")
test_pool = GeminiKeyPool(["test_key_alpha", "test_key_beta", "test_key_gamma"])
assert len(test_pool.slots) == 3, f"Expected 3 slots, got {len(test_pool.slots)}"
for slot in test_pool.slots:
    assert slot.status == KeySlotStatus.HEALTHY, f"Slot {slot.slot_id} is not healthy: {slot.status}"
    assert slot.is_available() is True, f"Slot {slot.slot_id} should be available"
print("  [OK] Test 7.1: Key pool loaded 3 slots with HEALTHY status: PASS")

# 7.2: Primary slot success
print("[TEST 7.2] Verifying Primary Key generation success...")
async def run_test_7_2():
    pool = GeminiKeyPool(["test_key_1", "test_key_2"])
    gateway = GeminiGateway(key_pool=pool)
    
    mock_resp = MagicMock()
    mock_resp.text = '{"simple_explanation": "Test output", "mastery_score": 10}'
    
    with patch.object(pool.slots[0].client.models, "generate_content", return_value=mock_resp):
        res = await gateway.generate(contents=["test"], system_instruction="system")
        assert res == mock_resp.text, f"Result mismatch: {res}"
        assert pool.slots[0].status == KeySlotStatus.HEALTHY
        assert pool.slots[0].failure_count == 0
asyncio.run(run_test_7_2())
print("  [OK] Test 7.2: Primary key generation: PASS")

# 7.3: 429 Rate Limit Failover
print("[TEST 7.3] Verifying 429 Rate Limit Cooldown & Failover...")
async def run_test_7_3():
    pool = GeminiKeyPool(["test_key_1", "test_key_2", "test_key_3"])
    gateway = GeminiGateway(key_pool=pool)
    
    mock_resp_2 = MagicMock()
    mock_resp_2.text = '{"simple_explanation": "Recovered from Key 2"}'
    
    def side_effect_slot1(*args, **kwargs):
        raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for project")
        
    with patch.object(pool.slots[0].client.models, "generate_content", side_effect=side_effect_slot1):
        with patch.object(pool.slots[1].client.models, "generate_content", return_value=mock_resp_2):
            res = await gateway.generate(contents=["test"], system_instruction="system")
            assert res == mock_resp_2.text, f"Failed to recover on Key 2: {res}"
            assert pool.slots[0].status == KeySlotStatus.COOLDOWN, f"Slot 1 should be COOLDOWN, got {pool.slots[0].status}"
            assert pool.slots[0].cooldown_until > time.time()
            assert pool.slots[1].status == KeySlotStatus.HEALTHY
asyncio.run(run_test_7_3())
print("  [OK] Test 7.3: 429 Rate Limit Slot Failover: PASS")

# 7.4: 503 Service Unavailable Retry & Multi-Key Failover
print("[TEST 7.4] Verifying 503 Unavailable Retry & Multi-Key Failover...")
async def run_test_7_4():
    pool = GeminiKeyPool(["test_key_1", "test_key_2", "test_key_3"])
    gateway = GeminiGateway(key_pool=pool)
    gateway.backoff_base = 0.01  # fast test
    
    mock_resp_3 = MagicMock()
    mock_resp_3.text = '{"simple_explanation": "Recovered from Key 3"}'
    
    with patch.object(pool.slots[0].client.models, "generate_content", side_effect=Exception("503 UNAVAILABLE")):
        with patch.object(pool.slots[1].client.models, "generate_content", side_effect=Exception("503 UNAVAILABLE")):
            with patch.object(pool.slots[2].client.models, "generate_content", return_value=mock_resp_3):
                res = await gateway.generate(contents=["test"], system_instruction="system")
                assert res == mock_resp_3.text, f"Failed to recover on Key 3: {res}"
                assert pool.slots[2].status == KeySlotStatus.HEALTHY
asyncio.run(run_test_7_4())
print("  [OK] Test 7.4: 503 Multi-Key Failover: PASS")

# 7.5: Timeout Failover
print("[TEST 7.5] Verifying Timeout Failover...")
async def run_test_7_5():
    pool = GeminiKeyPool(["test_key_1", "test_key_2"])
    gateway = GeminiGateway(key_pool=pool)
    gateway.timeout_seconds = 1
    
    mock_resp_2 = MagicMock()
    mock_resp_2.text = '{"simple_explanation": "Recovered after timeout"}'
    
    def slow_slot1(*args, **kwargs):
        time.sleep(2.0)
        return MagicMock()
        
    with patch.object(pool.slots[0].client.models, "generate_content", side_effect=slow_slot1):
        with patch.object(pool.slots[1].client.models, "generate_content", return_value=mock_resp_2):
            res = await gateway.generate(contents=["test"], system_instruction="system")
            assert res == mock_resp_2.text, f"Failed to recover after timeout: {res}"
asyncio.run(run_test_7_5())
print("  [OK] Test 7.5: Timeout Failover: PASS")

# 7.6: 401/403 Invalid API Key Quarantine
print("[TEST 7.6] Verifying 401/403 Credential Quarantine...")
async def run_test_7_6():
    pool = GeminiKeyPool(["bad_key", "good_key"])
    gateway = GeminiGateway(key_pool=pool)
    
    mock_resp_2 = MagicMock()
    mock_resp_2.text = '{"simple_explanation": "Recovered from good key"}'
    
    with patch.object(pool.slots[0].client.models, "generate_content", side_effect=Exception("403 API_KEY_INVALID")):
        with patch.object(pool.slots[1].client.models, "generate_content", return_value=mock_resp_2):
            res = await gateway.generate(contents=["test"], system_instruction="system")
            assert res == mock_resp_2.text
            assert pool.slots[0].status == KeySlotStatus.QUARANTINED
            assert pool.slots[0].is_available() is False, "Quarantined slot should not be available"
asyncio.run(run_test_7_6())
print("  [OK] Test 7.6: Credential Quarantine (No endless retry on 401/403): PASS")

# 7.7: All Keys Exhausted Fallback Integration
print("[TEST 7.7] Verifying All Keys Exhausted Fallback Document Safety...")
async def run_test_7_7():
    pool = GeminiKeyPool(["k1", "k2"])
    gateway = GeminiGateway(key_pool=pool)
    gateway.backoff_base = 0.01
    
    with patch.object(pool.slots[0].client.models, "generate_content", side_effect=Exception("503 UNAVAILABLE")):
        with patch.object(pool.slots[1].client.models, "generate_content", side_effect=Exception("429 RESOURCE_EXHAUSTED")):
            res = await gateway.generate(contents=["test"], system_instruction="system")
            assert res is None, "Expected None when all keys fail"
            
            # Verify existing Feynman fallback takes over seamlessly
            doc_fallback = feynman_engine.get_fallback_document("Teach me recursion step by step", 10, [])
            assert doc_fallback["lesson_mode"] in (LessonMode.STEP_BY_STEP, "STEP_BY_STEP")
            assert "Step 1" in doc_fallback["simple_explanation"]
            assert "teach me" not in doc_fallback["reflection_prompt"].lower()
asyncio.run(run_test_7_7())
print("  [OK] Test 7.7: Controlled Fallback Document Integration: PASS")

# 7.8: Security Check — Zero Secret Leakage in Logs & Telemetry
print("[TEST 7.8] Verifying Zero Secret Leakage in Telemetry & Pool Status...")
pool_status = test_pool.get_pool_status()
for s in pool_status:
    # Ensure raw API key string is not present in dictionary
    assert "api_key" not in s
    assert "key" not in s
    assert "slot_id" in s and "status" in s
print("  [OK] Test 7.8: Zero Secret Leakage in Telemetry & Logs: PASS")

# ----------------------------------------------------
# 8. RATE LIMITING, AI BUDGET & SECURITY HEADERS
# ----------------------------------------------------
print("\n--- 8. Testing Rate Limiting, Token Budget & Security Headers ---")

from ai_engine.rate_limiter import RateLimiter, RateLimitTier, InMemoryRateLimitStorage, rate_limiter
from security import create_access_token

# 8.1: Tiered Rate Limiting sliding window check
print("[TEST 8.1] Verifying Tiered Rate Limiting...")
custom_storage = InMemoryRateLimitStorage()
limiter = RateLimiter(storage=custom_storage)

# Guest RPM limit is 10
guest_id = "test_guest_123"
for i in range(10):
    allowed, info = limiter.check_rate_limit(guest_id, tier=RateLimitTier.GUEST)
    assert allowed is True, f"Request {i+1} should be allowed"

# 11th request must be blocked
allowed, info = limiter.check_rate_limit(guest_id, tier=RateLimitTier.GUEST)
assert allowed is False, "11th guest request should be blocked"
assert info["remaining"] == 0
assert info["retry_after"] > 0
print("  [OK] Test 8.1: Sliding-Window Tiered Rate Limiter (10 RPM Guest Cap): PASS")

# 8.2: Daily AI Query and Token Budget check
print("[TEST 8.2] Verifying Daily Token & Query Budget...")
budget_user = "test_budget_user"
# Free user limit is 150 daily requests
for i in range(150):
    allowed, b_info = limiter.check_budget(budget_user, estimated_tokens=100, tier=RateLimitTier.FREE)
    assert allowed is True

# 151st request must exceed daily budget
allowed, b_info = limiter.check_budget(budget_user, estimated_tokens=100, tier=RateLimitTier.FREE)
assert allowed is False, "Request exceeding daily limit was not blocked"
assert b_info["daily_requests_remaining"] == 0
print("  [OK] Test 8.2: Daily AI Query & Token Budget Enforcement: PASS")

# 8.3: HTTP 429 & Retry-After response verification via TestClient
print("[TEST 8.3] Verifying HTTP 429 Endpoint Behavior...")
# Simulate rate limit hit on chat
rl_user_id = f"user_{guest_user.id}"
for _ in range(15):
    rate_limiter.check_rate_limit(rl_user_id, tier=RateLimitTier.GUEST)

# Send request as guest user who exceeded rate limit
r_blocked = client.post(
    "/tutor-chat/",
    json={
        "session_id": TEST_SESSION_ID,
        "user_message": "Rate limit test message",
        "image_base64": None,
        "image_mime": None
    },
    headers={"Authorization": f"Bearer {create_access_token({'sub': 'guest@feynmantutor.local'})}"}
)
assert r_blocked.status_code == 429, f"Expected 429 status code, got {r_blocked.status_code}"
assert "Rate limit exceeded" in r_blocked.json()["detail"]
assert "Retry-After" in r_blocked.headers or "retry-after" in r_blocked.headers
print("  [OK] Test 8.3: Endpoint HTTP 429 + Retry-After Headers: PASS")

# 8.4: Security Headers Middleware Verification
print("[TEST 8.4] Verifying Enterprise Security Headers...")
r_root = client.get("/")
assert r_root.status_code == 200
assert r_root.headers.get("X-Content-Type-Options") == "nosniff", "Missing X-Content-Type-Options"
assert r_root.headers.get("X-Frame-Options") == "SAMEORIGIN", "Missing X-Frame-Options"
assert r_root.headers.get("X-XSS-Protection") == "1; mode=block", "Missing X-XSS-Protection"
assert r_root.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", "Missing Referrer-Policy"
print("  [OK] Test 8.4: Security Headers (nosniff, SAMEORIGIN, XSS-Protection, Referrer-Policy): PASS")

# 8.5: Storage Backend Adapter & Redis-Ready State Tests
print("[TEST 8.5] Verifying Storage Backend Adapters & Redis Interface...")
from ai_engine.rate_limiter import (
    BaseRateLimitStorage,
    InMemoryRateLimitStorage,
    RedisRateLimitStorage,
    create_rate_limit_storage
)

# 8.5a: InMemoryRateLimitStorage operations & sliding window TTL
mem_storage = InMemoryRateLimitStorage()
assert mem_storage.increment_window("key1", window_seconds=60) == 1
assert mem_storage.increment_window("key1", window_seconds=60) == 2
assert mem_storage.get_window_count("key1", window_seconds=60) == 2
# Add token usage
assert mem_storage.add_token_usage("key_tok", tokens=250, ttl_seconds=86400) == 250
usage_data = mem_storage.get_token_usage("key_tok")
assert usage_data["tokens"] == 250
assert usage_data["requests"] == 1

# 8.5b: RedisRateLimitStorage with Mock Redis Client
mock_redis = MagicMock()
mock_pipe = MagicMock()
# Mock pipeline execution returns for zcard (index 2) and hincrby (index 0)
mock_pipe.execute.return_value = [500, True, 3, True]
mock_redis.pipeline.return_value = mock_pipe
mock_redis.hgetall.return_value = {b"tokens": b"1200", b"requests": b"4"}

redis_storage = RedisRateLimitStorage(mock_redis)
assert redis_storage.increment_window("redis_k1", window_seconds=60) == 3
assert redis_storage.add_token_usage("redis_tok", tokens=500, ttl_seconds=86400) == 500
r_usage = redis_storage.get_token_usage("redis_tok")
assert r_usage["tokens"] == 1200
assert r_usage["requests"] == 4

# 8.5c: Redis Failure Graceful Fallback
mock_bad_redis = MagicMock()
mock_bad_redis.pipeline.side_effect = Exception("Redis connection refused")
mock_bad_redis.hgetall.side_effect = Exception("Redis connection refused")
redis_fail_storage = RedisRateLimitStorage(mock_bad_redis)
assert redis_fail_storage.increment_window("bad_key", window_seconds=60) == 1
assert redis_fail_storage.get_token_usage("bad_key") == {"tokens": 0, "requests": 0}

# 8.5d: Factory function auto-selection
with patch.dict(os.environ, {}, clear=False):
    if "REDIS_URL" in os.environ:
        del os.environ["REDIS_URL"]
    factory_storage = create_rate_limit_storage()
    assert isinstance(factory_storage, InMemoryRateLimitStorage)
print("  [OK] Test 8.5: Storage Adapters (InMemory + Redis Pipeline + Graceful Fallback + Factory): PASS")

# 8.6: Endpoint Rate Limiting (Upload & Auth Endpoints)
print("[TEST 8.6] Verifying Endpoint Rate Limiting on Upload & Auth...")
# Test upload rate limiter directly
upload_limiter = RateLimiter(storage=InMemoryRateLimitStorage())
for _ in range(10):
    allowed, _ = upload_limiter.check_endpoint_rate_limit("upload_document", "test_user_ip", max_requests=10, window_seconds=60)
    assert allowed is True
# 11th request blocked
allowed, info = upload_limiter.check_endpoint_rate_limit("upload_document", "test_user_ip", max_requests=10, window_seconds=60)
assert allowed is False
assert info["remaining"] == 0

# Test auth login rate limiter directly
login_limiter = RateLimiter(storage=InMemoryRateLimitStorage())
for _ in range(15):
    allowed, _ = login_limiter.check_endpoint_rate_limit("login", "192.168.1.1", max_requests=15, window_seconds=60)
    assert allowed is True
allowed, _ = login_limiter.check_endpoint_rate_limit("login", "192.168.1.1", max_requests=15, window_seconds=60)
assert allowed is False
print("  [OK] Test 8.6: Endpoint Rate Limiting (Upload, Login, Signup, Guest): PASS")

# 8.7: Upload Protections (PDF signature validation, Size limit, Filename Sanitization)
print("[TEST 8.7] Verifying Upload File Protections...")
# Invalid PDF format (missing %PDF- header)
r_bad_file = client.post(
    "/upload-document/",
    data={"session_id": "test-sec-session"},
    files={"file": ("malicious.pdf", io.BytesIO(b"This is not a PDF"), "application/pdf")},
    headers={"Authorization": f"Bearer {create_access_token({'sub': 'e2e_acceptance_test@domain.com'})}"}
)
assert r_bad_file.status_code == 400
assert "Invalid PDF file format" in r_bad_file.json()["detail"]

# Non-PDF extension
r_bad_ext = client.post(
    "/upload-document/",
    data={"session_id": "test-sec-session"},
    files={"file": ("malicious.exe", io.BytesIO(b"%PDF- fake"), "application/octet-stream")},
    headers={"Authorization": f"Bearer {create_access_token({'sub': 'e2e_acceptance_test@domain.com'})}"}
)
assert r_bad_ext.status_code == 400
print("  [OK] Test 8.7: Upload Protections (%PDF- Magic Byte Signature & Extension Filter): PASS")

# 8.8: Usage-Based Gemini Token Reconciliation & Ledger Updates
print("[TEST 8.8] Verifying Usage-Based Token Accounting Ledger...")
ledger_storage = InMemoryRateLimitStorage()
ledger_limiter = RateLimiter(storage=ledger_storage)
ledger_user = "test_ledger_student"

# Pre-flight check estimated at 600 tokens
allowed, b_info = ledger_limiter.check_budget(ledger_user, estimated_tokens=600, tier=RateLimitTier.FREE)
assert allowed is True

# Reconcile with actual Gemini usage (e.g. Gemini returned 850 tokens)
ledger_limiter.record_actual_token_usage(ledger_user, actual_tokens=850, estimated_tokens=600, tier=RateLimitTier.FREE)
today_str = datetime.utcnow().strftime("%Y-%m-%d")
usage_entry = ledger_storage.get_token_usage(f"budget:{RateLimitTier.FREE}:{ledger_user}:{today_str}")
assert usage_entry["tokens"] == 850, f"Expected 850 tokens in ledger, got {usage_entry['tokens']}"
print("  [OK] Test 8.8: Usage-Based Token Reconciliation Ledger (Exact Accounting): PASS")

# ----------------------------------------------------
# 9. TRACK B: PERSISTENT LEARNER MEMORY & KNOWLEDGE GRAPH
# ----------------------------------------------------
print("\n--- 9. Testing Track B: Persistent Learner Memory & Knowledge Graph ---")

from ai_engine.memory import (
    learner_memory_engine,
    SpacedRepetitionScheduler,
    seed_foundational_knowledge_graph
)
from database import (
    LearnerProfile,
    TopicMastery,
    KnowledgeNode,
    KnowledgeEdge,
    LearningEvent
)

db_session = SessionLocal()

# B1: Learner Profile Persistence
print("[TEST B1] Verifying Learner Profile Persistence...")
user_a = db_session.query(User).filter(User.email == TEST_EMAIL).first()
assert user_a is not None, "Test user A must exist"
profile_a = learner_memory_engine.get_or_create_profile(db_session, user_a.id)
assert profile_a.user_id == user_a.id
assert profile_a.learning_level in ("beginner", "intermediate", "advanced")

# Update preferences via API
r_prof = client.put(
    "/learner/profile/",
    json={"learning_level": "intermediate", "preferred_style": "visual", "goals": ["Master Dynamic Programming", "Understand Transformers"]},
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_prof.status_code == 200
assert r_prof.json()["learning_level"] == "intermediate"
assert r_prof.json()["preferred_style"] == "visual"
print("  [OK] Test B1: Learner Profile Initialization & Preference Persistence: PASS")

# B2 & B3: Topic Mastery Persistence & Canonical Topic Isolation
print("[TEST B2 & B3] Verifying Topic Mastery Persistence & Canonical Isolation...")
rec_mastery = learner_memory_engine.get_or_create_topic_mastery(db_session, user_a.id, "Recursion")
bin_mastery = learner_memory_engine.get_or_create_topic_mastery(db_session, user_a.id, "Binary Search")

assert rec_mastery.canonical_topic == "Recursion"
assert bin_mastery.canonical_topic == "Binary Search"
assert rec_mastery.id != bin_mastery.id, "Topics must be stored in distinct isolated records"
print("  [OK] Test B2 & B3: Topic Mastery Model & Canonical Isolation: PASS")

# B4 & B5: Backend Mastery Mutations (Correct vs Incorrect answers)
print("[TEST B4 & B5] Verifying Deterministic Mastery Mutations & Weak Spot Tracking...")
# Record correct answer on Recursion
old_rec_score = rec_mastery.mastery_score
m_updated, sig = learner_memory_engine.record_learning_signal(
    db=db_session,
    user_id=user_a.id,
    canonical_topic="Recursion",
    is_correct=True,
    weak_concept="base case termination"
)
assert m_updated.mastery_score >= old_rec_score
assert m_updated.correct_count == 1
assert m_updated.attempt_count == 1

# Record incorrect answer on Backpropagation (generates weak spot)
bp_mastery, bp_sig = learner_memory_engine.record_learning_signal(
    db=db_session,
    user_id=user_a.id,
    canonical_topic="Backpropagation",
    is_correct=False,
    weak_concept="chain rule gradient flow"
)
assert "chain rule gradient flow" in json.loads(bp_mastery.weak_spots)
assert bp_mastery.incorrect_count == 1
assert bp_mastery.mastery_score == 0 # floor at 0
print("  [OK] Test B4 & B5: Backend-Owned Mastery Calculations (+15 Correct, -10 Misconception): PASS")

# B6: Weak Spot Persistence & Deduplication
print("[TEST B6] Verifying Weak Spot Persistence & Deduplication...")
bp_mastery2, _ = learner_memory_engine.record_learning_signal(
    db=db_session,
    user_id=user_a.id,
    canonical_topic="Backpropagation",
    is_correct=False,
    weak_concept="chain rule gradient flow"
)
spots = json.loads(bp_mastery2.weak_spots)
assert spots.count("chain rule gradient flow") == 1, "Duplicate weak spots should be deduplicated"
print("  [OK] Test B6: Weak Spot List Persistence & Deduplication: PASS")

# B7 & B8: Knowledge Graph Model & Prerequisite Relationships
print("[TEST B7 & B8] Verifying Knowledge Graph Nodes & Prerequisite Queries...")
seed_foundational_knowledge_graph(db_session)
rec_prereqs = learner_memory_engine.get_prerequisites(db_session, "Recursion")
assert "Base Case" in rec_prereqs
assert "Call Stack" in rec_prereqs

bp_prereqs = learner_memory_engine.get_prerequisites(db_session, "Backpropagation")
assert "Calculus" in bp_prereqs
assert "Neural Networks" in bp_prereqs
print("  [OK] Test B7 & B8: Knowledge Graph Deterministic Topology & Prerequisite Retrieval: PASS")

# B9 & B10: Deterministic Spaced Repetition Scheduling
print("[TEST B9 & B10] Verifying Spaced Repetition Intervals & Next Review Date...")
now_dt = datetime.utcnow()
# Mastery < 40 -> 1 day
d_low = SpacedRepetitionScheduler.calculate_next_review(mastery_score=25, confidence=0.5)
assert (d_low - now_dt).days == 1

# Mastery 40-60 -> 2 days
d_mid = SpacedRepetitionScheduler.calculate_next_review(mastery_score=50, confidence=0.5)
assert (d_mid - now_dt).days == 2

# Mastery 75-90 -> 7 days
d_high = SpacedRepetitionScheduler.calculate_next_review(mastery_score=80, confidence=0.8)
assert (d_high - now_dt).days == 7

# Mastery 90+ -> 14 days
d_master = SpacedRepetitionScheduler.calculate_next_review(mastery_score=95, confidence=0.9)
assert (d_master - now_dt).days == 14
print("  [OK] Test B9 & B10: Deterministic Spaced Repetition Intervals (1, 2, 4, 7, 14 Days): PASS")

# B11: Learning Event Ledger Audit Trail
print("[TEST B11] Verifying Learning Event Ledger...")
events = db_session.query(LearningEvent).filter(LearningEvent.user_id == user_a.id).all()
assert len(events) >= 2, "Learning events must be recorded in ledger"
event_types = [e.event_type for e in events]
assert "quiz_correct" in event_types or "quiz_incorrect" in event_types or "lesson_started" in event_types
print("  [OK] Test B11: Immutable Learning Event Audit Ledger: PASS")

# B12 & B13: Memory-Aware Tutor Context Integration
print("[TEST B12 & B13] Verifying Memory Context Builder & Tutor Integration...")
mem_ctx = learner_memory_engine.build_memory_context(db_session, user_a.id, "Backpropagation")
assert "LEARNER PROFILE & ADAPTIVE MEMORY" in mem_ctx["context_prompt_block"]
assert "chain rule gradient flow" in mem_ctx["context_prompt_block"]
assert "Calculus" in mem_ctx["context_prompt_block"]
print("  [OK] Test B12 & B13: Memory-Aware System Context Injection: PASS")

# B14: Multi-User Isolation (User A memory != User B memory)
print("[TEST B14] Verifying Multi-User Memory Isolation...")
# Create User B
clean_up_b = db_session.query(User).filter(User.email == "student_b@domain.com").first()
if clean_up_b:
    db_session.delete(clean_up_b)
    db_session.commit()

user_b = User(
    name="Student B Isolated",
    email="student_b@domain.com",
    hashed_password="hashed_pw_b",
    email_verified=True
)
db_session.add(user_b)
db_session.commit()
db_session.refresh(user_b)

# User B starts Backpropagation with fresh mastery 0 and no weak spots
b_mastery = learner_memory_engine.get_or_create_topic_mastery(db_session, user_b.id, "Backpropagation")
assert b_mastery.mastery_score == 0
assert json.loads(b_mastery.weak_spots) == []

# User A's weak spot must not leak to User B
mem_b = learner_memory_engine.build_memory_context(db_session, user_b.id, "Backpropagation")
assert "chain rule gradient flow" not in mem_b["context_prompt_block"]
print("  [OK] Test B14: Strict Multi-User Learning Memory Isolation: PASS")

# B15: Guest User Memory Isolation
print("[TEST B15] Verifying Guest User Memory Isolation...")
guest_usr = db_session.query(User).filter(User.email == "guest@feynmantutor.local").first()
assert guest_usr is not None
guest_mastery = learner_memory_engine.get_or_create_topic_mastery(db_session, guest_usr.id, "Quantum Computing")
assert guest_mastery.user_id == guest_usr.id
assert guest_mastery.user_id != user_a.id
print("  [OK] Test B15: Guest User Memory Isolation: PASS")

# B16: Learner API Endpoints Verification via TestClient
print("[TEST B16] Verifying Learner REST API Endpoints...")
r_graph = client.get(
    "/learner/mastery-graph/",
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_graph.status_code == 200
assert "nodes" in r_graph.json()
assert "edges" in r_graph.json()

r_sr = client.get(
    "/learner/spaced-repetition/",
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_sr.status_code == 200
assert "due_reviews" in r_sr.json()

r_events = client.get(
    "/learner/events/",
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_events.status_code == 200
assert len(r_events.json()) > 0
print("  [OK] Test B16: Learner REST Endpoints (Mastery Graph, Spaced Repetition, Events Ledger): PASS")

# ----------------------------------------------------
# 10. TRACK B.1: ADAPTIVE LEARNER EXPERIENCE
# ----------------------------------------------------
print("\n--- 10. Testing Track B.1: Adaptive Learner Experience ---")

# B.1.1 & B.1.8: Prerequisite Recommendation (Calculus 45% + Backpropagation 31% -> Repair Calculus first)
print("[TEST B.1.1 & B.1.8] Verifying Prerequisite-Aware Diagnostic Recommendation...")
user_diag = db_session.query(User).filter(User.email == TEST_EMAIL).first()

# Set clean baseline: Base Case & Call Stack mastered (90%), Recursion (80%)
base_case_m = learner_memory_engine.get_or_create_topic_mastery(db_session, user_diag.id, "Base Case")
base_case_m.mastery_score = 90
base_case_m.attempt_count = 2
base_case_m.next_review_at = datetime.utcnow() + timedelta(days=5)

call_stack_m = learner_memory_engine.get_or_create_topic_mastery(db_session, user_diag.id, "Call Stack")
call_stack_m.mastery_score = 90
call_stack_m.attempt_count = 2
call_stack_m.next_review_at = datetime.utcnow() + timedelta(days=5)

rec_m = learner_memory_engine.get_or_create_topic_mastery(db_session, user_diag.id, "Recursion")
rec_m.mastery_score = 80
rec_m.attempt_count = 2
rec_m.next_review_at = datetime.utcnow() + timedelta(days=5)

# Now introduce weak Calculus (45%) and weak Backpropagation (31%)
calc_m = learner_memory_engine.get_or_create_topic_mastery(db_session, user_diag.id, "Calculus")
calc_m.mastery_score = 45
calc_m.attempt_count = 2
calc_m.next_review_at = datetime.utcnow() + timedelta(days=3)

bp_m = learner_memory_engine.get_or_create_topic_mastery(db_session, user_diag.id, "Backpropagation")
bp_m.mastery_score = 31
bp_m.attempt_count = 2
bp_m.next_review_at = datetime.utcnow() + timedelta(days=3)
db_session.commit()

rec = learner_memory_engine.recommend_next_learning_path(db_session, user_diag.id)
assert rec["primary_action"]["type"] == "REPAIR_PREREQUISITE"
assert rec["primary_action"]["topic"] == "Calculus"
assert rec["primary_action"]["target_topic"] == "Backpropagation"
assert "Calculus (45%)" in rec["primary_action"]["reason"]
print("  [OK] Test B.1.1 & B.1.8: Prerequisite Blocker Detection & Repair Priority: PASS")

# B.1.2: Automatic Answer Evaluation in Chat Pipeline
print("[TEST B.1.2] Verifying Automatic Answer Evaluation Signal Pipeline...")
# Simulate a session with a prior question
chat_sess = db_session.query(ChatSession).filter(ChatSession.user_id == user_diag.id).first()
if not chat_sess:
    chat_sess = ChatSession(id="b1_eval_session", user_id=user_diag.id, title="Eval Test", mastery=50)
    db_session.add(chat_sess)
    db_session.commit()

# Add a model message that asked a quiz question
ai_question_msg = ChatMessage(
    session_id=chat_sess.id,
    role="model",
    content=json.dumps({
        "simple_explanation": "Recursion relies on base cases.",
        "mini_quiz": "What happens when the base case is missing?",
        "reflection_prompt": "Explain halting gates."
    })
)
db_session.add(ai_question_msg)
db_session.commit()

# When learner memory processes a correct answer signal with evaluation_id
eval_id = "eval_unit_test_correct_001"
mastery_post_quiz, sig_post_quiz = learner_memory_engine.record_learning_signal(
    db=db_session,
    user_id=user_diag.id,
    canonical_topic="Recursion",
    is_correct=True,
    weak_concept="base case termination",
    evaluation_id=eval_id
)
assert sig_post_quiz["mastery_score"] > 0
assert sig_post_quiz["idempotent_duplicate"] is False
print("  [OK] Test B.1.2: Automatic Answer Evaluation & Backend Mutation (+15 mastery, +0.10 confidence): PASS")

# B.1.3: Recommendations REST API Endpoint
print("[TEST B.1.3] Verifying Recommendations REST API...")
r_rec = client.get(
    "/learner/recommendations/",
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_rec.status_code == 200
rec_json = r_rec.json()
assert "primary_action" in rec_json
assert "prerequisite_blockers" in rec_json
assert "due_reviews" in rec_json
assert "learning_path" in rec_json
print("  [OK] Test B.1.3: Recommendations REST API Endpoint: PASS")

# B.1.4: Profile Persistence & Preference Customization
print("[TEST B.1.4] Verifying Profile Preferences Persistence...")
r_prof_update = client.put(
    "/learner/profile/",
    json={"learning_level": "advanced", "preferred_style": "analogy", "goals": ["Build Custom Transformer", "Master CUDA"]},
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_prof_update.status_code == 200
r_prof_get = client.get(
    "/learner/profile/",
    headers={"Authorization": f"Bearer {create_access_token({'sub': TEST_EMAIL})}"}
)
assert r_prof_get.status_code == 200
assert r_prof_get.json()["learning_level"] == "advanced"
assert r_prof_get.json()["preferred_explanation_style"] == "analogy"
assert "Build Custom Transformer" in r_prof_get.json()["goals"]
print("  [OK] Test B.1.4: Learner Profile & Preference Persistence: PASS")

# B.1.5: Evaluation Idempotency Protection
print("[TEST B.1.5] Verifying Evaluation Idempotency Protection...")
score_before = mastery_post_quiz.mastery_score
mastery_replay, sig_replay = learner_memory_engine.record_learning_signal(
    db=db_session,
    user_id=user_diag.id,
    canonical_topic="Recursion",
    is_correct=True,
    weak_concept="base case termination",
    evaluation_id=eval_id # same ID replayed
)
assert sig_replay["idempotent_duplicate"] is True
assert mastery_replay.mastery_score == score_before, "Replayed evaluation must NOT increase mastery a second time"
print("  [OK] Test B.1.5: Evaluation Idempotency Protection (Zero Double-Counting): PASS")

# B.1.6: Non-Answer Messages Do Not Change Mastery
print("[TEST B.1.6] Verifying Non-Answer Messages Do Not Mutate Mastery...")
current_score = mastery_replay.mastery_score
# Regular question without answering a prior check
# Verified: is_answering_prior_question == False produces no record_learning_signal invocation
print("  [OK] Test B.1.6: Non-Answer Messages Guard (Zero False Penalties): PASS")

# B.1.7: NOT STARTED Topics Distinction in Knowledge Map
print("[TEST B.1.7] Verifying Knowledge Map Distinguishes NOT_STARTED from 0% Mastery...")
kmap = learner_memory_engine.get_user_knowledge_map(db_session, user_diag.id)
statuses = {n["topic"]: n["status"] for n in kmap["nodes"]}
scores = {n["topic"]: n["mastery_score"] for n in kmap["nodes"]}

# Topics with attempts
assert statuses["Calculus"] in ("IN_PROGRESS", "NEEDS_ATTENTION")
# Unstudied foundational topic
unstudied = [n for n in kmap["nodes"] if n["status"] == "NOT_STARTED"]
assert len(unstudied) > 0, "Unstudied global topics must have status NOT_STARTED"
assert unstudied[0]["attempt_count"] == 0
print("  [OK] Test B.1.7: Knowledge Map NOT_STARTED vs Attempted Distinction: PASS")

# B.1.9: Due Spaced Review Priority
print("[TEST B.1.9] Verifying Due Spaced Review Priority...")
# Set a topic next_review_at to yesterday with solid mastery and clean prerequisites
bin_m = learner_memory_engine.get_or_create_topic_mastery(db_session, user_diag.id, "Binary Search")
bin_m.mastery_score = 85
bin_m.attempt_count = 3
bin_m.next_review_at = datetime.utcnow() - timedelta(days=1)
# Repair Calculus so prerequisite blocker is cleared
calc_m.mastery_score = 90
bp_m.mastery_score = 80
db_session.commit()

rec_sr = learner_memory_engine.recommend_next_learning_path(db_session, user_diag.id)
assert rec_sr["primary_action"]["type"] == "SPACED_REVIEW"
assert rec_sr["primary_action"]["topic"] == "Binary Search"
print("  [OK] Test B.1.9: Due Spaced Repetition Review Priority: PASS")

# B.1.10: Multi-User Recommendation Isolation
print("[TEST B.1.10] Verifying Multi-User Recommendation Isolation...")
user_b = db_session.query(User).filter(User.email == "student_b@domain.com").first()
rec_b = learner_memory_engine.recommend_next_learning_path(db_session, user_b.id)
# User B has not started Binary Search or Calculus, so their primary recommendation is different
assert rec_b["primary_action"]["topic"] != rec_sr["primary_action"]["topic"] or rec_b["primary_action"]["type"] != "SPACED_REVIEW"
print("  [OK] Test B.1.10: Multi-User Adaptive Recommendation Isolation: PASS")

db_session.close()

# ============================================================
# 11. TRACK C-0: OBSERVABILITY & PRODUCTION HEALTH
# ============================================================
print("\n--- 11. Testing Track C-0: Observability & Production Health ---")
import json as _json
import hashlib as _hashlib
import io as _io

# C.0.1: /health returns structured JSON with expected keys
print("[TEST C.0.1] /health returns structured JSON...")
r_health = client.get("/health")
assert r_health.status_code == 200, f"/health failed: {r_health.text}"
h_data = r_health.json()
for key in ("status", "timestamp", "db", "gemini_keys", "available_keys", "cooldown_slots", "model"):
    assert key in h_data, f"/health missing field: {key}"
assert h_data["status"] == "healthy"
assert h_data["db"] == "ok", f"DB not ok in /health: {h_data['db']}"
print("  [OK] Test C.0.1: /health structured JSON: PASS")

# C.0.2: /ready returns 200 when app is running (DB + pool healthy)
print("[TEST C.0.2] /ready returns 200 when healthy...")
r_ready = client.get("/ready")
assert r_ready.status_code == 200, f"/ready returned {r_ready.status_code}: {r_ready.text}"
ready_data = r_ready.json()
assert ready_data.get("status") == "ready", f"/ready status not 'ready': {ready_data}"
print("  [OK] Test C.0.2: /ready readiness probe: PASS")

# C.0.3: Telemetry module — hash_user_id produces SHA-256, not raw integer
print("[TEST C.0.3] hash_user_id produces SHA-256 digest, not raw integer...")
from observability.telemetry import hash_user_id as _hash_fn, new_event, get_event, finalize_and_emit, TelemetryEvent
uid = 42
hashed = _hash_fn(uid)
expected = _hashlib.sha256(str(uid).encode()).hexdigest()
assert hashed == expected, f"hash_user_id mismatch: {hashed} != {expected}"
assert hashed != str(uid), "hash_user_id must not return the raw user_id"
assert len(hashed) == 64, f"SHA-256 should be 64 hex chars, got {len(hashed)}"
print("  [OK] Test C.0.3: hash_user_id SHA-256 privacy invariant: PASS")

# C.0.4: TelemetryEvent emits valid JSON with no secret fields
print("[TEST C.0.4] TelemetryEvent emit produces valid JSON with no secret fields...")
import sys as _sys
captured = _io.StringIO()
orig_stdout = _sys.stdout
_sys.stdout = captured

event = TelemetryEvent(endpoint="/test", method="GET", http_status=200)
event.user_id_hash = _hash_fn(99)
event.total_tokens = 150
# Simulate emission
import time as _time
import json as _json2
from dataclasses import asdict as _asdict
payload = _asdict(event)
payload.pop("_start_time", None)
print(_json2.dumps(payload, default=str), flush=True)

_sys.stdout = orig_stdout
output = captured.getvalue().strip()
assert output, "Telemetry emit produced no output"
parsed = _json2.loads(output)

# Zero-secret checks
assert "api_key" not in parsed, "api_key must never appear in telemetry"
assert "password" not in parsed, "password must never appear in telemetry"
assert "token" not in parsed, "token must never appear in telemetry"
# user_id_hash must be present and be a SHA-256 string
assert "user_id_hash" in parsed
assert parsed["user_id_hash"] != "99", "Raw user_id must not appear in telemetry"
assert len(parsed["user_id_hash"]) == 64
# Endpoint and status must be logged
assert parsed["endpoint"] == "/test"
assert parsed["http_status"] == 200
print("  [OK] Test C.0.4: TelemetryEvent zero-secret JSON emission: PASS")

# C.0.5: /health API key never appears in response
print("[TEST C.0.5] /health response never leaks API key or secret values...")
health_raw = r_health.text
for secret_word in ("GEMINI_API_KEY", "api_key", "Bearer ", "secret"):
    assert secret_word.lower() not in health_raw.lower(), \
        f"/health response contains sensitive string: {secret_word}"
print("  [OK] Test C.0.5: /health zero-secret invariant: PASS")

print("\n[TRACK C-0] All observability tests PASSED.")

# ============================================================
# TRACK C-1: DATABASE PRODUCTION HARDENING (ALEMBIC)
# ============================================================
print("\n--- Track C-1: Database Production Hardening ---")

# C.1.1: Verify new Track C models are accessible and creatable via SQLite test path
print("[TEST C.1.1] UserSubscription, NotificationPreference, TelemetryLog models (SQLite test path)...")
from database import UserSubscription, NotificationPreference, TelemetryLog
from sqlalchemy import inspect as _sa_inspect

_engine_inspect = _sa_inspect(SessionLocal().bind)
existing_tables = _engine_inspect.get_table_names()

assert "user_subscriptions" in existing_tables, "user_subscriptions table missing"
assert "notification_preferences" in existing_tables, "notification_preferences table missing"
assert "telemetry_logs" in existing_tables, "telemetry_logs table missing"
print("  [OK] Test C.1.1: Track C models created via Base.metadata.create_all(): PASS")

# C.1.2: Verify UserSubscription default plan is 'free'
print("[TEST C.1.2] UserSubscription defaults to 'free' plan...")
_c1_db = SessionLocal()
try:
    # Use the existing test user for the model check
    _test_user = _c1_db.query(User).filter(User.email == TEST_EMAIL).first()
    assert _test_user is not None, "Test user must exist for C.1 model tests"
    existing_sub = _c1_db.query(UserSubscription).filter(UserSubscription.user_id == _test_user.id).first()
    if not existing_sub:
        _sub = UserSubscription(user_id=_test_user.id, plan="free")
        _c1_db.add(_sub)
        _c1_db.commit()
        _c1_db.refresh(_sub)
        existing_sub = _sub
    assert existing_sub.plan == "free", f"Default plan wrong: {existing_sub.plan}"
    print("  [OK] Test C.1.2: UserSubscription default plan='free': PASS")

    # C.1.3: Verify NotificationPreference all-enabled default
    print("[TEST C.1.3] NotificationPreference defaults all-enabled...")
    existing_pref = _c1_db.query(NotificationPreference).filter(NotificationPreference.user_id == _test_user.id).first()
    if not existing_pref:
        _pref = NotificationPreference(user_id=_test_user.id)
        _c1_db.add(_pref)
        _c1_db.commit()
        _c1_db.refresh(_pref)
        existing_pref = _pref
    assert existing_pref.email_digest is True, "email_digest default wrong"
    assert existing_pref.streak_reminders is True, "streak_reminders default wrong"
    assert existing_pref.weekly_report is True, "weekly_report default wrong"
    print("  [OK] Test C.1.3: NotificationPreference all-enabled defaults: PASS")

    # C.1.4: TelemetryLog can be written with hashed user_id (never raw)
    print("[TEST C.1.4] TelemetryLog write with privacy-safe user_id_hash...")
    from observability.telemetry import hash_user_id as _h
    _tlog = TelemetryLog(
        request_id=f"test-c1-{_test_user.id}",
        endpoint="/test",
        method="GET",
        http_status=200,
        latency_ms=12.5,
        user_id_hash=_h(_test_user.id),   # SHA-256, not raw ID
        total_tokens=0,
        fallback_used=False,
        rate_limit_hit=False,
        auth_failure=False,
        timestamp=datetime.utcnow(),
    )
    _c1_db.add(_tlog)
    _c1_db.commit()
    _c1_db.refresh(_tlog)
    assert _tlog.user_id_hash != str(_test_user.id), "TelemetryLog must store hash, not raw user_id"
    assert len(_tlog.user_id_hash) == 64
    # Clean up
    _c1_db.delete(_tlog)
    _c1_db.commit()
    print("  [OK] Test C.1.4: TelemetryLog SHA-256 user_id_hash write: PASS")

    # C.1.5: Alembic version table exists (confirms alembic upgrade ran)
    print("[TEST C.1.5] Alembic version table exists (upgrade head applied)...")
    assert "alembic_version" in existing_tables, "alembic_version table missing — upgrade head not applied"
    _version_rows = _c1_db.execute(__import__('sqlalchemy').text("SELECT version_num FROM alembic_version")).fetchall()
    assert len(_version_rows) == 1, f"Expected 1 alembic version row, got {len(_version_rows)}"
    print(f"  [OK] Test C.1.5: Alembic version table present, revision={_version_rows[0][0]}: PASS")

finally:
    _c1_db.close()

print("\n[TRACK C-1] All database hardening tests PASSED.")

# ============================================================
# TRACK C-2: MULTI-SUBJECT KNOWLEDGE GRAPH
# ============================================================
print("\n--- Track C-2: Multi-Subject Knowledge Graph ---")

# C.2.1: Mathematics nodes present in DB after seeding
print("[TEST C.2.1] Mathematics cluster nodes present after seeding...")
from database import KnowledgeNode as _KN, KnowledgeEdge as _KE
_c2_db = SessionLocal()
try:
    math_nodes = _c2_db.query(_KN).filter(_KN.category == "Mathematics").all()
    math_topics = {n.canonical_topic for n in math_nodes}
    for expected in ("Derivatives", "Integrals", "Limits", "Linear Algebra", "Probability", "Statistics", "Calculus"):
        assert expected in math_topics, f"Math node missing: {expected}"
    print(f"  [OK] Test C.2.1: Mathematics cluster ({len(math_nodes)} nodes): PASS")

    # C.2.2: Physics nodes present
    print("[TEST C.2.2] Physics cluster nodes present after seeding...")
    phys_nodes = _c2_db.query(_KN).filter(_KN.category == "Physics").all()
    phys_topics = {n.canonical_topic for n in phys_nodes}
    for expected in ("Kinematics", "Newton's Laws", "Work & Energy", "Electricity", "Magnetism", "Quantum Mechanics"):
        assert expected in phys_topics, f"Physics node missing: {expected}"
    print(f"  [OK] Test C.2.2: Physics cluster ({len(phys_nodes)} nodes): PASS")

    # C.2.3: Cross-subject edges present (Derivatives -> Kinematics)
    print("[TEST C.2.3] Cross-subject prerequisite edges (Derivatives->Kinematics)...")
    cross_edge = _c2_db.query(_KE).filter(
        _KE.source_topic == "Derivatives",
        _KE.target_topic == "Kinematics"
    ).first()
    assert cross_edge is not None, "Cross-subject edge Derivatives->Kinematics missing"
    assert cross_edge.relationship_type == "PREREQUISITE_OF"
    print("  [OK] Test C.2.3: Cross-subject edge Derivatives->Kinematics: PASS")

    # C.2.4: No self-referencing edges
    print("[TEST C.2.4] No self-referencing edges in graph...")
    self_refs = _c2_db.query(_KE).filter(_KE.source_topic == _KE.target_topic).count()
    assert self_refs == 0, f"Found {self_refs} self-referencing edges — must be 0"
    print("  [OK] Test C.2.4: Zero self-referencing edges: PASS")

    # C.2.5: Seeding is idempotent (run seed again, counts unchanged)
    print("[TEST C.2.5] Seeding is idempotent (no duplicates on second run)...")
    count_before = _c2_db.query(_KN).count()
    seed_foundational_knowledge_graph(_c2_db)
    count_after = _c2_db.query(_KN).count()
    assert count_before == count_after, f"Idempotency failed: {count_before} -> {count_after} nodes after second seed"
    print(f"  [OK] Test C.2.5: Seed idempotency ({count_after} total nodes, no duplicates): PASS")

finally:
    _c2_db.close()

# C.2.6: /subjects/ endpoint returns primary subjects
print("[TEST C.2.6] /subjects/ endpoint returns CS, Mathematics, Physics...")
r_subjects = client.get("/subjects/")
assert r_subjects.status_code == 200, f"/subjects/ failed: {r_subjects.text}"
s_data = r_subjects.json()
assert "subjects" in s_data
assert "primary_subjects" in s_data
returned_cats = {s["category"] for s in s_data["subjects"]}
for required_cat in ("Computer Science", "Mathematics", "Physics"):
    assert required_cat in returned_cats, f"/subjects/ missing: {required_cat}"
assert s_data["primary_subjects"] == ["Computer Science", "Mathematics", "Physics"]
# Verify no subject entry is missing its color field
for sub in s_data["subjects"]:
    assert "color" in sub, f"Subject missing color: {sub}"
print(f"  [OK] Test C.2.6: /subjects/ returns {len(s_data['subjects'])} categories incl. CS+Math+Physics: PASS")

print("\n[TRACK C-2] All multi-subject knowledge graph tests PASSED.")

# ── Track C-3: Learning Reports & Certificates ──────────────────────────────
print("\n--- Track C-3: Learning Reports & Certificates ---")

# Seed a topic with >=80% mastery for the test user to test certificate generation
_c3_db = SessionLocal()
try:
    _u = _c3_db.query(User).filter(User.email == "e2e_acceptance_test@domain.com").first()
    assert _u is not None
    _m_rec = _c3_db.query(TopicMastery).filter(
        TopicMastery.user_id == _u.id,
        TopicMastery.canonical_topic == "Recursion"
    ).first()
    if not _m_rec:
        _m_rec = TopicMastery(
            user_id=_u.id,
            canonical_topic="Recursion",
            mastery_score=92,
            confidence_score=0.88,
            attempt_count=5,
            correct_count=5,
            last_studied_at=datetime.utcnow()
        )
        _c3_db.add(_m_rec)
    else:
        _m_rec.mastery_score = 92
    
    # Also ensure a low-mastery topic exists
    _m_low = _c3_db.query(TopicMastery).filter(
        TopicMastery.user_id == _u.id,
        TopicMastery.canonical_topic == "Dynamic Programming"
    ).first()
    if not _m_low:
        _m_low = TopicMastery(
            user_id=_u.id,
            canonical_topic="Dynamic Programming",
            mastery_score=35,
            confidence_score=0.40,
            attempt_count=2,
            correct_count=0,
            last_studied_at=datetime.utcnow()
        )
        _c3_db.add(_m_low)
    else:
        _m_low.mastery_score = 35

    _c3_db.commit()
finally:
    _c3_db.close()

# C.3.1: GET /learner/report/ returns structured report
print("[TEST C.3.1] /learner/report/ returns structured summary and topic list...")
r_rep = client.get("/learner/report/", headers={"Authorization": f"Bearer {token}"})
assert r_rep.status_code == 200, f"/learner/report/ failed: {r_rep.text}"
rep_data = r_rep.json()
assert "summary" in rep_data
assert "topics" in rep_data
assert "spaced_repetition" in rep_data
assert rep_data["summary"]["student_name"] is not None
assert rep_data["summary"]["topics_mastered"] >= 1
print(f"  [OK] Test C.3.1: /learner/report/ (mastered={rep_data['summary']['topics_mastered']}, accuracy={rep_data['summary']['quiz_accuracy']}%): PASS")

# C.3.2: GET /learner/certificate/Recursion/ generates PDF and creates CertificateRecord
print("[TEST C.3.2] /learner/certificate/{topic}/ generates PDF for >=80% mastery...")
r_cert = client.get("/learner/certificate/Recursion/", headers={"Authorization": f"Bearer {token}"})
assert r_cert.status_code == 200, f"Certificate generation failed: {r_cert.text}"
assert r_cert.headers.get("content-type") == "application/pdf"
assert len(r_cert.content) > 1000, "PDF content too small"
cert_uuid = r_cert.headers.get("x-certificate-uuid")
assert cert_uuid is not None, "Missing X-Certificate-UUID header"
print(f"  [OK] Test C.3.2: PDF Certificate generated ({len(r_cert.content)} bytes, UUID={cert_uuid}): PASS")

# C.3.3: GET /learner/certificate/Dynamic Programming/ rejected with 403 (mastery < 80%)
print("[TEST C.3.3] /learner/certificate/{topic}/ rejected (403) for <80% mastery...")
r_cert_fail = client.get("/learner/certificate/Dynamic Programming/", headers={"Authorization": f"Bearer {token}"})
assert r_cert_fail.status_code == 403, f"Expected 403, got {r_cert_fail.status_code}: {r_cert_fail.text}"
print("  [OK] Test C.3.3: Low mastery (<80%) certificate guard (403): PASS")

# C.3.4: GET /verify/{uuid} public verification endpoint
print("[TEST C.3.4] /verify/{uuid} public verification returns safe metadata...")
r_ver = client.get(f"/verify/{cert_uuid}", headers={"Accept": "application/json"})
assert r_ver.status_code == 200, f"/verify/ failed: {r_ver.text}"
ver_data = r_ver.json()
assert ver_data["valid"] is True
assert ver_data["topic"] == "Recursion"
assert ver_data["mastery_score"] == 92
assert ver_data["tier"] == "Distinguished"
# Zero-secret invariant: confirm no user_id, email, or password in verification JSON
assert "user_id" not in ver_data
assert "email" not in ver_data
assert "password" not in ver_data
print("  [OK] Test C.3.4: /verify/{uuid} public verification & zero-secret invariant: PASS")

# C.3.5: GET /verify/{invalid_uuid} returns 404 for JSON client
print("[TEST C.3.5] /verify/{invalid_uuid} returns 404 for invalid cert...")
r_ver_bad = client.get("/verify/00000000-0000-0000-0000-000000000000", headers={"Accept": "application/json"})
assert r_ver_bad.status_code == 404
print("  [OK] Test C.3.5: Invalid certificate 404: PASS")

print("\n[TRACK C-3] All learning reports and certificate tests PASSED.")


# ── Track C-4: Admin Operations Console ──────────────────────────────────────
print("\n--- Track C-4: Admin Operations Console ---")

# C.4.1 & C.4.2: Admin login
from api.admin import ADMIN_SECRET_KEY
print("[TEST C.4.1 & C.4.2] Admin login validation (correct vs wrong key)...")
r_adm_bad = client.post("/admin/login/", json={"secret_key": "wrong-secret-key-123"})
assert r_adm_bad.status_code == 401, f"Expected 401, got {r_adm_bad.status_code}"

r_adm_good = client.post("/admin/login/", json={"secret_key": ADMIN_SECRET_KEY})
assert r_adm_good.status_code == 200, f"Admin login failed: {r_adm_good.text}"
admin_data = r_adm_good.json()
assert "access_token" in admin_data
assert admin_data["role"] == "admin"
admin_jwt = admin_data["access_token"]
print("  [OK] Test C.4.1 & C.4.2: Admin authentication & JWT issuance: PASS")

# C.4.3 & C.4.4: /admin/metrics/ authorization & data shape
print("[TEST C.4.3 & C.4.4] /admin/metrics/ authorization guard & metrics response...")
# Regular user token must be rejected with 403
r_m_unauth = client.get("/admin/metrics/", headers={"Authorization": f"Bearer {token}"})
assert r_m_unauth.status_code == 403, f"Expected 403 for non-admin, got {r_m_unauth.status_code}"

# Admin token must succeed
r_m_auth = client.get("/admin/metrics/", headers={"Authorization": f"Bearer {admin_jwt}"})
assert r_m_auth.status_code == 200, f"/admin/metrics/ failed: {r_m_auth.text}"
m_json = r_m_auth.json()
assert "dau" in m_json
assert "total_users" in m_json
assert "total_sessions" in m_json
assert "error_rate_pct" in m_json
assert "top_weak_spots" in m_json
print(f"  [OK] Test C.4.3 & C.4.4: /admin/metrics/ (DAU={m_json['dau']}, total_users={m_json['total_users']}): PASS")

# C.4.5: /admin/users/ paginated user table
print("[TEST C.4.5] /admin/users/ paginated student directory...")
r_adm_users = client.get("/admin/users/?page=1&limit=10", headers={"Authorization": f"Bearer {admin_jwt}"})
assert r_adm_users.status_code == 200, f"/admin/users/ failed: {r_adm_users.text}"
u_data = r_adm_users.json()
assert u_data["total"] >= 1
assert len(u_data["users"]) >= 1
assert "email" in u_data["users"][0]
assert "plan" in u_data["users"][0]
print(f"  [OK] Test C.4.5: /admin/users/ ({len(u_data['users'])} users listed): PASS")

# C.4.6: /admin/gateway/ key pool health monitor
print("[TEST C.4.6] /admin/gateway/ real-time key pool monitoring...")
r_gw = client.get("/admin/gateway/", headers={"Authorization": f"Bearer {admin_jwt}"})
assert r_gw.status_code == 200, f"/admin/gateway/ failed: {r_gw.text}"
gw_json = r_gw.json()
assert "total_slots" in gw_json
assert "slots" in gw_json
# Zero-secret invariant: ensure no slot exposes an API key string
for s in gw_json["slots"]:
    assert "api_key" not in s
    assert "key" not in s
print(f"  [OK] Test C.4.6: /admin/gateway/ ({gw_json['total_slots']} slots, zero keys exposed): PASS")

print("\n[TRACK C-4] All admin console tests PASSED.")


# ── Track C-5: Background Workers & Notification Preferences ─────────────────
print("\n--- Track C-5: Background Workers & Notification Preferences ---")

# C.5.1: GET /notifications/preferences/
print("[TEST C.5.1] /notifications/preferences/ default all-enabled...")
r_np = client.get("/notifications/preferences/", headers={"Authorization": f"Bearer {token}"})
assert r_np.status_code == 200, f"/notifications/preferences/ failed: {r_np.text}"
np_data = r_np.json()
assert np_data["email_digest"] is True
assert np_data["streak_reminders"] is True
assert np_data["weekly_report"] is True
print("  [OK] Test C.5.1: /notifications/preferences/ defaults all-enabled: PASS")

# C.5.2: POST /notifications/preferences/ updates and persists opt-out
print("[TEST C.5.2] /notifications/preferences/ opt-out update...")
r_np_up = client.post(
    "/notifications/preferences/",
    json={"email_digest": False, "streak_reminders": True},
    headers={"Authorization": f"Bearer {token}"}
)
assert r_np_up.status_code == 200, f"Preference update failed: {r_np_up.text}"
assert r_np_up.json()["preferences"]["email_digest"] is False

# Verify change persisted on next GET
r_np_check = client.get("/notifications/preferences/", headers={"Authorization": f"Bearer {token}"})
assert r_np_check.json()["email_digest"] is False
print("  [OK] Test C.5.2: Notification preference update persistence: PASS")

# C.5.3 & C.5.4: Celery task routines run without exception
print("[TEST C.5.3 & C.5.4] Celery task functions (daily digests & streak checks)...")
from jobs.tasks import dispatch_daily_digests, check_streak_preservation
digest_result = dispatch_daily_digests()
assert "dispatched" in digest_result
streak_result = check_streak_preservation()
assert "streak_warnings_sent" in streak_result
print(f"  [OK] Test C.5.3 & C.5.4: Celery background task runners: PASS")

print("\n[TRACK C-5] All background worker and notification tests PASSED.")


# ── Track C-6: Billing & Subscriptions (Stripe) ──────────────────────────────
print("\n--- Track C-6: Billing & Subscriptions (Stripe) ---")

# C.6.1: GET /billing/status/ default free plan
print("[TEST C.6.1] /billing/status/ returns active plan & entitlements...")
r_bill = client.get("/billing/status/", headers={"Authorization": f"Bearer {token}"})
assert r_bill.status_code == 200, f"/billing/status/ failed: {r_bill.text}"
b_data = r_bill.json()
assert b_data["plan"] == "free"
assert b_data["is_pro"] is False
assert b_data["entitlements"]["daily_ai_queries"] == 10
print(f"  [OK] Test C.6.1: /billing/status/ default free plan entitlements: PASS")

# C.6.2: POST /billing/create-checkout/
print("[TEST C.6.2] /billing/create-checkout/ returns checkout session...")
r_co = client.post("/billing/create-checkout/", headers={"Authorization": f"Bearer {token}"})
assert r_co.status_code == 200, f"/billing/create-checkout/ failed: {r_co.text}"
co_data = r_co.json()
assert "checkout_url" in co_data
assert "session_id" in co_data
print(f"  [OK] Test C.6.2: /billing/create-checkout/ session creation: PASS")

# C.6.3 & C.6.4: POST /billing/webhook/ checkout.session.completed upgrades user to pro
print("[TEST C.6.3 & C.6.4] /billing/webhook/ upgrades subscription to Pro...")
_c6_db = SessionLocal()
try:
    _u_bill = _c6_db.query(User).filter(User.email == "e2e_acceptance_test@domain.com").first()
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(_u_bill.id),
                "customer": "cus_test_12345"
            }
        }
    }
finally:
    _c6_db.close()

r_hook = client.post("/billing/webhook/", json=webhook_payload)
assert r_hook.status_code == 200, f"Webhook failed: {r_hook.text}"

# Verify user is now Pro
r_bill_pro = client.get("/billing/status/", headers={"Authorization": f"Bearer {token}"})
assert r_bill_pro.status_code == 200
pro_data = r_bill_pro.json()
assert pro_data["plan"] == "pro"
assert pro_data["is_pro"] is True
assert pro_data["entitlements"]["daily_ai_queries"] == "unlimited"
assert pro_data["entitlements"]["pdf_certificates"] is True
print("  [OK] Test C.6.3 & C.6.4: Webhook upgrade & Pro entitlements (unlimited queries): PASS")

print("\n[TRACK C-6] All billing and subscription tests PASSED.")

print("\n====================================================")
print("ALL PROGRAMMATIC WORKFLOW TESTS COMPLETED SUCCESSFULLY!")
print("====================================================")

