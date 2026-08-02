"""
Tests for the deduplication module.

This module tests the deduplication functionality,
ensuring that duplicate events are correctly identified and handled.
"""

import pytest
from datetime import datetime, timedelta

from outbreak_intel.models import EventCard, PriorityBand, ReviewStatus, Geography
from outbreak_intel.triage.dedup import (
    is_duplicate,
    deduplicate_events_in_memory,
    _text_similarity,
    _hash_similarity,
    _geography_similarity,
)
from outbreak_intel.db import Database
import tempfile
import os


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    yield db

    # Clean up
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return EventCard(
        event_id="test_event_001",
        source_id="test_source",
        source_name="Test Source",
        source_url="https://example.com/test",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="Test Event",
        disease_or_hazard="Test Disease",
        event_type="outbreak",
        geographies=[Geography(country="United States")],
        case_count=10,
        death_count=1,
        affected_settings=["healthcare"],
        official_source="Test Authority",
        explicit_facts=[],
        unknowns=[],
        relevance_reasons=["test"],
        priority_score=50,
        priority_band=PriorityBand.REVIEW_TODAY,
        summary="Test summary",
        content_hash=EventCard.generate_content_hash("Test content", "https://example.com/test"),
        review_status=ReviewStatus.PENDING,
        raw_content="Test content",
        metadata={"test": True},
    )


class TestTextSimilarity:
    """Test text similarity calculations."""

    def test_identical_texts(self):
        """Test similarity of identical texts."""
        similarity = _text_similarity("hello world", "hello world")
        assert similarity == 1.0

    def test_completely_different_texts(self):
        """Test similarity of completely different texts."""
        similarity = _text_similarity("hello world", "goodbye moon")
        assert similarity == 0.0

    def test_partial_similarity(self):
        """Test partial similarity."""
        similarity = _text_similarity("hello world", "hello there world")
        assert similarity > 0.0
        assert similarity < 1.0

    def test_empty_texts(self):
        """Test similarity with empty texts."""
        similarity = _text_similarity("", "hello")
        assert similarity == 0.0
        similarity = _text_similarity("", "")
        assert similarity == 0.0


class TestHashSimilarity:
    """Test hash similarity calculations."""

    def test_identical_hashes(self):
        """Test similarity of identical hashes."""
        hash1 = "abc123def456"
        similarity = _hash_similarity(hash1, hash1)
        assert similarity == 1.0

    def test_completely_different_hashes(self):
        """Test similarity of completely different hashes."""
        hash1 = "abc123def456"
        hash2 = "xyz789uvw012"
        similarity = _hash_similarity(hash1, hash2)
        assert similarity == 0.0

    def test_partial_hash_similarity(self):
        """Test partial hash similarity."""
        hash1 = "abc123def456"
        hash2 = "abc123xyz789"
        similarity = _hash_similarity(hash1, hash2)
        assert similarity > 0.0
        assert similarity < 1.0

    def test_different_length_hashes(self):
        """Test similarity with different length hashes."""
        hash1 = "abc123"
        hash2 = "abc123def456"
        similarity = _hash_similarity(hash1, hash2)
        assert similarity == 0.0


class TestGeographySimilarity:
    """Test geography similarity calculations."""

    def test_identical_geographies(self):
        """Test similarity of identical geographies."""
        geos1 = [Geography(country="United States", state="Idaho")]
        geos2 = [Geography(country="United States", state="Idaho")]
        similarity = _geography_similarity(geos1, geos2)
        assert similarity == 1.0

    def test_different_geographies(self):
        """Test similarity of different geographies."""
        geos1 = [Geography(country="United States")]
        geos2 = [Geography(country="Canada")]
        similarity = _geography_similarity(geos1, geos2)
        assert similarity == 0.0

    def test_partial_geography_similarity(self):
        """Test partial geography similarity."""
        geos1 = [Geography(country="United States", state="Idaho")]
        geos2 = [Geography(country="United States", state="Washington")]
        similarity = _geography_similarity(geos1, geos2)
        assert similarity > 0.0
        assert similarity < 1.0

    def test_empty_geographies(self):
        """Test similarity with empty geographies."""
        geos1 = []
        geos2 = [Geography(country="United States")]
        similarity = _geography_similarity(geos1, geos2)
        assert similarity == 0.0


