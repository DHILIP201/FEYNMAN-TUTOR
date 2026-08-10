import os
import io
import asyncio
import webbrowser
import threading
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai
from google.genai import types as genai_types
from pypdf import PdfReader
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import random
import secrets
from datetime import datetime, timedelta

# Import our custom modules
from database import init_db, SessionLocal, get_db, User, ChatSession, ChatMessage, PasswordResetOTP
from ai_engine import feynman_engine, gemini_gateway, rate_limiter, RateLimitTier
from security import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    decode_access_token, 
    get_current_user,
    check_password_strength,
    validate_email_format,
    hash_token
)
from rag import add_document_to_rag, query_rag

# Load environment variables
load_dotenv()
AVAILABLE_CHAT_MODELS = [os.getenv("GEMINI_MODEL", "gemini-flash-latest")]

# Full JSON schema for structured tutor responses
TUTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "simple_explanation": {"type": "string"},
        "why_it_works": {"type": "string"},
        "visual_intuition": {"type": "string"},
        "example": {"type": "string"},
        "common_mistake": {"type": "string"},
        "mini_quiz": {"type": "string"},
        "reflection_prompt": {"type": "string"},
        "coach_recommendation": {"type": "string"},
        "next_learning_step": {"type": "string"},
        "estimated_study_time": {"type": "integer"},
        "cognitive_trace": {"type": "string"},
        "mastery_score": {"type": "integer"}
    },
    "required": [
        "simple_explanation", "why_it_works", "visual_intuition",
        "example", "common_mistake", "mini_quiz", "reflection_prompt",
        "coach_recommendation", "next_learning_step", "estimated_study_time",
        "cognitive_trace", "mastery_score"
    ]
}

app = FastAPI(title="Feynman AI Tutor API")

# Security Headers & Abuse Protection Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates folders safely
try:
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
except Exception:
    pass

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- AUTO OPEN BROWSER LOGIC ---
def open_browser():
    time.sleep(1.5) # Wait for server to boot
    webbrowser.open("http://127.0.0.1:8000/")

@app.on_event("startup")
def startup_event():
    init_db()  # Initialize SQLite Tables
    
    # STEP 6: Verify startup parameters
    print("\n==========================================")
    print("FEYNMAN TUTOR SYSTEM STARTUP LOGS")
    print("==========================================")
    slots_count = len(gemini_gateway.key_pool.slots)
    avail_count = len(gemini_gateway.key_pool.get_available_slots())
    print(f"Gemini Key Pool: {slots_count} slots configured ({avail_count} active/healthy)")
    print(f"Selected model: {gemini_gateway.model_name}")
    print(f"AUTH_MODE: {os.getenv('AUTH_MODE', 'development')}")
    print("==========================================\n")
    
    # Pre-seed Guest Demo PDF for View Source Document action
    upload_dir = "/tmp/uploads" if os.getenv("VERCEL") == "1" else "static/uploads"
    try:
        os.makedirs(upload_dir, exist_ok=True)
        pdf_path = os.path.join(upload_dir, "session_rec.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 48 >>\nstream\nBT /F1 24 Tf 100 700 Td (Recursion Active Study Notes) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000062 00000 n\n0000000121 00000 n\n0000000222 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n321\n%%EOF\n")
    except Exception:
        pass
    
    # Pre-seed Guest Judge
    try:
        db = SessionLocal()
        guest = db.query(User).filter(User.email == "guest@feynmantutor.local").first()
        if not guest:
            guest = User(
                name="Guest Judge",
                email="guest@feynmantutor.local",
                hashed_password=get_password_hash("GuestPass1337!"),
                email_verified=True
            )
            db.add(guest)
            db.commit()
        db.close()
    except Exception as e:
        print(f"[STARTUP WARNING] DB pre-seed skipped: {e}")
        
    if os.getenv("VERCEL") != "1":
        threading.Thread(target=open_browser).start()

class TutorResponse(BaseModel):
    simple_explanation: str = Field(description="Comprehensive Socratic explanation using structured markdown (Step 1, Step 2, Step 3) with clear analogies.")
    why_it_works: str = Field(description="Conceptual logic and underlying mechanics.")
    visual_intuition: str = Field(description="Valid Mermaid graph definition (e.g. graph TD; A --> B;) or structured visual table.")
    example: str = Field(description="Clear real-life analogy.")
    common_mistake: str = Field(description="Typical pitfall or misconception point.")
    mini_quiz: str = Field(description="Conceptual query checking student understanding.")
    reflection_prompt: str = Field(description="Ask the student to explain the idea back or teach it.")
    coach_recommendation: str = Field(description="Customized coaching tip based on their current progress.")
    next_learning_step: str = Field(description="Preview of the next concept.")
    estimated_study_time: int = Field(description="Recommended session length in minutes for this topic.")
    cognitive_trace: str = Field(description="Reasoning reconstruction: reconstruct the student's reasoning, identify gaps, explain why that logic felt plausible, and guide to correct model.")
    mastery_score: int = Field(description="The updated mastery score of the student from 0 to 100.")

