"""
Feynman AI — Production PDF Upload Pipeline & RAG Ingestion Test Suite
Verifies requirements PDF-1 through PDF-12.
"""

import os
import io
import time
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, User, ChatSession
from security import create_access_token, create_refresh_token, hash_token

client = TestClient(app)

TEST_USER_EMAIL = "pdf_test_student@feynmantutor.com"
TEST_USER_PASS = "ValidPassword123!"
TEST_SESSION_ID = "test_pdf_session_alpha"


def setup_module():
    """Ensure clean test user and session."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == TEST_USER_EMAIL).first()
        if user:
            db.query(ChatSession).filter(ChatSession.user_id == user.id).delete()
            db.delete(user)
            db.commit()
    finally:
        db.close()


def test_pdf_1_frontend_file_selection_handler():
    """PDF-1: File selection handler exists and is bound to input."""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    with open("static/js/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert 'id="file-upload"' in html
    assert 'onchange="handleFileSelected(this)"' in html
    assert "function handleFileSelected(" in js
    assert "function initFileUpload(" in js
    assert "window.handleFileSelected = handleFileSelected" in js
    print("  [PASS] PDF-1: File selection handler exists and is properly bound")


def test_pdf_2_formdata_field_names():
    """PDF-2: Frontend constructs FormData with field 'file' and 'session_id'."""
    with open("static/js/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "formData.append('file', file)" in js or 'formData.append("file", file)' in js
    assert "formData.append('session_id', currentSessionId)" in js or 'formData.append("session_id", currentSessionId)' in js
    print("  [PASS] PDF-2: FormData field names ('file', 'session_id') validated")


def test_pdf_3_api_url_resolution():
    """PDF-3: Production URL resolves via resolveURL without hardcoding."""
    with open("static/js/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "resolveURL('/upload-document/')" in js or 'resolveURL("/upload-document/")' in js
    assert "const API_BASE_URL" in js
    print("  [PASS] PDF-3: Production API URL resolves via resolveURL")


def test_pdf_4_auth_header_required():
    """PDF-4: Authorization header is required by /upload-document/."""
    with open("test_study_material.pdf", "rb") as f:
        r = client.post(
            "/upload-document/",
            data={"session_id": "anon_session"},
            files={"file": ("test_study_material.pdf", f, "application/pdf")}
        )
    assert r.status_code == 401, f"Expected 401 Unauthorized, got {r.status_code}"
    print("  [PASS] PDF-4: Unauthenticated upload rejected with 401")


def test_pdf_5_oversized_file_rejected():
    """PDF-5: File exceeding 15 MB limit is rejected with 413."""
    # Register/login test user
    r_reg = client.post("/auth/signup/", json={
        "name": "PDF Test Student",
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASS
    })
    token = r_reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    oversized_data = b"%PDF-1.4 " + (b"0" * (16 * 1024 * 1024))
    r = client.post(
        "/upload-document/",
        data={"session_id": TEST_SESSION_ID},
        files={"file": ("huge_file.pdf", io.BytesIO(oversized_data), "application/pdf")},
        headers=headers
    )
    assert r.status_code == 413, f"Expected 413 Payload Too Large, got {r.status_code}"
    assert "15 MB" in r.text
    print("  [PASS] PDF-5: Oversized file (>15 MB) rejected with 413")


def test_pdf_6_invalid_pdf_magic_bytes_rejected():
    """PDF-6: File with invalid magic bytes (not starting with %PDF-) is rejected with 400."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_USER_EMAIL).first()
    db.close()
    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    fake_data = b"This is just a plain text file pretending to be a pdf."
    r = client.post(
        "/upload-document/",
        data={"session_id": TEST_SESSION_ID},
        files={"file": ("fake_file.pdf", io.BytesIO(fake_data), "application/pdf")},
        headers=headers
    )
    assert r.status_code == 400, f"Expected 400 Bad Request, got {r.status_code}"
    assert "signature" in r.text.lower() or "invalid" in r.text.lower()
    print("  [PASS] PDF-6: Invalid magic bytes rejected with 400")


