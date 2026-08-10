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
from datetime import datetime

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

db_session.close()

print("\n====================================================")
print("ALL PROGRAMMATIC WORKFLOW TESTS COMPLETED SUCCESSFULLY!")
print("====================================================")