class UserSignup(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ResendVerificationRequest(BaseModel):
    email: str

class ForgotPasswordRequest(BaseModel):
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

class ResetPasswordRequest(BaseModel):
    email: str
    reset_token: str
    new_password: str

class SessionCreate(BaseModel):
    id: str
    title: str

class SessionRename(BaseModel):
    title: str

class ChatRequest(BaseModel):
    session_id: str
    user_message: str
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None

# --- FRONTEND ROUTE ---
@app.get("/", response_class=HTMLResponse)
async def get_frontend(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

def send_verification_email(to_email: str, name: str, token: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "verify@feynmantutor.local")
    
    host = os.getenv("APP_HOST", "http://127.0.0.1:8000")
    verify_url = f"{host}/auth/verify/?token={token}"
    
    is_local = os.getenv("IS_LOCAL_DEV", "true").lower() == "true"
    if is_local:
        print("\n=== LOCAL DEV EMAIL SENT ===")
        print(f"To: {to_email}")
        print(f"Subject: Verify your Feynman Tutor AI OS Account")
        print(f"Link: {verify_url}")
        print("============================\n")
        
    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Verify your Feynman Tutor AI OS Account"
            msg["From"] = smtp_from
            msg["To"] = to_email
            
            html = f"""
            <html>
              <body style="font-family: sans-serif; background-color: #0A0D14; color: #E2E8F0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #111622; border: 1px solid #1F293D; border-radius: 12px; padding: 30px;">
                  <h2 style="color: #6366F1; font-family: Outfit, sans-serif;">Welcome to Feynman Tutor AI OS!</h2>
                  <p>Hello {name},</p>
                  <p>Please click the button below to verify your account and initialize your learning OS profile. This verification link expires in 15 minutes.</p>
                  <div style="margin: 30px 0;">
                    <a href="{verify_url}" style="background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%); color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Verify Email</a>
                  </div>
                  <p style="font-size: 11px; color: #4B5563;">If you did not sign up for this service, please disregard this email.</p>
                </div>
              </body>
            </html>
            """
            msg.attach(MIMEText(html, "html"))
            
            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, to_email, msg.as_string())
        except Exception as e:
            print("SMTP Verification Send Error:", e)

# --- AUTH ENDPOINTS ---
@app.post("/auth/signup/")
async def signup(user_data: UserSignup, request: Request, db: Session = Depends(get_db)):
    # Rate Limit Signups (10 per minute per IP)
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, rl_info = rate_limiter.check_endpoint_rate_limit("signup", client_ip, max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many registration requests. Please wait {rl_info['retry_after']}s before trying again.",
            headers={"Retry-After": str(rl_info["retry_after"])}
        )

    # Validate Email Format
    if not validate_email_format(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email format you entered is invalid."
        )
    
    # Validate Password Strength
    if not check_password_strength(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters and include uppercase, lowercase, numbers, and symbols."
        )
        
    clean_email = user_data.email.strip().lower()
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )
    
    # Hash password and create user
    hashed_pw = get_password_hash(user_data.password)
    auth_mode = os.getenv("AUTH_MODE", "development").lower()
    is_dev = auth_mode == "development" or not os.getenv("SMTP_USER")
    
    new_user = User(
        name=user_data.name,
        email=clean_email,
        hashed_password=hashed_pw,
        email_verified=is_dev
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    if is_dev:
        access_token = create_access_token(data={"sub": new_user.email})
        return {
            "message": "User registered successfully (Development Mode).",
            "access_token": access_token,
            "user": {
                "name": new_user.name,
                "email": new_user.email
            }
        }
        
    # Generate verification token (Production Mode)
    verification_token = create_access_token(data={"sub": new_user.email, "verify": True})
    new_user.verification_token_hash = hash_token(verification_token)
    db.commit()
    
    # Send verification email via SMTP
    send_verification_email(new_user.email, new_user.name, verification_token)
    
    return {
        "message": "User registered successfully. A verification link has been sent to your email.",
        "user": {
            "name": new_user.name,
            "email": new_user.email
        }
    }

from datetime import timedelta

@app.get("/auth/verify/")
def verify_email(token: str, db: Session = Depends(get_db)):
    token_hash = hash_token(token)
    user = db.query(User).filter(User.verification_token_hash == token_hash).first()
    
    if not user:
        return HTMLResponse(content="""
        <html>
          <body style="font-family: sans-serif; background-color: #0A0D14; color: #E2E8F0; text-align: center; padding: 50px;">
            <div style="max-width: 500px; margin: 0 auto; background-color: #111622; border: 1px solid #EF4444; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
              <h2 style="color: #EF4444;">Verification Failed</h2>
              <p>This verification link is invalid or has already been used.</p>
              <a href="/" style="color: #6366F1; text-decoration: underline;">Go back to Login</a>
            </div>
          </body>
        </html>
        """, status_code=400)
        
    # Check expiration (15 minutes)
    expiration_time = timedelta(minutes=15)
    if datetime.utcnow() - user.updated_at > expiration_time:
        return HTMLResponse(content="""
        <html>
          <body style="font-family: sans-serif; background-color: #0A0D14; color: #E2E8F0; text-align: center; padding: 50px;">
            <div style="max-width: 500px; margin: 0 auto; background-color: #111622; border: 1px solid #F59E0B; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
              <h2 style="color: #F59E0B;">Link Expired</h2>
              <p>This verification link has expired (15 minutes limit). Please log in and request a new link.</p>
              <a href="/" style="color: #6366F1; text-decoration: underline;">Go back to Login</a>
            </div>
          </body>
        </html>
        """, status_code=400)
        
    # Verify user
    user.email_verified = True
    user.verification_token_hash = None
    db.commit()
    
    # Redirect to home page with verified flag
    return RedirectResponse(url="/?verified=true")

@app.post("/auth/resend/")
def resend_verification(request: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not registered with this email.")
    if user.email_verified:
        return {"message": "Email is already verified. Please log in."}
        
    token = create_access_token(data={"sub": user.email, "verify": True})
    user.verification_token_hash = hash_token(token)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    send_verification_email(user.email, user.name, token)
    return {"message": "Verification email resent successfully."}

@app.post("/auth/login/")
async def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    clean_email = credentials.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    
    # Anti-Brute-Force Rate Limit (15 attempts / minute per IP)
    is_allowed, rl_info = rate_limiter.check_endpoint_rate_limit("login", client_ip, max_requests=15, window_seconds=60)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please wait {rl_info['retry_after']}s before trying again.",
            headers={"Retry-After": str(rl_info["retry_after"])}
        )

    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        print(f"[AUTH LOGIN FAIL] User not found: {clean_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The email or password you entered is incorrect."
        )
        
    pw_match = verify_password(credentials.password, user.hashed_password)
    if not pw_match:
        print(f"[AUTH LOGIN FAIL] Password mismatch for user: {clean_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The email or password you entered is incorrect."
        )
    
    # Auto-verify email if SMTP user is not set or in development mode
    if not user.email_verified:
        if not os.getenv("SMTP_USER"):
            user.email_verified = True
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please verify your email before signing in."
            )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create JWT token
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "name": user.name,
            "email": user.email
        }
    }

