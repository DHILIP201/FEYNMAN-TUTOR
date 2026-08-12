"""
ai_engine/memory/subject_catalog.py
====================================
Track C — C-2: Multi-Subject Knowledge Graph — Subject Catalog

Centralized subject-domain definitions used by the frontend to render
subject-filtered knowledge map views and subject selector pill bars.

Subjects currently seeded: Computer Science, Mathematics, Physics.
Architecture is domain-agnostic: add more entries here + nodes/edges in
learner_memory_engine.py to expand to Chemistry, Economics, etc.
"""

from typing import Dict, List
from sqlalchemy.orm import Session
from database import KnowledgeNode


# ---------------------------------------------------------------------------
# Subject catalog: maps category name → display metadata
# ---------------------------------------------------------------------------

SUBJECT_CATALOG: Dict[str, dict] = {
    "Computer Science": {
        "color": "#6C63FF",          # Purple
        "icon_class": "fa-laptop-code",
        "description": "Algorithms, data structures, programming paradigms, and AI",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
    "Algorithms": {
        "color": "#4ECDC4",          # Teal — subset of CS in the catalog
        "icon_class": "fa-sitemap",
        "description": "Complexity analysis, search, sort, and graph algorithms",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
    "Artificial Intelligence": {
        "color": "#FF6B6B",          # Coral
        "icon_class": "fa-brain",
        "description": "Neural networks, backpropagation, and deep learning",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
    "Machine Learning": {
        "color": "#FF8E53",          # Orange — subset of AI
        "icon_class": "fa-chart-line",
        "description": "Supervised and unsupervised learning, loss functions",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
    "Optimization": {
        "color": "#2EC4B6",          # Mint — cross-cutting
        "icon_class": "fa-sliders-h",
        "description": "Gradient descent and mathematical optimization",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
    "Mathematics": {
        "color": "#F7B731",          # Amber
        "icon_class": "fa-square-root-alt",
        "description": "Algebra, calculus, linear algebra, probability, and statistics",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
    "Physics": {
        "color": "#26de81",          # Green
        "icon_class": "fa-atom",
        "description": "Classical mechanics, thermodynamics, electricity, and quantum theory",
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    },
}

# The three primary user-visible subject domains for C-2
PRIMARY_SUBJECTS: List[str] = ["Computer Science", "Mathematics", "Physics"]


def get_subjects(db: Session) -> List[str]:
    """
    Return all distinct category names currently in the knowledge_nodes table.
    Ordered: PRIMARY_SUBJECTS first, then any additional categories alphabetically.
    """
    rows = db.query(KnowledgeNode.category).distinct().all()
    all_categories = sorted({r[0] for r in rows})

    # Primary subjects first for frontend ordering
    ordered = [s for s in PRIMARY_SUBJECTS if s in all_categories]
    others = [s for s in all_categories if s not in PRIMARY_SUBJECTS]
    return ordered + others


def get_subject_metadata(category: str) -> dict:
    """Return display metadata for a subject category, with a safe default."""
    return SUBJECT_CATALOG.get(category, {
        "color": "#888888",
        "icon_class": "fa-book",
        "description": category,
        "tier_thresholds": {"mastered": 80, "in_progress": 40},
    })
