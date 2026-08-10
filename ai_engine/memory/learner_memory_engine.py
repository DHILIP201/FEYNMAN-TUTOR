"""
Feynman Cognitive Engine — Track B: Persistent Learner Memory & Knowledge Graph
Provides persistent learner profiling, canonical topic mastery tracking,
deterministic spaced repetition scheduling, knowledge graph relationship querying,
and learning event ledger auditing.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from database import (
    User,
    LearnerProfile,
    TopicMastery,
    KnowledgeNode,
    KnowledgeEdge,
    LearningEvent,
    init_db
)


# ----------------------------------------------------
# 1. DETERMINISTIC KNOWLEDGE GRAPH REPOSITORY
# ----------------------------------------------------

FOUNDATIONAL_KNOWLEDGE_NODES = [
    {"canonical_topic": "Recursion", "category": "Computer Science", "description": "Functions calling themselves with base cases", "difficulty_tier": 2},
    {"canonical_topic": "Call Stack", "category": "Computer Science", "description": "Memory structure tracking active execution frames", "difficulty_tier": 1},
    {"canonical_topic": "Base Case", "category": "Computer Science", "description": "Terminating condition that stops recursive calls", "difficulty_tier": 1},
    {"canonical_topic": "Binary Search", "category": "Algorithms", "description": "Logarithmic search over sorted arrays", "difficulty_tier": 2},
    {"canonical_topic": "Big-O Notation", "category": "Algorithms", "description": "Asymptotic computational complexity analysis", "difficulty_tier": 1},
    {"canonical_topic": "Neural Networks", "category": "Artificial Intelligence", "description": "Interconnected layers of parameterized perceptrons", "difficulty_tier": 2},
    {"canonical_topic": "Backpropagation", "category": "Artificial Intelligence", "description": "Chain-rule gradient computation across network weights", "difficulty_tier": 3},
    {"canonical_topic": "Gradient Descent", "category": "Optimization", "description": "First-order iterative optimization algorithm", "difficulty_tier": 2},
    {"canonical_topic": "Activation Function", "category": "Artificial Intelligence", "description": "Non-linear transformations applied to neuron outputs", "difficulty_tier": 2},
    {"canonical_topic": "Loss Function", "category": "Machine Learning", "description": "Scalar penalty quantifying prediction error", "difficulty_tier": 1},
    {"canonical_topic": "Linear Algebra", "category": "Mathematics", "description": "Vectors, matrices, linear transformations, and dot products", "difficulty_tier": 1},
    {"canonical_topic": "Calculus", "category": "Mathematics", "description": "Derivatives, integrals, and rate of change", "difficulty_tier": 1}
]

FOUNDATIONAL_KNOWLEDGE_EDGES = [
    {"source_topic": "Base Case", "target_topic": "Recursion", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Call Stack", "target_topic": "Recursion", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Big-O Notation", "target_topic": "Binary Search", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Linear Algebra", "target_topic": "Neural Networks", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Activation Function", "target_topic": "Neural Networks", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Loss Function", "target_topic": "Gradient Descent", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Calculus", "target_topic": "Backpropagation", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Gradient Descent", "target_topic": "Backpropagation", "relationship_type": "RELATED_TO", "weight": 1.0},
    {"source_topic": "Neural Networks", "target_topic": "Backpropagation", "relationship_type": "PREREQUISITE_OF", "weight": 1.0}
]


def seed_foundational_knowledge_graph(db: Session):
    """Populates foundational concept nodes and relationship edges idempotently."""
    for n in FOUNDATIONAL_KNOWLEDGE_NODES:
        existing = db.query(KnowledgeNode).filter(KnowledgeNode.canonical_topic == n["canonical_topic"]).first()
        if not existing:
            db.add(KnowledgeNode(
                canonical_topic=n["canonical_topic"],
                category=n["category"],
                description=n["description"],
                difficulty_tier=n["difficulty_tier"]
            ))
    db.commit()

    for e in FOUNDATIONAL_KNOWLEDGE_EDGES:
        existing_edge = db.query(KnowledgeEdge).filter(
            KnowledgeEdge.source_topic == e["source_topic"],
            KnowledgeEdge.target_topic == e["target_topic"],
            KnowledgeEdge.relationship_type == e["relationship_type"]
        ).first()
        if not existing_edge:
            db.add(KnowledgeEdge(
                source_topic=e["source_topic"],
                target_topic=e["target_topic"],
                relationship_type=e["relationship_type"],
                weight=e["weight"]
            ))
    db.commit()


# ----------------------------------------------------
# 2. SPACED REPETITION SCHEDULER
# ----------------------------------------------------

class SpacedRepetitionScheduler:
    """
    Deterministic Spaced Repetition Engine.
    Calculates next review timestamp based on verified mastery levels.
    """

    @staticmethod
    def calculate_next_review(mastery_score: int, confidence: float = 0.5) -> datetime:
        now = datetime.utcnow()
        if mastery_score < 40:
            interval_days = 1
        elif 40 <= mastery_score < 60:
            interval_days = 2
        elif 60 <= mastery_score < 75:
            interval_days = 4
        elif 75 <= mastery_score < 90:
            interval_days = 7
        else: # 90%+
            interval_days = 14

        # Confidence modifier: low confidence accelerates next review
        if confidence < 0.4 and interval_days > 1:
            interval_days = max(1, interval_days - 1)

        return now + timedelta(days=interval_days)


# ----------------------------------------------------
# 3. CORE LEARNER MEMORY & KNOWLEDGE GRAPH ENGINE
# ----------------------------------------------------

class LearnerMemoryEngine:
    """
    Orchestrates persistent learner memory, topic mastery mutations,
    knowledge graph context generation, and learning event ledger auditing.
    """

    def __init__(self):
        self.scheduler = SpacedRepetitionScheduler()

    # --- LEARNER PROFILE SERVICE ---

    def get_or_create_profile(self, db: Session, user_id: int) -> LearnerProfile:
        """Retrieves or initializes a persistent learner profile for an authenticated user."""
        profile = db.query(LearnerProfile).filter(LearnerProfile.user_id == user_id).first()
        if not profile:
            profile = LearnerProfile(
                user_id=user_id,
                learning_level="beginner",
                preferred_explanation_style="practical",
                strengths="[]",
                weaknesses="[]",
                goals="[]",
                total_study_minutes=0,
                aggregate_mastery=0
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    def update_profile_preferences(
        self,
        db: Session,
        user_id: int,
        learning_level: Optional[str] = None,
        preferred_style: Optional[str] = None,
        goals: Optional[List[str]] = None
    ) -> LearnerProfile:
        profile = self.get_or_create_profile(db, user_id)
        if learning_level:
            profile.learning_level = learning_level
        if preferred_style:
            profile.preferred_explanation_style = preferred_style
        if goals is not None:
            profile.goals = json.dumps(goals)
        db.commit()
        db.refresh(profile)
        return profile

    # --- TOPIC MASTERY SERVICE ---

    def get_or_create_topic_mastery(
        self,
        db: Session,
        user_id: int,
        canonical_topic: str
    ) -> TopicMastery:
        """Retrieves or initializes topic mastery for a given canonical topic."""
        clean_topic = canonical_topic.strip()
        mastery = db.query(TopicMastery).filter(
            TopicMastery.user_id == user_id,
            TopicMastery.canonical_topic == clean_topic
        ).first()

        if not mastery:
            mastery = TopicMastery(
                user_id=user_id,
                canonical_topic=clean_topic,
                mastery_score=0,
                confidence_score=0.5,
                attempt_count=0,
                correct_count=0,
                incorrect_count=0,
                last_studied_at=datetime.utcnow(),
                next_review_at=datetime.utcnow(),
                weak_spots="[]",
                preferred_lesson_mode="STANDARD",
                difficulty="beginner"
            )
            db.add(mastery)
            db.commit()
            db.refresh(mastery)
        return mastery

    def record_lesson_started(
        self,
        db: Session,
        user_id: int,
        canonical_topic: str,
        lesson_mode: str = "STANDARD"
    ) -> TopicMastery:
        """Logs a lesson start event and refreshes study timestamp."""
        mastery = self.get_or_create_topic_mastery(db, user_id, canonical_topic)
        mastery.last_studied_at = datetime.utcnow()
        mastery.preferred_lesson_mode = lesson_mode
        db.commit()

        self.log_event(
            db,
            user_id=user_id,
            canonical_topic=canonical_topic,
            event_type="lesson_started",
            metadata={"lesson_mode": lesson_mode}
        )
        return mastery

    # --- BACKEND DETERMINISTIC MASTERY & WEAK SPOT ENGINE ---

    def record_learning_signal(
        self,
        db: Session,
        user_id: int,
        canonical_topic: str,
        is_correct: bool,
        weak_concept: Optional[str] = None,
        confidence_delta: float = 0.0
    ) -> Tuple[TopicMastery, Dict[str, Any]]:
        """
        Authoritative backend calculation of learner mastery and weak spots.
        Gemini is NOT allowed to directly set database values.
        """
        mastery = self.get_or_create_topic_mastery(db, user_id, canonical_topic)
        profile = self.get_or_create_profile(db, user_id)

        current_weaknesses = json.loads(mastery.weak_spots or "[]")
        old_mastery = mastery.mastery_score

        if is_correct:
            # Mastery increase & confidence boost
            mastery.mastery_score = min(100, mastery.mastery_score + 15)
            mastery.confidence_score = min(1.0, round(mastery.confidence_score + 0.10 + confidence_delta, 2))
            mastery.correct_count += 1
            # If a weak spot was resolved, remove it
            if weak_concept and weak_concept in current_weaknesses:
                current_weaknesses.remove(weak_concept)
            event_type = "quiz_correct"
        else:
            # Mastery penalty & confidence decrement
            mastery.mastery_score = max(0, mastery.mastery_score - 10)
            mastery.confidence_score = max(0.0, round(mastery.confidence_score - 0.15, 2))
            mastery.incorrect_count += 1
            # Add identified weak spot
            if weak_concept and weak_concept not in current_weaknesses:
                current_weaknesses.append(weak_concept)
            event_type = "quiz_incorrect"

        mastery.attempt_count += 1
        mastery.weak_spots = json.dumps(current_weaknesses)
        mastery.last_studied_at = datetime.utcnow()
        mastery.next_review_at = self.scheduler.calculate_next_review(
            mastery_score=mastery.mastery_score,
            confidence=mastery.confidence_score
        )

        # Update aggregate mastery across all topics for the profile
        all_masteries = db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()
        if all_masteries:
            profile.aggregate_mastery = int(sum(m.mastery_score for m in all_masteries) / len(all_masteries))

        db.commit()
        db.refresh(mastery)
        db.refresh(profile)

        # Log learning event in ledger
        self.log_event(
            db,
            user_id=user_id,
            canonical_topic=canonical_topic,
            event_type=event_type,
            metadata={
                "old_mastery": old_mastery,
                "new_mastery": mastery.mastery_score,
                "is_correct": is_correct,
                "weak_concept": weak_concept,
                "next_review_at": mastery.next_review_at.isoformat()
            }
        )

        signal_summary = {
            "canonical_topic": canonical_topic,
            "mastery_score": mastery.mastery_score,
            "confidence_score": mastery.confidence_score,
            "attempts": mastery.attempt_count,
            "weak_spots": current_weaknesses,
            "next_review_at": mastery.next_review_at.strftime("%Y-%m-%d %H:%M")
        }
        return mastery, signal_summary

    # --- KNOWLEDGE GRAPH RELATIONS ---

    def get_prerequisites(self, db: Session, canonical_topic: str) -> List[str]:
        """Returns immediate prerequisite concepts required before learning canonical_topic."""
        edges = db.query(KnowledgeEdge).filter(
            KnowledgeEdge.target_topic == canonical_topic,
            KnowledgeEdge.relationship_type == "PREREQUISITE_OF"
        ).all()
        return [e.source_topic for e in edges]

    def get_related_concepts(self, db: Session, canonical_topic: str) -> List[str]:
        """Returns related concepts linked in the knowledge graph."""
        edges = db.query(KnowledgeEdge).filter(
            (KnowledgeEdge.source_topic == canonical_topic) | (KnowledgeEdge.target_topic == canonical_topic)
        ).all()
        related = set()
        for e in edges:
            if e.source_topic != canonical_topic:
                related.add(e.source_topic)
            if e.target_topic != canonical_topic:
                related.add(e.target_topic)
        return list(related)

    # --- LEARNING EVENT LEDGER ---

    def log_event(
        self,
        db: Session,
        user_id: int,
        canonical_topic: str,
        event_type: str,
        metadata: Dict[str, Any]
    ) -> LearningEvent:
        """Appends an immutable learning event to the audit ledger."""
        event = LearningEvent(
            user_id=user_id,
            canonical_topic=canonical_topic,
            event_type=event_type,
            metadata_json=json.dumps(metadata)
        )
        db.add(event)
        db.commit()
        return event

    # --- MEMORY-AWARE TUTOR CONTEXT BUILDER ---

    def build_memory_context(
        self,
        db: Session,
        user_id: int,
        canonical_topic: str
    ) -> Dict[str, Any]:
        """
        Constructs rich, structured learner context for system prompts without
        violating response schemas or leaking unauthorized user state.
        """
        profile = self.get_or_create_profile(db, user_id)
        mastery = self.get_or_create_topic_mastery(db, user_id, canonical_topic)
        prereqs = self.get_prerequisites(db, canonical_topic)
        related = self.get_related_concepts(db, canonical_topic)
        weak_spots = json.loads(mastery.weak_spots or "[]")

        # Fetch prerequisite mastery states
        prereq_masteries = []
        for p in prereqs:
            pm = db.query(TopicMastery).filter(
                TopicMastery.user_id == user_id,
                TopicMastery.canonical_topic == p
            ).first()
            score = pm.mastery_score if pm else 0
            prereq_masteries.append(f"{p} (Mastery: {score}%)")

        context_prompt_block = (
            f"[LEARNER PROFILE & ADAPTIVE MEMORY]\n"
            f"- User Learning Level: {profile.learning_level.title()}\n"
            f"- Preferred Explanation Style: {profile.preferred_explanation_style.title()}\n"
            f"- Topic: {canonical_topic}\n"
            f"- Current Mastery Score: {mastery.mastery_score}% (Confidence: {int(mastery.confidence_score * 100)}%)\n"
            f"- Prior Attempts: {mastery.attempt_count} (Correct: {mastery.correct_count}, Misconceptions: {mastery.incorrect_count})\n"
        )
        if weak_spots:
            context_prompt_block += f"- Identified Weak Spots: {', '.join(weak_spots)}\n"
        if prereq_masteries:
            context_prompt_block += f"- Prerequisite Concepts: {', '.join(prereq_masteries)}\n"
        if related:
            context_prompt_block += f"- Connected Knowledge Graph Concepts: {', '.join(related[:3])}\n"

        return {
            "canonical_topic": canonical_topic,
            "mastery_score": mastery.mastery_score,
            "confidence_score": mastery.confidence_score,
            "learning_level": profile.learning_level,
            "preferred_style": profile.preferred_explanation_style,
            "weak_spots": weak_spots,
            "prerequisites": prereqs,
            "related_concepts": related,
            "context_prompt_block": context_prompt_block
        }


# Singleton Learner Memory Engine
learner_memory_engine = LearnerMemoryEngine()