@app.post("/auth/guest/")
async def guest_login(request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, rl_info = rate_limiter.check_endpoint_rate_limit("guest_login", client_ip, max_requests=20, window_seconds=60)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many guest sessions requested. Please wait {rl_info['retry_after']}s before trying again.",
            headers={"Retry-After": str(rl_info["retry_after"])}
        )

    # Retrieve Guest user
    guest = db.query(User).filter(User.email == "guest@feynmantutor.local").first()
    if not guest:
        # Create fallback if deleted
        guest = User(
            name="Guest Judge",
            email="guest@feynmantutor.local",
            hashed_password=get_password_hash("GuestPass1337!"),
            email_verified=True
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)
        
    access_token = create_access_token(data={"sub": guest.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "name": guest.name,
            "email": guest.email
        }
    }

@app.post("/auth/resend-verification/")
async def resend_verification(req: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email address not found.")
    
    if user.email_verified:
        return {"message": "Email is already verified. You can log in directly."}
        
    # Generate new token
    verification_token = create_access_token(data={"sub": user.email, "verify": True})
    user.verification_token_hash = hash_token(verification_token)
    db.commit()
    
    simulated_link = f"http://127.0.0.1:8000/auth/verify/?token={verification_token}"
    print(f"\n[EMAIL SIMULATOR] Resent verification link to {user.email}:\n{simulated_link}\n")
    
    return {
        "message": "Verification link has been sent.",
        "verification_link": simulated_link
    }

@app.post("/auth/forgot-password/")
async def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    # Rate Limit Password Reset (5 requests / 5 min)
    is_allowed, rl_info = rate_limiter.check_endpoint_rate_limit("forgot_password", f"{client_ip}:{req.email}", max_requests=5, window_seconds=300)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many password reset requests. Please wait {rl_info['retry_after']}s before trying again.",
            headers={"Retry-After": str(rl_info["retry_after"])}
        )

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        # Anti-enumeration response format
        return {
            "message": "If an account exists for this email, a 6-digit verification code has been sent.",
            "cooldown": 60
        }

    # Invalidate previous unused OTPs for this email
    db.query(PasswordResetOTP).filter(PasswordResetOTP.email == req.email, PasswordResetOTP.is_used == False).update({"is_used": True})
    
    # Generate secure 6-digit OTP
    otp_code = f"{random.randint(100000, 999999)}"
    otp_hash = hash_token(otp_code)
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    reset_entry = PasswordResetOTP(
        email=req.email,
        otp_hash=otp_hash,
        expires_at=expires_at,
        attempts=0,
        is_used=False
    )
    db.add(reset_entry)
    db.commit()
    
    print(f"\n==========================================")
    print(f"[SECURITY OTP SIMULATOR] Sent Password Reset OTP '{otp_code}' to {req.email}")
    print(f"Expires at: {expires_at} UTC (10 mins valid)")
    print(f"==========================================\n")
    
    return {
        "message": f"Verification code sent to {req.email}. (Demo OTP: {otp_code})",
        "cooldown": 60
    }