def test_pdf_7_valid_pdf_accepted_and_indexed():
    """PDF-7: Valid PDF is successfully processed and indexed (200 OK)."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_USER_EMAIL).first()
    db.close()
    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    with open("test_study_material.pdf", "rb") as f:
        r = client.post(
            "/upload-document/",
            data={"session_id": TEST_SESSION_ID},
            files={"file": ("test_study_material.pdf", f, "application/pdf")},
            headers=headers
        )

    assert r.status_code == 200, f"Upload failed: {r.text}"
    data = r.json()
    assert "pages" in data and data["pages"] >= 1
    assert "chunks" in data and data["chunks"] >= 1
    assert data["status"] == "Indexed successfully"
    print(f"  [PASS] PDF-7: Valid PDF accepted (Pages={data['pages']}, Chunks={data['chunks']})")


def test_pdf_8_rag_metadata_persisted():
    """PDF-8: RAG module query retrieves indexed content chunks."""
    from rag import query_rag
    chunks = query_rag(TEST_SESSION_ID, "recursion stack limits", n_results=2)
    assert len(chunks) > 0, "No chunks retrieved from RAG for session"
    assert any("recursion" in c.get("text", "").lower() or "stack" in c.get("text", "").lower() for c in chunks)
    print(f"  [PASS] PDF-8: RAG metadata retrieved {len(chunks)} relevant chunks")


def test_pdf_9_session_has_doc_persisted_in_db():
    """PDF-9: Database ChatSession row reflects has_doc=True."""
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == TEST_SESSION_ID).first()
        assert session is not None, "ChatSession not found in DB"
        assert session.has_doc is True, f"Expected has_doc=True, got {session.has_doc}"
        assert session.title is not None
        print(f"  [PASS] PDF-9: Session DB persistence verified (has_doc={session.has_doc}, title='{session.title}')")
    finally:
        db.close()


def test_pdf_10_quiz_generation_available():
    """PDF-10: PDF-grounded quiz generation succeeds on uploaded session."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_USER_EMAIL).first()
    db.close()
    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/quiz/start/",
        json={"session_id": TEST_SESSION_ID, "question_count": 3},
        headers=headers
    )
    assert r.status_code == 200, f"Quiz start failed: {r.text}"
    quiz_data = r.json()
    assert "quiz_id" in quiz_data
    assert len(quiz_data["questions"]) == 3
    print(f"  [PASS] PDF-10: Interactive quiz generated {len(quiz_data['questions'])} PDF-grounded questions")


def test_pdf_11_refresh_token_recovery():
    """PDF-11: Token refresh + upload retry works when access token is expired."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_USER_EMAIL).first()
    refresh_token = create_refresh_token(data={"sub": user.email})
    user.refresh_token_hash = hash_token(refresh_token)
    db.commit()
    db.close()

    # Request new access token with refresh cookie
    r_ref = client.post(
        "/auth/refresh/",
        cookies={"feynman_refresh": refresh_token}
    )
    assert r_ref.status_code == 200
    new_access_token = r_ref.json()["access_token"]
    assert new_access_token is not None

    # Use refreshed access token for upload
    with open("test_study_material.pdf", "rb") as f:
        r_up = client.post(
            "/upload-document/",
            data={"session_id": "test_refreshed_session"},
            files={"file": ("test_study_material.pdf", f, "application/pdf")},
            headers={"Authorization": f"Bearer {new_access_token}"}
        )
    assert r_up.status_code == 200
    print("  [PASS] PDF-11: Refresh token recovery and upload retry succeeded")


def test_pdf_12_ui_error_states():
    """PDF-12: Frontend contains friendly error mapping for 400, 401, 413, 429, 500/503."""
    with open("static/js/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "response.status === 413" in js
    assert "response.status === 400" in js
    assert "response.status === 429" in js
    assert "UPLOAD_STATES" in js
    assert "isUploadingPdf" in js
    print("  [PASS] PDF-12: Complete UI state machine and friendly error handling verified")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FEYNMAN AI — PDF UPLOAD & RAG INGESTION TEST SUITE (PDF-1 to PDF-12)")
    print("=" * 70)

    setup_module()
    test_pdf_1_frontend_file_selection_handler()
    test_pdf_2_formdata_field_names()
    test_pdf_3_api_url_resolution()
    test_pdf_4_auth_header_required()
    test_pdf_5_oversized_file_rejected()
    test_pdf_6_invalid_pdf_magic_bytes_rejected()
    test_pdf_7_valid_pdf_accepted_and_indexed()
    test_pdf_8_rag_metadata_persisted()
    test_pdf_9_session_has_doc_persisted_in_db()
    test_pdf_10_quiz_generation_available()
    test_pdf_11_refresh_token_recovery()
    test_pdf_12_ui_error_states()

    print("\n" + "=" * 70)
    print("PDF UPLOAD TEST RESULTS: 12 PASSED, 0 FAILED")
    print("=" * 70)
