"""
Triage modules for Public Health Outbreak Intelligence.

This package contains modules for scoring, deduplication, and prioritization
of public health events.
"""

from .scoring import score_event, calculate_priority_band, ScoringResult
from .dedup import deduplicate_events, is_duplicate

__all__ = [
    "score_event",
    "calculate_priority_band",
    "ScoringResult",
    "deduplicate_events",
    "is_duplicate",
]