@app.post("/auth/verify-otp/")
async def verify_otp(req: VerifyOTPRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    # Rate Limit OTP Verification (10 attempts / 5 min)
    is_allowed, rl_info = rate_limiter.check_endpoint_rate_limit("verify_otp", f"{client_ip}:{req.email}", max_requests=10, window_seconds=300)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many verification attempts. Please wait {rl_info['retry_after']}s before trying again.",
            headers={"Retry-After": str(rl_info["retry_after"])}
        )
    reset_entry = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == req.email,
        PasswordResetOTP.is_used == False
    ).order_by(PasswordResetOTP.created_at.desc()).first()

    if not reset_entry:
        raise HTTPException(status_code=400, detail="No active password reset request found. Please request a new code.")

    if reset_entry.expires_at < datetime.utcnow():
        reset_entry.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")

    if reset_entry.attempts >= 5:
        reset_entry.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Maximum verification attempts exceeded. Please request a new code.")

    # Check OTP hash match
    input_otp_hash = hash_token(req.otp.strip())
    if reset_entry.otp_hash != input_otp_hash:
        reset_entry.attempts += 1
        db.commit()
        remaining = 5 - reset_entry.attempts
        raise HTTPException(status_code=400, detail=f"Invalid verification code. {remaining} attempt(s) remaining.")

    # Generate single-use reset token
    reset_token = secrets.token_hex(32)
    reset_entry.reset_token = reset_token
    db.commit()

    return {
        "message": "Verification code confirmed successfully.",
        "reset_token": reset_token
    }

@app.post("/auth/reset-password/")
async def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    pw = req.new_password
    # Validate password strength: min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char
    if len(pw) < 8 or not any(c.isupper() for c in pw) or not any(c.islower() for c in pw) or not any(c.isdigit() for c in pw) or not any(not c.isalnum() for c in pw):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one number, and one special character."
        )

    reset_entry = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == req.email,
        PasswordResetOTP.reset_token == req.reset_token,
        PasswordResetOTP.is_used == False
    ).first()

    if not reset_entry or reset_entry.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired password reset session. Please start over.")

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # Update password and invalidate all OTP reset tokens for this user
    user.hashed_password = get_password_hash(pw)
    db.query(PasswordResetOTP).filter(PasswordResetOTP.email == req.email).update({"is_used": True})
    db.commit()

    return {"message": "Password updated successfully."}

