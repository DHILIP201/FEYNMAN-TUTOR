import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

is_vercel = os.getenv("VERCEL") == "1"
default_db_url = "sqlite:////tmp/feynman.db" if is_vercel else "sqlite:///./feynman.db"
DATABASE_URL = os.getenv("DATABASE_URL", default_db_url)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    verification_token_hash = Column(String, nullable=True)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_study_date = Column(String, nullable=True)  # Format: YYYY-MM-DD
    xp = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    learner_profile = relationship("LearnerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    topic_masteries = relationship("TopicMastery", back_populates="user", cascade="all, delete-orphan")
    learning_events = relationship("LearningEvent", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("UserSubscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notification_preferences = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    certificates = relationship("CertificateRecord", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False, default="Untitled Chat")
    mastery = Column(Integer, nullable=False, default=0)
    has_doc = Column(Boolean, nullable=False, default=False)
    study_mode = Column(String, nullable=False, default="Focus")  # 'Focus' | 'Exam' | 'Practice' | 'Revision' | 'Interview'
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'model' or 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

class PasswordResetOTP(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    otp_hash = Column(String, nullable=False)
    reset_token = Column(String, unique=True, index=True, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ----------------------------------------------------
# TRACK B: PERSISTENT LEARNER MEMORY & KNOWLEDGE GRAPH
# ----------------------------------------------------

class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    learning_level = Column(String, default="beginner", nullable=False) # beginner, intermediate, advanced
    preferred_explanation_style = Column(String, default="practical", nullable=False) # practical, theoretical, visual, analogy
    strengths = Column(Text, default="[]", nullable=False) # JSON list of topic strings
    weaknesses = Column(Text, default="[]", nullable=False) # JSON list of misconception/weak area strings
    goals = Column(Text, default="[]", nullable=False) # JSON list of goals
    total_study_minutes = Column(Integer, default=0, nullable=False)
    aggregate_mastery = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="learner_profile")

class TopicMastery(Base):
    __tablename__ = "topic_masteries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    canonical_topic = Column(String, index=True, nullable=False)
    mastery_score = Column(Integer, default=0, nullable=False) # 0 to 100
    confidence_score = Column(Float, default=0.5, nullable=False) # 0.0 to 1.0
    attempt_count = Column(Integer, default=0, nullable=False)
    correct_count = Column(Integer, default=0, nullable=False)
    incorrect_count = Column(Integer, default=0, nullable=False)
    last_studied_at = Column(DateTime, default=datetime.utcnow)
    next_review_at = Column(DateTime, default=datetime.utcnow)
    weak_spots = Column(Text, default="[]", nullable=False) # JSON list of weak sub-concepts
    preferred_lesson_mode = Column(String, default="STANDARD", nullable=False)
    difficulty = Column(String, default="beginner", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="topic_masteries")

class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id = Column(Integer, primary_key=True, index=True)
    canonical_topic = Column(String, unique=True, index=True, nullable=False)
    category = Column(String, index=True, nullable=False) # e.g. "Computer Science", "Artificial Intelligence", "Mathematics"
    description = Column(Text, default="", nullable=False)
    difficulty_tier = Column(Integer, default=1, nullable=False) # 1: Foundational, 2: Core, 3: Advanced
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_topic = Column(String, index=True, nullable=False) # Prerequisite concept
    target_topic = Column(String, index=True, nullable=False) # Downstream concept
    relationship_type = Column(String, default="PREREQUISITE_OF", nullable=False) # PREREQUISITE_OF, RELATED_TO, SUBTOPIC_OF, EXTENDS
    weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LearningEvent(Base):
    __tablename__ = "learning_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    canonical_topic = Column(String, index=True, nullable=False)
    event_type = Column(String, index=True, nullable=False) # lesson_started, lesson_completed, quiz_answered, quiz_correct, quiz_incorrect, concept_reviewed, mastery_updated
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="learning_events")

# ----------------------------------------------------
# TRACK C: PRODUCTION PLATFORM MODELS
# ----------------------------------------------------

class UserSubscription(Base):
    """Tracks the billing plan for each user (free / pro)."""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    plan = Column(String, default="free", nullable=False)  # "free" | "pro"
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)           # null = perpetual
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscription")


class NotificationPreference(Base):
    """User opt-in/out controls for background email notifications."""
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    email_digest = Column(Boolean, default=True, nullable=False)       # Daily spaced-repetition digest
    streak_reminders = Column(Boolean, default=True, nullable=False)   # Streak preservation alerts
    weekly_report = Column(Boolean, default=True, nullable=False)      # Sunday progress report
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="notification_preferences")


class TelemetryLog(Base):
    """
    Optional DB persistence of per-request telemetry events for the admin dashboard.
    Primary telemetry output is always stdout (log aggregator). This table enables
    SQL-based analytics (DAU, error rates, token consumption) without external tooling.
    """
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    endpoint = Column(String, index=True, nullable=False)
    method = Column(String, nullable=False)
    http_status = Column(Integer, index=True, nullable=False)
    latency_ms = Column(Float, nullable=False)
    user_id_hash = Column(String, nullable=True)   # SHA-256 of user_id, never raw
    model = Column(String, nullable=True)
    key_slot = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    fallback_used = Column(Boolean, default=False, nullable=False)
    rate_limit_hit = Column(Boolean, default=False, nullable=False)
    auth_failure = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)


class CertificateRecord(Base):
    """
    Persistent record of an issued mastery certificate.
    v4 UUID cert_uuid is publicly verifiable via /verify/{cert_uuid}.
    """
    __tablename__ = "certificate_records"

    id = Column(Integer, primary_key=True, index=True)
    cert_uuid = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    student_name = Column(String, nullable=False)
    topic = Column(String, index=True, nullable=False)
    mastery_score = Column(Integer, nullable=False)
    tier = Column(String, nullable=False)
    issued_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="certificates")


# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

