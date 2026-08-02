"""
Deduplication module for Public Health Outbreak Intelligence.

This module provides deterministic deduplication of events based on content hashing
and other similarity metrics to avoid processing duplicate notices.
"""

from typing import Optional, Any
from datetime import datetime, timedelta

from ..models import EventCard
from ..db import Database


def is_duplicate(event: EventCard, db: Database, window_hours: int = 24) -> bool:
    """
    Check if an event is a duplicate of an existing event.

    Args:
        event: The EventCard to check
        db: Database instance
        window_hours: Time window in hours for considering duplicates

    Returns:
        True if the event is a duplicate, False otherwise
    """
    # Check for exact content hash match
    existing_events = db.get_events_by_content_hash(event.content_hash)
    if existing_events:
        return True

    # Check for similar events within the time window
    time_window = timedelta(hours=window_hours)
    recent_events = db.get_events_by_date((datetime.utcnow() - time_window).strftime("%Y-%m-%d"))

    for existing_event in recent_events:
        if _are_events_similar(event, existing_event):
            return True

    return False


def _are_events_similar(event1: EventCard, event2: EventCard, threshold: float = 0.9) -> bool:
    """
    Check if two events are similar based on multiple factors.

    Args:
        event1: First EventCard
        event2: Second EventCard
        threshold: Similarity threshold (0-1)

    Returns:
        True if events are similar above the threshold
    """
    # Same source and similar title
    if (
        event1.source_id == event2.source_id
        and _text_similarity(event1.title, event2.title) > threshold
    ):
        return True

    # Same source and similar content hash (partial match)
    if (
        event1.source_id == event2.source_id
        and _hash_similarity(event1.content_hash, event2.content_hash) > threshold
    ):
        return True

    # Same disease and similar geography
    if (
        event1.disease_or_hazard == event2.disease_or_hazard
        and _geography_similarity(event1.geographies, event2.geographies) > threshold
    ):
        return True

    return False


def _text_similarity(text1: str, text2: str) -> float:
    """
    Calculate text similarity using simple token overlap.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0-1)
    """
    if not text1 or not text2:
        return 0.0

    # Tokenize and normalize
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())

    if not tokens1 or not tokens2:
        return 0.0

    # Calculate Jaccard similarity
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def _hash_similarity(hash1: str, hash2: str) -> float:
    """
    Calculate hash similarity by comparing character overlap.

    Args:
        hash1: First hash
        hash2: Second hash

    Returns:
        Similarity score (0-1)
    """
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 0.0

    matches = sum(1 for c1, c2 in zip(hash1, hash2) if c1 == c2)
    return matches / len(hash1) if len(hash1) > 0 else 0.0


def _geography_similarity(geos1: list, geos2: list) -> float:
    """
    Calculate geography similarity.

    Args:
        geos1: List of Geography objects
        geos2: List of Geography objects

    Returns:
        Similarity score (0-1)
    """
    if not geos1 or not geos2:
        return 0.0

    # Convert to sets of tuples for comparison
    geo_set1 = set()
    geo_set2 = set()

    for geo in geos1:
        geo_tuple = tuple([geo.country, geo.state, geo.region])
        if any(geo_tuple):
            geo_set1.add(geo_tuple)

    for geo in geos2:
        geo_tuple = tuple([geo.country, geo.state, geo.region])
        if any(geo_tuple):
            geo_set2.add(geo_tuple)

    if not geo_set1 or not geo_set2:
        return 0.0

    # Calculate Jaccard similarity for exact matches
    intersection = len(geo_set1 & geo_set2)
    union = len(geo_set1 | geo_set2)
    exact_similarity = intersection / union if union > 0 else 0.0

    # Also check for partial matches (same country, different state)
    partial_matches = 0
    for geo1 in geo_set1:
        for geo2 in geo_set2:
            # Check if they share the same country
            if geo1[0] == geo2[0] and geo1 != geo2:
                partial_matches += 0.5  # Half credit for same country

    # Combine exact and partial similarity
    total_similarity = exact_similarity + (partial_matches / union if union > 0 else 0.0)

    return min(total_similarity, 1.0)  # Cap at 1.0


def deduplicate_events(
    events: list[EventCard], db: Database
) -> tuple[list[EventCard], list[EventCard]]:
    """
    Deduplicate a list of events.

    Args:
        events: List of EventCards to deduplicate
        db: Database instance

    Returns:
        Tuple of (unique_events, duplicate_events)
    """
    unique_events = []
    duplicate_events = []

    for event in events:
        if is_duplicate(event, db):
            duplicate_events.append(event)
        else:
            unique_events.append(event)

    return unique_events, duplicate_events


def deduplicate_events_in_memory(
    events: list[EventCard],
) -> tuple[list[EventCard], list[EventCard]]:
    """
    Deduplicate events in memory without database access.

    Args:
        events: List of EventCards to deduplicate

    Returns:
        Tuple of (unique_events, duplicate_events)
    """
    unique_events = []
    duplicate_events = []
    seen_hashes = set()

    for event in events:
        if event.content_hash in seen_hashes:
            duplicate_events.append(event)
        else:
            unique_events.append(event)
            seen_hashes.add(event.content_hash)

    return unique_events, duplicate_events