@app.get("/auth/verify/", response_class=HTMLResponse)
async def verify_email(token: str, db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload or not payload.get("verify"):
        return """
        <html>
            <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #F9FAFB;">
                <div style="background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 400px;">
                    <div style="font-size: 48px; color: #EF4444; margin-bottom: 20px;">⚠️</div>
                    <h2 style="color: #111827; margin-bottom: 10px;">Verification Failed</h2>
                    <p style="color: #6B7280; font-size: 14px; line-height: 1.5;">The verification link is invalid or has expired.</p>
                </div>
            </body>
        </html>
        """
    
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return "User not found."
        
    # Verify hashed token match
    token_hash = hash_token(token)
    if user.verification_token_hash != token_hash:
        return """
        <html>
            <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #F9FAFB;">
                <div style="background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 400px;">
                    <div style="font-size: 48px; color: #EF4444; margin-bottom: 20px;">⚠️</div>
                    <h2 style="color: #111827; margin-bottom: 10px;">Already Verified or Invalid</h2>
                    <p style="color: #6B7280; font-size: 14px; line-height: 1.5;">This link has already been used or is no longer valid.</p>
                </div>
            </body>
        </html>
        """
        
    user.email_verified = True
    user.verification_token_hash = None
    db.commit()
    
    return """
    <html>
        <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #F9FAFB;">
            <div style="background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 400px;">
                <div style="font-size: 48px; color: #10B981; margin-bottom: 20px;">✅</div>
                <h2 style="color: #111827; margin-bottom: 10px;">Verification Successful!</h2>
                <p style="color: #6B7280; font-size: 14px; line-height: 1.5; margin-bottom: 24px;">Your email address has been successfully verified. You can now close this tab and return to the Feynman Tutor AI to sign in.</p>
                <div style="color: #6366F1; font-weight: 600; font-size: 14px;">Happy Active Learning!</div>
            </div>
        </body>
    </html>
    """

# --- CHAT SESSION ENDPOINTS ---
@app.get("/sessions/")
async def get_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "mastery": s.mastery,
            "has_doc": s.has_doc,
            "study_mode": s.study_mode,
            "created_at": s.created_at.isoformat()
        } for s in sessions
    ]