class TestDeduplicationInMemory:
    """Test in-memory deduplication."""

    def test_identical_content_hashes(self, sample_event):
        """Test deduplication of events with identical content hashes."""
        event2 = EventCard(
            event_id="test_event_002",
            source_id="test_source",
            source_name="Test Source",
            source_url="https://example.com/test2",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Different Title",
            disease_or_hazard="Test Disease",
            event_type="outbreak",
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=1,
            affected_settings=["healthcare"],
            official_source="Test Authority",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["test"],
            priority_score=50,
            priority_band=PriorityBand.REVIEW_TODAY,
            summary="Test summary",
            content_hash=sample_event.content_hash,  # Same hash
            review_status=ReviewStatus.PENDING,
            raw_content="Different content",
            metadata={"test": True},
        )

        events = [sample_event, event2]
        unique, duplicates = deduplicate_events_in_memory(events)

        assert len(unique) == 1
        assert len(duplicates) == 1
        assert unique[0].event_id == sample_event.event_id
        assert duplicates[0].event_id == event2.event_id

    def test_different_content_hashes(self, sample_event):
        """Test deduplication of events with different content hashes."""
        event2 = EventCard(
            event_id="test_event_002",
            source_id="test_source",
            source_name="Test Source",
            source_url="https://example.com/test2",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Different Title",
            disease_or_hazard="Test Disease",
            event_type="outbreak",
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=1,
            affected_settings=["healthcare"],
            official_source="Test Authority",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["test"],
            priority_score=50,
            priority_band=PriorityBand.REVIEW_TODAY,
            summary="Test summary",
            content_hash=EventCard.generate_content_hash(
                "Different content", "https://example.com/test2"
            ),
            review_status=ReviewStatus.PENDING,
            raw_content="Different content",
            metadata={"test": True},
        )

        events = [sample_event, event2]
        unique, duplicates = deduplicate_events_in_memory(events)

        assert len(unique) == 2
        assert len(duplicates) == 0

    def test_multiple_duplicates(self, sample_event):
        """Test deduplication with multiple duplicates."""
        event2 = EventCard(
            event_id="test_event_002",
            source_id="test_source",
            source_name="Test Source",
            source_url="https://example.com/test2",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Different Title",
            disease_or_hazard="Test Disease",
            event_type="outbreak",
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=1,
            affected_settings=["healthcare"],
            official_source="Test Authority",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["test"],
            priority_score=50,
            priority_band=PriorityBand.REVIEW_TODAY,
            summary="Test summary",
            content_hash=sample_event.content_hash,  # Same hash
            review_status=ReviewStatus.PENDING,
            raw_content="Different content",
            metadata={"test": True},
        )

        event3 = EventCard(
            event_id="test_event_003",
            source_id="test_source",
            source_name="Test Source",
            source_url="https://example.com/test3",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Another Title",
            disease_or_hazard="Test Disease",
            event_type="outbreak",
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=1,
            affected_settings=["healthcare"],
            official_source="Test Authority",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["test"],
            priority_score=50,
            priority_band=PriorityBand.REVIEW_TODAY,
            summary="Test summary",
            content_hash=sample_event.content_hash,  # Same hash
            review_status=ReviewStatus.PENDING,
            raw_content="Another content",
            metadata={"test": True},
        )

        events = [sample_event, event2, event3]
        unique, duplicates = deduplicate_events_in_memory(events)

        assert len(unique) == 1
        assert len(duplicates) == 2


class TestDeduplicationWithDatabase:
    """Test deduplication with database."""

    def test_is_duplicate_with_db(self, temp_db, sample_event):
        """Test duplicate detection with database."""
        # Save the sample event to database
        temp_db.save_event(sample_event)

        # Create a duplicate event
        duplicate_event = EventCard(
            event_id="test_event_002",
            source_id="test_source",
            source_name="Test Source",
            source_url="https://example.com/test2",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Different Title",
            disease_or_hazard="Test Disease",
            event_type="outbreak",
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=1,
            affected_settings=["healthcare"],
            official_source="Test Authority",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["test"],
            priority_score=50,
            priority_band=PriorityBand.REVIEW_TODAY,
            summary="Test summary",
            content_hash=sample_event.content_hash,  # Same hash
            review_status=ReviewStatus.PENDING,
            raw_content="Different content",
            metadata={"test": True},
        )

        # Check if duplicate
        is_dup = is_duplicate(duplicate_event, temp_db)
        assert is_dup is True

    def test_is_not_duplicate_with_db(self, temp_db, sample_event):
        """Test non-duplicate detection with database."""
        # Save the sample event to database
        temp_db.save_event(sample_event)

        # Create a unique event
        unique_event = EventCard(
            event_id="test_event_002",
            source_id="test_source",
            source_name="Test Source",
            source_url="https://example.com/test2",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Different Title",
            disease_or_hazard="Test Disease",
            event_type="outbreak",
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=1,
            affected_settings=["healthcare"],
            official_source="Test Authority",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["test"],
            priority_score=50,
            priority_band=PriorityBand.REVIEW_TODAY,
            summary="Test summary",
            content_hash=EventCard.generate_content_hash(
                "Different content", "https://example.com/test2"
            ),
            review_status=ReviewStatus.PENDING,
            raw_content="Different content",
            metadata={"test": True},
        )

        # Check if duplicate
        is_dup = is_duplicate(unique_event, temp_db)
        assert is_dup is False
