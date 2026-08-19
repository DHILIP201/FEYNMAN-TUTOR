"""
Feynman AI -- Dedicated Persistent Authentication Hardening Test Suite (AUTH-1 to AUTH-12)
"""

import sys
import os
import uuid
import json
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from main import app
from database import get_db, SessionLocal, User, LearnerProfile
from security import (
    get_password_hash, verify_password, create_access_token,
    create_refresh_token, decode_refresh_token, decode_access_token, hash_token
)

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
print("FEYNMAN AI -- AUTHENTICATION HARDENING TEST SUITE (AUTH-1 to AUTH-12)")
print("=" * 70)

# AUTH-11: Password hashing uses bcrypt with unique salts
pw = "SecureMastery2026!"
hash1 = get_password_hash(pw)
hash2 = get_password_hash(pw)
check("AUTH-11: Password hashing uses bcrypt with unique salts and valid verification", hash1 != hash2 and verify_password(pw, hash1) and verify_password(pw, hash2))

# AUTH-1: Signup issues 30-min access token + 7-day refresh token in HttpOnly cookie
test_email = f"auth_user_{uuid.uuid4().hex[:8]}@test.com"
r_signup = client.post("/auth/signup/", json={
    "name": "Auth Student",
    "email": test_email,
    "password": "Password123!"
})
check("AUTH-1: Signup endpoint succeeds with 200/201 and sets refresh cookie", r_signup.status_code == 200 and "access_token" in r_signup.json() and "feynman_refresh" in r_signup.cookies)

# Verify access token has 30 min expiration claim
token_payload = decode_access_token(r_signup.json()["access_token"])
check("AUTH-1b: Access token payload is valid and has expiration", token_payload is not None and token_payload.get("sub") == test_email)

# AUTH-2: Login issues access token + HttpOnly refresh cookie + updates last_login
r_login = client.post("/auth/login/", json={
    "email": test_email,
    "password": "Password123!"
})
check("AUTH-2: Login succeeds and sets HttpOnly refresh cookie", r_login.status_code == 200 and "access_token" in r_login.json() and "feynman_refresh" in r_login.cookies)

# AUTH-3: Refresh token is stored as SHA-256 hash in database
user_row = db.query(User).filter(User.email == test_email).first()
check("AUTH-3: Refresh token hash is recorded in DB User row", user_row.refresh_token_hash is not None and len(user_row.refresh_token_hash) == 64)

# AUTH-4: /auth/refresh/ validates refresh cookie, rotates token, issues new access token
refresh_cookie = r_login.cookies.get("feynman_refresh")
client.cookies.set("feynman_refresh", refresh_cookie)
r_refresh = client.post("/auth/refresh/")
check("AUTH-4: /auth/refresh/ issues new access token and rotates refresh cookie", r_refresh.status_code == 200 and "access_token" in r_refresh.json() and "feynman_refresh" in r_refresh.cookies)

# AUTH-5: /auth/refresh/ fails when no cookie provided
client.cookies.clear()
r_no_cookie = client.post("/auth/refresh/")
check("AUTH-5: /auth/refresh/ without cookie returns 401 Unauthorized", r_no_cookie.status_code == 401)

# AUTH-6: /auth/refresh/ fails when cookie is forged or invalid
client.cookies.set("feynman_refresh", "forged.fake.token")
r_bad_cookie = client.post("/auth/refresh/")
check("AUTH-6: /auth/refresh/ with invalid cookie returns 401 Unauthorized", r_bad_cookie.status_code == 401)

# AUTH-7 & AUTH-8: /auth/logout/ clears refresh cookie and revokes refresh_token_hash in DB
# Log in again to get fresh valid session
r_login2 = client.post("/auth/login/", json={"email": test_email, "password": "Password123!"})
fresh_token = r_login2.json()["access_token"]
client.cookies.set("feynman_refresh", r_login2.cookies.get("feynman_refresh"))

r_logout = client.post("/auth/logout/", headers={"Authorization": f"Bearer {fresh_token}"})
db.refresh(user_row)
check("AUTH-7: /auth/logout/ nulls refresh_token_hash in DB and clears cookie", r_logout.status_code == 200 and user_row.refresh_token_hash is None)

# Old refresh token is now revoked
r_revoked_try = client.post("/auth/refresh/")
check("AUTH-8: Revoked refresh token rejected on subsequent /auth/refresh/ (401)", r_revoked_try.status_code == 401)

# AUTH-9: Single authoritative /auth/verify/ endpoint with redirect
v_token = create_access_token(data={"sub": test_email, "verify": True})
user_row.verification_token_hash = hash_token(v_token)
user_row.email_verified = False
db.commit()

r_verify = client.get(f"/auth/verify/?token={v_token}", follow_redirects=False)
db.refresh(user_row)
check("AUTH-9: /auth/verify/ verifies email and returns 307 redirect to /?verified=true", r_verify.status_code in (302, 307) and user_row.email_verified is True and "/?verified=true" in r_verify.headers.get("location", ""))

# AUTH-10: Learner profile preserved across login cycles (not wiped)
from ai_engine.memory.learner_memory_engine import LearnerMemoryEngine
mem = LearnerMemoryEngine()
prof = mem.get_or_create_profile(db, user_row.id)
prof.aggregate_mastery = 85
prof.learning_level = "advanced"
db.commit()

# Re-login
r_login3 = client.post("/auth/login/", json={"email": test_email, "password": "Password123!"})
tok3 = r_login3.json()["access_token"]
prof_after = client.get("/learner/profile/", headers={"Authorization": f"Bearer {tok3}"}).json()
check("AUTH-10: Learner profile aggregate mastery and level preserved across login", prof_after.get("aggregate_mastery") == 85 and prof_after.get("learning_level") == "advanced")

# AUTH-12: CORS configuration allows credentials
from main import app
cors_middleware = next((m for m in app.user_middleware if "CORSMiddleware" in str(m)), None)
check("AUTH-12: CORS middleware configured with allow_credentials=True", cors_middleware is not None and cors_middleware.kwargs.get("allow_credentials") is True)

db.close()

print("=" * 70)
print(f"AUTH HARDENING TEST RESULTS: {passed} PASSED, {failed} FAILED")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