@app.post("/sessions/")
async def create_session(session_data: SessionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if session already exists
    session = db.query(ChatSession).filter(ChatSession.id == session_data.id).first()
    if session:
        return {"message": "Session already exists"}
        
    new_session = ChatSession(
        id=session_data.id,
        user_id=current_user.id,
        title=session_data.title,
        mastery=0,
        has_doc=False,
        study_mode="Focus"
    )
    db.add(new_session)
    db.commit()
    return {"message": "Session created successfully", "id": new_session.id}

@app.get("/sessions/{session_id}/messages/")
async def get_session_messages(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Ensure session belongs to user
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    return [
        {
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        } for m in messages
    ]

@app.put("/sessions/{session_id}")
async def rename_session(session_id: str, session_update: SessionRename, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.title = session_update.title
    db.commit()
    return {"message": "Session renamed successfully"}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    db.delete(session)
    db.commit()
    
    # Also clean up ChromaDB collection if RAG exists
    try:
        from rag import chroma_client, get_collection_name
        chroma_client.delete_collection(name=get_collection_name(session_id))
    except Exception:
        pass
        
    return {"message": "Session deleted successfully"}

@app.get("/users/stats/")
def get_user_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Fetch sessions
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).all()
    session_ids = [s.id for s in sessions]
    
    # 2. Calculate Mastery stats
    mastery_scores = [s.mastery for s in sessions if s.mastery > 0]
    avg_mastery = int(sum(mastery_scores) / len(mastery_scores)) if mastery_scores else 0
    
    # 3. Calculate dynamic XP
    # Base user XP + active session masteries
    total_xp = current_user.xp + sum(mastery_scores) * 10
    
    # 4. Study Time Today
    # Count messages sent today * 3 minutes
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_msgs_count = db.query(ChatMessage)\
        .filter(ChatMessage.session_id.in_(session_ids))\
        .filter(ChatMessage.created_at >= today_start)\
        .count() if session_ids else 0
    study_time = max(today_msgs_count * 3, 0)
    
    # 5. Weak and Strong concepts
    weak_concepts = []
    strong_concepts = []
    
    for sess in sessions:
        concept_name = sess.title.replace(".pdf", "")
        if sess.mastery >= 70:
            strong_concepts.append(concept_name)
        elif sess.mastery > 0 and sess.mastery < 50:
            weak_concepts.append(concept_name)
            
    # Default tags if lists are empty but sessions exist
    if not weak_concepts and sessions:
        weak_concepts.append("Halting bounds")
    if not strong_concepts and sessions:
        strong_concepts.append("Basic logic")
        
    # 6. Timeline events
    timeline = []
    for sess in sessions:
        timeline.append({
            "title": "Document Indexed",
            "description": f"Successfully indexed {sess.title}. Mastery at {sess.mastery}%.",
            "time": sess.created_at.strftime("%Y-%m-%d %H:%M"),
            "xp": 100
        })
        
    # Sort timeline by time desc
    timeline = sorted(timeline, key=lambda x: x["time"], reverse=True)[:5]
    
    retention_index = min(int(avg_mastery * 0.95 + current_user.current_streak * 2), 99)
    if avg_mastery == 0:
        retention_index = 0

    return {
        "current_streak": current_user.current_streak,
        "longest_streak": current_user.longest_streak,
        "study_time_today": study_time,
        "quiz_accuracy": avg_mastery if avg_mastery > 0 else 0,
        "mastery_percentage": avg_mastery,
        "xp": total_xp,
        "retention_index": f"High ({retention_index}%)" if retention_index > 50 else (f"Medium ({retention_index}%)" if retention_index > 0 else "0%"),
        "weak_concepts": weak_concepts,
        "strong_concepts": strong_concepts,
        "timeline": timeline
    }

# --- TUTORING / FILE ENDPOINTS ---
@app.post("/upload-document/")
async def upload_document(
    session_id: str = Form(...), 
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Rate Limit Uploads (10 uploads / minute per user)
    user_id_str = f"user_{current_user.id}"
    is_allowed, rl_info = rate_limiter.check_endpoint_rate_limit("upload_document", user_id_str, max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Upload rate limit exceeded. Please wait {rl_info['retry_after']}s before uploading another document.",
            headers={"Retry-After": str(rl_info["retry_after"])}
        )

    # 2. Filename & Path Sanitization
    import os
    safe_filename = os.path.basename(file.filename or "document.pdf").replace("\x00", "")
    if not safe_filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Check if session exists or create it
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        session = ChatSession(
            id=session_id,
            user_id=current_user.id,
            title=safe_filename,
            mastery=0,
            has_doc=True,
            study_mode="Focus"
        )
        db.add(session)
    else:
        session.title = safe_filename
        session.has_doc = True
        
    try:
        contents = await file.read()

        # 3. File Size Validation (Max 15 MB)
        if len(contents) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File size exceeds maximum allowable limit (15 MB).")

        # 4. MIME Magic Bytes Validation (%PDF-)
        if not contents.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file format. Missing PDF signature.")

        pdf_reader = PdfReader(io.BytesIO(contents))
        pages_data = []
        for idx, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                pages_data.append({
                    "text": page_text,
                    "page_num": idx + 1,
                    "filename": file.filename
                })
        
        # Feed text pages list to RAG module
        add_document_to_rag(session_id, pages_data)
        
        # Save PDF copy locally or to /tmp for viewing
        upload_dir = "/tmp/uploads" if os.getenv("VERCEL") == "1" else "static/uploads"
        try:
            os.makedirs(upload_dir, exist_ok=True)
            pdf_path = os.path.join(upload_dir, f"{session_id}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(contents)
        except Exception as save_err:
            print(f"[UPLOAD WARNING] Could not write PDF copy to disk: {save_err}")
            
        # Save updates to DB
        db.commit()
        
        # Calculate chunks count for front-end reporting
        from rag import chunk_text
        chunk_count = sum(len(chunk_text(page["text"])) for page in pages_data)
        
        return {
            "message": f"Successfully processed and indexed {file.filename}",
            "filename": file.filename,
            "pages": len(pages_data),
            "chunks": chunk_count,
            "status": "Indexed successfully",
            "text_preview": pages_data[0]["text"][:200] if pages_data else ""
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

from fastapi.responses import FileResponse

@app.get("/static/uploads/{filename}")
async def serve_uploaded_pdf(filename: str):
    upload_dir = "/tmp/uploads" if os.getenv("VERCEL") == "1" else "static/uploads"
    file_path = os.path.join(upload_dir, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/pdf")
    static_fallback = os.path.join("static/uploads", filename)
    if os.path.exists(static_fallback):
        return FileResponse(static_fallback, media_type="application/pdf")
    raise HTTPException(status_code=404, detail="PDF document not found")

@app.post("/tutor-chat/")
async def tutor_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Tiered Sliding-Window Rate Limiting & Daily AI Budgeting
    user_tier = RateLimitTier.GUEST if current_user.email == "guest@feynmantutor.local" else RateLimitTier.FREE
    user_id_str = f"user_{current_user.id}"

    # 1. Check Requests-Per-Minute Rate Limit
    is_allowed, rl_info = rate_limiter.check_rate_limit(user_id_str, tier=user_tier)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for {user_tier} tier ({rl_info['limit']} req/min). Please wait {rl_info['retry_after']}s before sending another message.",
            headers={
                "Retry-After": str(rl_info["retry_after"]),
                "X-RateLimit-Limit": str(rl_info["limit"]),
                "X-RateLimit-Remaining": "0"
            }
        )

    # 2. Check Daily Token & Query Budget
    budget_allowed, budget_info = rate_limiter.check_budget(user_id_str, estimated_tokens=600, tier=user_tier)
    if not budget_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily AI study budget reached for {user_tier} tier ({budget_info['daily_requests_used']}/{budget_info['daily_requests_limit']} daily requests). Resets at midnight UTC.",
            headers={"X-TokenBudget-Remaining": "0"}
        )

    # Ensure session exists and belongs to the user
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        # If it doesn't exist, create it as a text-only chat
        session = ChatSession(
            id=request.session_id,
            user_id=current_user.id,
            title=request.user_message[:25] + "...",
            mastery=0,
            has_doc=False,
            study_mode="Focus"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
    if not session.has_doc:
        msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == request.session_id).count()
        if msg_count == 0:
            raise HTTPException(status_code=400, detail="NO_DOCUMENT")

    user_message = request.user_message
    
    # Save user message to database
    user_chat_msg = ChatMessage(
        session_id=request.session_id,
        role="user",
        content=user_message
    )
    db.add(user_chat_msg)
    
    # Calculate and update streak
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if current_user.last_study_date != today_str:
        if current_user.last_study_date:
            try:
                last_date = datetime.strptime(current_user.last_study_date, "%Y-%m-%d")
                delta = datetime.utcnow() - last_date
                if delta.days == 1:
                    current_user.current_streak += 1
                else:
                    # Reset streak if they missed a day
                    current_user.current_streak = 1
            except Exception:
                current_user.current_streak = 1
        else:
            current_user.current_streak = 1
            
        current_user.last_study_date = today_str
        current_user.longest_streak = max(current_user.longest_streak, current_user.current_streak)
        current_user.xp += 100  # XP bonus for daily streak
        
    current_user.xp += 15  # Normal XP gain for messaging
    db.commit()
    
    # Fetch chat history for Gemini context
    history_msgs = db.query(ChatMessage)\
        .filter(ChatMessage.session_id == request.session_id)\
        .order_by(ChatMessage.created_at.asc())\
        .all()

    # Scan history for previous cognitive traces/mistakes to construct active learning memory
    previous_mistakes = []
    for m in history_msgs:
        if m.role == "model" or m.role == "ai":
            try:
                data = json.loads(m.content)
                cog = data.get("cognitive_trace", "")
                if cog:
                    previous_mistakes.append(cog)
            except Exception:
                pass
    
    mistakes_text = "\n".join([f"- {m}" for m in previous_mistakes[-3:]]) if previous_mistakes else "No previous misconceptions recorded in this session."
    
    # Query ChromaDB for top relevant context chunks
    context_chunks = query_rag(request.session_id, user_message, n_results=4)
    
    # Flatten dicts into ground truth text with page citations
    context_text = ""
    sources_citation = []
    for idx, chunk in enumerate(context_chunks):
        filename = chunk.get("filename", "document.pdf")
        page_num = chunk.get("page", 1)
        text_content = chunk.get("text", "")
        
        context_text += f"Context Block {idx+1} (Source: {filename} - Page {page_num}):\n{text_content}\n---\n"
        sources_citation.append({
            "filename": filename,
            "page": page_num
        })
        
    if not context_text:
        if session.has_doc:
            context_text = f"The student HAS uploaded a PDF document titled '{session.title}' for this study session. Explain the topic comprehensively using pedagogical best practices."
        else:
            context_text = "No document attached to this session. Answer from your knowledge and guide the student."

    # STAGE 1 & 2: Clean Topic & Formulate LearningPlan via FeynmanCognitiveEngine
    import re
    cleaned_user_topic = re.sub(
        r'^(Teach me step by step until I understand|Explain this concept even simpler|Give a real world analogy|Tell me about|Understanding how the|Understanding|Explain what is|What is)\s+',
        '',
        request.user_message,
        flags=re.IGNORECASE
    ).strip()
    if not cleaned_user_topic:
        cleaned_user_topic = request.user_message

    learning_plan = feynman_engine.plan_learning_strategy(
        user_message=cleaned_user_topic,
        current_mastery=session.mastery,
        study_mode=session.study_mode
    )
    system_prompt = feynman_engine.prepare_system_prompt(
        plan=learning_plan,
        mistakes_text=mistakes_text,
        context_text=context_text
    )

    try:
        # Build conversation history for Gemini
        contents = []
        for i, m in enumerate(history_msgs):
            role = "model" if m.role in ("model", "ai") else "user"
            content_text = m.content

            # Summarize previous AI JSON responses into natural text for context
            if role == "model":
                try:
                    d = json.loads(content_text)
                    exp = d.get("simple_explanation", "")
                    quiz = d.get("mini_quiz", "")
                    refl = d.get("reflection_prompt", "")
                    content_text = f"{exp}\n\nQuiz I asked: {quiz}\n\nReflection I asked: {refl}"
                except Exception:
                    pass

            # Attach image to last user message if provided
            if i == len(history_msgs) - 1 and role == "user" and request.image_base64 and request.image_mime:
                try:
                    image_bytes = base64.b64decode(request.image_base64)
                    contents.append(genai_types.Content(
                        role=role,
                        parts=[
                            genai_types.Part.from_bytes(data=image_bytes, mime_type=request.image_mime),
                            genai_types.Part.from_text(text=content_text)
                        ]
                    ))
                    continue
                except Exception:
                    pass

            contents.append(genai_types.Content(
                role=role,
                parts=[genai_types.Part.from_text(text=content_text)]
            ))

        import traceback
        t0 = time.time()

        global AVAILABLE_CHAT_MODELS
        models_failover = AVAILABLE_CHAT_MODELS
        selected_model = None
        response = None
        # Generate structured response via resilient Gemini API Gateway
        raw_text = await gemini_gateway.generate(
            contents=contents,
            system_instruction=system_prompt,
            response_schema=TUTOR_SCHEMA,
            temperature=0.7,
            request_id=request.session_id[:8]
        )

        if not raw_text:
            print("[MODEL PIPELINE] Gemini Gateway slots exhausted. Returning structured fallback tutor response...")
            tutor_data = feynman_engine.get_fallback_document(
                user_message=request.user_message,
                current_mastery=session.mastery,
                sources=sources_citation
            )
            session.mastery = tutor_data["mastery_score"]
            ai_chat_msg = ChatMessage(
                session_id=request.session_id,
                role="model",
                content=json.dumps(tutor_data)
            )
            db.add(ai_chat_msg)
            db.commit()
            return tutor_data

        # Parse and validate full JSON response through canonical validator
        try:
            raw_json = json.loads(raw_text)
        except Exception:
            # If JSON parsing failed, use structured fallback document
            tutor_data = feynman_engine.get_fallback_document(
                user_message=request.user_message,
                current_mastery=session.mastery,
                sources=sources_citation
            )
            session.mastery = tutor_data["mastery_score"]
            ai_chat_msg = ChatMessage(
                session_id=request.session_id,
                role="model",
                content=json.dumps(tutor_data)
            )
            db.add(ai_chat_msg)
            db.commit()
            return tutor_data

        raw_json["sources"] = sources_citation
        raw_json["canonical_topic"] = cleaned_user_topic
        tutor_doc = feynman_engine.validate_and_build_document(raw_json, session.mastery)
        tutor_data = tutor_doc.model_dump()
        tutor_data["blocks"] = feynman_engine.build_document_blocks(tutor_data)
        mastery_score = int(tutor_data.get("mastery_score", session.mastery))

        # Update session mastery
        session.mastery = mastery_score

        ai_chat_msg = ChatMessage(
            session_id=request.session_id,
            role="model",
            content=json.dumps(tutor_data)
        )
        db.add(ai_chat_msg)
        db.commit()

        # Record actual Gemini token usage into rate limiter ledger
        actual_tokens = gemini_gateway.get_last_token_count() or (len(raw_text.split()) * 2 if raw_text else 600)
        rate_limiter.record_actual_token_usage(
            user_id_str,
            actual_tokens=actual_tokens,
            estimated_tokens=600,
            tier=user_tier
        )

        return tutor_data

    except Exception as e:
        db.rollback()
        try:
            db.delete(user_chat_msg)
            db.commit()
        except Exception:
            pass
        print(f"[TUTOR-CHAT ERROR] {type(e).__name__}: {e}")
        import traceback
        full_tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "exception_type": type(e).__name__,
                "message": str(e),
                "traceback": full_tb
            }
        )

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)