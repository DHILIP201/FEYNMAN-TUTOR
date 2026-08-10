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
    # ─── Computer Science ───────────────────────────────────────────
    {"canonical_topic": "Variables", "category": "Computer Science", "description": "Named storage containers for values in programs", "difficulty_tier": 1},
    {"canonical_topic": "Conditionals", "category": "Computer Science", "description": "If/else branching logic based on boolean conditions", "difficulty_tier": 1},
    {"canonical_topic": "Loops", "category": "Computer Science", "description": "Repeated execution of a code block while a condition holds", "difficulty_tier": 1},
    {"canonical_topic": "Functions", "category": "Computer Science", "description": "Reusable named blocks of code that accept parameters", "difficulty_tier": 1},
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

    # ─── Mathematics ────────────────────────────────────────────────
    {"canonical_topic": "Arithmetic", "category": "Mathematics", "description": "Basic operations: addition, subtraction, multiplication, division", "difficulty_tier": 1},
    {"canonical_topic": "Algebra", "category": "Mathematics", "description": "Symbolic manipulation of expressions and equations", "difficulty_tier": 1},
    {"canonical_topic": "Functions (Math)", "category": "Mathematics", "description": "Mappings from inputs to outputs: f(x) = ...", "difficulty_tier": 1},
    {"canonical_topic": "Limits", "category": "Mathematics", "description": "Value a function approaches as input nears a point", "difficulty_tier": 2},
    {"canonical_topic": "Derivatives", "category": "Mathematics", "description": "Instantaneous rate of change of a function", "difficulty_tier": 2},
    {"canonical_topic": "Integrals", "category": "Mathematics", "description": "Accumulated area under a curve", "difficulty_tier": 2},
    {"canonical_topic": "Differential Equations", "category": "Mathematics", "description": "Equations relating a function to its derivatives", "difficulty_tier": 3},
    {"canonical_topic": "Linear Algebra", "category": "Mathematics", "description": "Vectors, matrices, linear transformations, and dot products", "difficulty_tier": 1},
    {"canonical_topic": "Probability", "category": "Mathematics", "description": "Mathematical study of randomness and likelihood", "difficulty_tier": 2},
    {"canonical_topic": "Statistics", "category": "Mathematics", "description": "Collection, analysis, and interpretation of data", "difficulty_tier": 2},
    {"canonical_topic": "Calculus", "category": "Mathematics", "description": "Derivatives, integrals, and rate of change", "difficulty_tier": 1},

    # ─── Physics ────────────────────────────────────────────────────
    {"canonical_topic": "Units & Measurement", "category": "Physics", "description": "SI units, dimensional analysis, and scientific notation", "difficulty_tier": 1},
    {"canonical_topic": "Kinematics", "category": "Physics", "description": "Description of motion: position, velocity, acceleration", "difficulty_tier": 1},
    {"canonical_topic": "Newton's Laws", "category": "Physics", "description": "The three fundamental laws of motion and force", "difficulty_tier": 2},
    {"canonical_topic": "Work & Energy", "category": "Physics", "description": "Mechanical work, kinetic and potential energy, conservation", "difficulty_tier": 2},
    {"canonical_topic": "Momentum", "category": "Physics", "description": "Mass times velocity; conservation in collisions", "difficulty_tier": 2},
    {"canonical_topic": "Waves", "category": "Physics", "description": "Oscillatory disturbances propagating through media", "difficulty_tier": 2},
    {"canonical_topic": "Thermodynamics", "category": "Physics", "description": "Heat, temperature, and the laws governing energy transfer", "difficulty_tier": 2},
    {"canonical_topic": "Electricity", "category": "Physics", "description": "Electric charge, current, voltage, and resistance", "difficulty_tier": 2},
    {"canonical_topic": "Magnetism", "category": "Physics", "description": "Magnetic fields, forces, and electromagnetic induction", "difficulty_tier": 2},
    {"canonical_topic": "Quantum Mechanics", "category": "Physics", "description": "Probabilistic description of matter at atomic/subatomic scales", "difficulty_tier": 3},
]

FOUNDATIONAL_KNOWLEDGE_EDGES = [
    # ─── Computer Science internal edges ────────────────────────────
    {"source_topic": "Variables", "target_topic": "Conditionals", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Variables", "target_topic": "Loops", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Conditionals", "target_topic": "Functions", "relationship_type": "PREREQUISITE_OF", "weight": 0.8},
    {"source_topic": "Loops", "target_topic": "Functions", "relationship_type": "PREREQUISITE_OF", "weight": 0.8},
    {"source_topic": "Base Case", "target_topic": "Recursion", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Call Stack", "target_topic": "Recursion", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Functions", "target_topic": "Recursion", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Big-O Notation", "target_topic": "Binary Search", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Linear Algebra", "target_topic": "Neural Networks", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Activation Function", "target_topic": "Neural Networks", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Loss Function", "target_topic": "Gradient Descent", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Calculus", "target_topic": "Backpropagation", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Gradient Descent", "target_topic": "Backpropagation", "relationship_type": "RELATED_TO", "weight": 1.0},
    {"source_topic": "Neural Networks", "target_topic": "Backpropagation", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},

    # ─── Mathematics internal edges ──────────────────────────────────
    {"source_topic": "Arithmetic", "target_topic": "Algebra", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Algebra", "target_topic": "Functions (Math)", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Functions (Math)", "target_topic": "Limits", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Limits", "target_topic": "Derivatives", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Derivatives", "target_topic": "Integrals", "relationship_type": "RELATED_TO", "weight": 1.0},
    {"source_topic": "Derivatives", "target_topic": "Differential Equations", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Integrals", "target_topic": "Differential Equations", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Algebra", "target_topic": "Linear Algebra", "relationship_type": "PREREQUISITE_OF", "weight": 0.8},
    {"source_topic": "Arithmetic", "target_topic": "Probability", "relationship_type": "PREREQUISITE_OF", "weight": 0.8},
    {"source_topic": "Probability", "target_topic": "Statistics", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Derivatives", "target_topic": "Calculus", "relationship_type": "SUBTOPIC_OF", "weight": 1.0},
    {"source_topic": "Integrals", "target_topic": "Calculus", "relationship_type": "SUBTOPIC_OF", "weight": 1.0},

    # ─── Physics internal edges ──────────────────────────────────────
    {"source_topic": "Units & Measurement", "target_topic": "Kinematics", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Kinematics", "target_topic": "Newton's Laws", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Newton's Laws", "target_topic": "Work & Energy", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Newton's Laws", "target_topic": "Momentum", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Work & Energy", "target_topic": "Thermodynamics", "relationship_type": "RELATED_TO", "weight": 0.7},
    {"source_topic": "Electricity", "target_topic": "Magnetism", "relationship_type": "PREREQUISITE_OF", "weight": 1.0},
    {"source_topic": "Quantum Mechanics", "target_topic": "Quantum Mechanics", "relationship_type": "RELATED_TO", "weight": 0.1},  # self-ref placeholder avoided below

    # ─── Cross-subject prerequisite edges ───────────────────────────
    # Physics uses Calculus (Kinematics → Derivatives; force = ma → Newton's Laws need Derivatives)
    {"source_topic": "Derivatives", "target_topic": "Kinematics", "relationship_type": "PREREQUISITE_OF", "weight": 0.9},
    {"source_topic": "Derivatives", "target_topic": "Newton's Laws", "relationship_type": "RELATED_TO", "weight": 0.8},
    {"source_topic": "Integrals", "target_topic": "Work & Energy", "relationship_type": "RELATED_TO", "weight": 0.7},
    # Linear Algebra underpins ML which is CS
    {"source_topic": "Linear Algebra", "target_topic": "Backpropagation", "relationship_type": "PREREQUISITE_OF", "weight": 0.9},
    # Probability underpins ML/AI
    {"source_topic": "Probability", "target_topic": "Loss Function", "relationship_type": "RELATED_TO", "weight": 0.7},
    {"source_topic": "Statistics", "target_topic": "Loss Function", "relationship_type": "RELATED_TO", "weight": 0.6},
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
        evaluation_id: Optional[str] = None
    ) -> Tuple[TopicMastery, Dict[str, Any]]:
        """
        Authoritative backend calculation of learner mastery and weak spots.
        Gemini is NOT allowed to directly set database values or confidence deltas.
        Idempotent: If evaluation_id is provided and already recorded, ignores duplicates.
        """
        mastery = self.get_or_create_topic_mastery(db, user_id, canonical_topic)
        profile = self.get_or_create_profile(db, user_id)
        current_weaknesses = json.loads(mastery.weak_spots or "[]")

        # Idempotency check
        if evaluation_id:
            existing_event = db.query(LearningEvent).filter(
                LearningEvent.user_id == user_id,
                LearningEvent.metadata_json.like(f'%"evaluation_id": "{evaluation_id}"%')
            ).first()
            if existing_event:
                # Already processed — return current state without double mutating
                return mastery, {
                    "canonical_topic": canonical_topic,
                    "mastery_score": mastery.mastery_score,
                    "confidence_score": mastery.confidence_score,
                    "attempts": mastery.attempt_count,
                    "weak_spots": current_weaknesses,
                    "next_review_at": mastery.next_review_at.strftime("%Y-%m-%d %H:%M") if mastery.next_review_at else None,
                    "idempotent_duplicate": True
                }

        old_mastery = mastery.mastery_score

        if is_correct:
            # Backend strictly controls exact mastery (+15) and confidence (+0.10) increments
            mastery.mastery_score = min(100, mastery.mastery_score + 15)
            mastery.confidence_score = min(1.0, round(mastery.confidence_score + 0.10, 2))
            mastery.correct_count += 1
            # If a weak spot was resolved, remove it
            if weak_concept and weak_concept in current_weaknesses:
                current_weaknesses.remove(weak_concept)
            event_type = "quiz_correct"
        else:
            # Backend strictly controls exact mastery (-10) and confidence (-0.15) decrements
            mastery.mastery_score = max(0, mastery.mastery_score - 10)
            mastery.confidence_score = max(0.0, round(mastery.confidence_score - 0.15, 2))
            mastery.incorrect_count += 1
            # Add identified weak spot (deduplicated)
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

        # Log learning event in ledger with evaluation_id
        event_metadata = {
            "old_mastery": old_mastery,
            "new_mastery": mastery.mastery_score,
            "is_correct": is_correct,
            "weak_concept": weak_concept,
            "next_review_at": mastery.next_review_at.isoformat()
        }
        if evaluation_id:
            event_metadata["evaluation_id"] = evaluation_id

        self.log_event(
            db,
            user_id=user_id,
            canonical_topic=canonical_topic,
            event_type=event_type,
            metadata=event_metadata
        )

        signal_summary = {
            "canonical_topic": canonical_topic,
            "mastery_score": mastery.mastery_score,
            "confidence_score": mastery.confidence_score,
            "attempts": mastery.attempt_count,
            "weak_spots": current_weaknesses,
            "next_review_at": mastery.next_review_at.strftime("%Y-%m-%d %H:%M"),
            "idempotent_duplicate": False
        }
        return mastery, signal_summary

    # --- KNOWLEDGE GRAPH & STATUS MAPPING ---

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

    def get_user_knowledge_map(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Distinguishes NOT_STARTED from 0% mastery and provides visual statuses:
        - MASTERED: mastery >= 80%
        - IN_PROGRESS: 40% <= mastery < 80%
        - NEEDS_ATTENTION: attempted but mastery < 40%
        - NOT_STARTED: topic in knowledge graph not yet attempted by student
        """
        global_nodes = db.query(KnowledgeNode).all()
        user_masteries = {
            m.canonical_topic: m for m in db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()
        }

        nodes = []
        for gn in global_nodes:
            topic = gn.canonical_topic
            m = user_masteries.get(topic)

            if m is None or (m.attempt_count == 0 and m.mastery_score == 0):
                status = "NOT_STARTED"
                score = 0
                confidence = 0.0
                attempts = 0
                weak_spots = []
                last_studied = None
                next_review = None
            else:
                score = m.mastery_score
                confidence = m.confidence_score
                attempts = m.attempt_count
                weak_spots = json.loads(m.weak_spots or "[]")
                last_studied = m.last_studied_at.isoformat() if m.last_studied_at else None
                next_review = m.next_review_at.isoformat() if m.next_review_at else None

                if score >= 80:
                    status = "MASTERED"
                elif score >= 40:
                    status = "IN_PROGRESS"
                else:
                    status = "NEEDS_ATTENTION"

            nodes.append({
                "topic": topic,
                "category": gn.category,
                "description": gn.description,
                "difficulty_tier": gn.difficulty_tier,
                "status": status,
                "mastery_score": score,
                "confidence_score": confidence,
                "attempt_count": attempts,
                "weak_spots": weak_spots,
                "last_studied_at": last_studied,
                "next_review_at": next_review
            })

        edges = []
        db_edges = db.query(KnowledgeEdge).all()
        for e in db_edges:
            edges.append({
                "source": e.source_topic,
                "target": e.target_topic,
                "relationship": e.relationship_type,
                "weight": e.weight
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "mastered_count": sum(1 for n in nodes if n["status"] == "MASTERED"),
            "in_progress_count": sum(1 for n in nodes if n["status"] == "IN_PROGRESS"),
            "needs_attention_count": sum(1 for n in nodes if n["status"] == "NEEDS_ATTENTION"),
            "not_started_count": sum(1 for n in nodes if n["status"] == "NOT_STARTED")
        }

    # --- ADAPTIVE LEARNING PATH & PREREQUISITE RECOMMENDER ---

    def recommend_next_learning_path(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Cognitive recommendation engine:
        1. Checks for prerequisite blockers (e.g. Backpropagation weak, but Calculus is weak too).
        2. Checks for due spaced repetition reviews.
        3. Checks for weak topic remediation.
        4. Suggests next unlocked frontier concepts in knowledge graph.
        """
        user_masteries = {
            m.canonical_topic: m for m in db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()
        }
        all_edges = db.query(KnowledgeEdge).filter(KnowledgeEdge.relationship_type == "PREREQUISITE_OF").all()

        now = datetime.utcnow()
        due_reviews = []
        for m in user_masteries.values():
            if m.next_review_at and m.next_review_at <= now and m.attempt_count > 0:
                due_reviews.append({
                    "topic": m.canonical_topic,
                    "mastery_score": m.mastery_score,
                    "next_review_at": m.next_review_at.strftime("%Y-%m-%d %H:%M")
                })

        # Find Prerequisite Blockers
        prerequisite_blockers = []
        for topic, m in user_masteries.items():
            if m.attempt_count > 0 and m.mastery_score < 60:
                # Find prerequisites of this topic
                prereqs = [e.source_topic for e in all_edges if e.target_topic == topic]
                for p in prereqs:
                    pm = user_masteries.get(p)
                    p_score = pm.mastery_score if pm else 0
                    if p_score < 60:
                        prerequisite_blockers.append({
                            "target_topic": topic,
                            "target_mastery": m.mastery_score,
                            "prerequisite_topic": p,
                            "prerequisite_mastery": p_score,
                            "recommendation": f"Strengthen {p} ({p_score}%) before continuing {topic} ({m.mastery_score}%)."
                        })

        # Weak spots across all topics
        all_weak_spots = []
        for m in user_masteries.values():
            ws = json.loads(m.weak_spots or "[]")
            for w in ws:
                all_weak_spots.append({"topic": m.canonical_topic, "weak_concept": w})

        # Determine Primary Action
        primary_action = None

        if prerequisite_blockers:
            pb = prerequisite_blockers[0]
            primary_action = {
                "type": "REPAIR_PREREQUISITE",
                "topic": pb["prerequisite_topic"],
                "target_topic": pb["target_topic"],
                "reason": pb["recommendation"],
                "current_mastery": pb["prerequisite_mastery"],
                "urgency": "high"
            }
        elif due_reviews:
            dr = due_reviews[0]
            primary_action = {
                "type": "SPACED_REVIEW",
                "topic": dr["topic"],
                "target_topic": None,
                "reason": f"Active recall review is due today to reinforce retention.",
                "current_mastery": dr["mastery_score"],
                "urgency": "high"
            }
        else:
            # Look for weak topic
            weak_topics = [m for m in user_masteries.values() if m.attempt_count > 0 and m.mastery_score < 60]
            if weak_topics:
                wt = weak_topics[0]
                primary_action = {
                    "type": "REMEDY_WEAK_TOPIC",
                    "topic": wt.canonical_topic,
                    "target_topic": None,
                    "reason": f"Mastery is currently at {wt.mastery_score}%. Practice active recall to overcome detected misconceptions.",
                    "current_mastery": wt.mastery_score,
                    "urgency": "medium"
                }
            else:
                # Find Next Frontier (topics where all prerequisites are >= 75%)
                global_nodes = db.query(KnowledgeNode).all()
                unlocked_topics = []
                for gn in global_nodes:
                    topic = gn.canonical_topic
                    m = user_masteries.get(topic)
                    if m is None or m.attempt_count == 0:
                        # Check prerequisites
                        prereqs = [e.source_topic for e in all_edges if e.target_topic == topic]
                        all_prereqs_met = True
                        for p in prereqs:
                            pm = user_masteries.get(p)
                            if not pm or pm.mastery_score < 75:
                                all_prereqs_met = False
                                break
                        if all_prereqs_met:
                            unlocked_topics.append(topic)

                next_topic = unlocked_topics[0] if unlocked_topics else "Recursion"
                primary_action = {
                    "type": "NEXT_FRONTIER",
                    "topic": next_topic,
                    "target_topic": None,
                    "reason": f"Prerequisites are mastered! Ready to explore {next_topic}.",
                    "current_mastery": 0,
                    "urgency": "low"
                }

        # Build Recommended Sequence
        learning_path = []
        if primary_action:
            learning_path.append(primary_action["topic"])
        for pb in prerequisite_blockers:
            if pb["target_topic"] not in learning_path:
                learning_path.append(pb["target_topic"])
        for dr in due_reviews:
            if dr["topic"] not in learning_path:
                learning_path.append(dr["topic"])

        return {
            "primary_action": primary_action,
            "prerequisite_blockers": prerequisite_blockers,
            "due_reviews": due_reviews,
            "weak_spots": all_weak_spots,
            "learning_path": learning_path[:5]
        }

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

