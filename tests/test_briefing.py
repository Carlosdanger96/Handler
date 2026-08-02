"""
Tests for the briefing module.

This module tests the Markdown briefing generation functionality,
ensuring that briefings are correctly formatted and contain all required information.
"""

import pytest
from datetime import datetime

from outbreak_intel.models import (
    EventCard,
    EventType,
    PriorityBand,
    ReviewStatus,
    Geography,
    ExplicitFact,
)
from outbreak_intel.briefing.markdown import (
    generate_briefing,
    generate_demo_briefing,
    BriefingOptions,
)
from outbreak_intel.db import Database
import tempfile
import os


@pytest.fixture
def temp_db_with_events():
    """Create a temporary database with sample events for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database(db_path)

    # Add sample events
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Urgent event
    urgent_event = EventCard(
        event_id="urgent_001",
        source_id="cdc_han",
        source_name="CDC Health Alert Network",
        source_url="https://emergency.cdc.gov/han/urgent",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="Urgent Health Alert",
        disease_or_hazard="Ebola",
        event_type=EventType.HEALTH_ALERT,
        geographies=[Geography(country="United States", state="Idaho")],
        case_count=100,
        death_count=5,
        affected_settings=["healthcare", "public_health"],
        official_source="CDC Health Alert Network",
        explicit_facts=[
            ExplicitFact(
                fact_text="100 cases confirmed",
                fact_type="case_count",
                source_attribution="CDC",
                confidence="high",
            )
        ],
        unknowns=["Source unknown"],
        relevance_reasons=["CDC Health Alert", "Idaho relevance", "Healthcare relevance"],
        priority_score=85,
        priority_band=PriorityBand.URGENT_HUMAN_REVIEW,
        summary="Urgent health alert from CDC",
        content_hash="urgent_hash",
        review_status=ReviewStatus.PENDING,
        raw_content="Urgent content",
        metadata={"test": True},
    )
    db.save_event(urgent_event)

    # Review today event
    review_event = EventCard(
        event_id="review_001",
        source_id="idaho_dhw",
        source_name="Idaho Department of Health and Welfare",
        source_url="https://healthandwelfare.idaho.gov/review",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="Measles Advisory",
        disease_or_hazard="Measles",
        event_type=EventType.ADVISORY,
        geographies=[Geography(country="United States", state="Idaho", county="Ada County")],
        case_count=5,
        death_count=None,
        affected_settings=["public_health", "community"],
        official_source="Idaho DHW",
        explicit_facts=[
            ExplicitFact(
                fact_text="5 cases confirmed",
                fact_type="case_count",
                source_attribution="Idaho DHW",
                confidence="high",
            )
        ],
        unknowns=["Source unknown"],
        relevance_reasons=["Idaho relevance", "Healthcare relevance"],
        priority_score=60,
        priority_band=PriorityBand.REVIEW_TODAY,
        summary="Measles advisory from Idaho DHW",
        content_hash="review_hash",
        review_status=ReviewStatus.PENDING,
        raw_content="Review content",
        metadata={"test": True},
    )
    db.save_event(review_event)

    # Monitor event
    monitor_event = EventCard(
        event_id="monitor_001",
        source_id="who_don",
        source_name="WHO Disease Outbreak News",
        source_url="https://www.who.int/monitor",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="International Outbreak",
        disease_or_hazard="Dengue",
        event_type=EventType.OUTBREAK,
        geographies=[Geography(country="Brazil")],
        case_count=50,
        death_count=None,
        affected_settings=["public_health"],
        official_source="WHO",
        explicit_facts=[
            ExplicitFact(
                fact_text="50 cases reported",
                fact_type="case_count",
                source_attribution="WHO",
                confidence="high",
            )
        ],
        unknowns=[],
        relevance_reasons=["WHO Disease Outbreak News"],
        priority_score=30,
        priority_band=PriorityBand.MONITOR,
        summary="International dengue outbreak",
        content_hash="monitor_hash",
        review_status=ReviewStatus.PENDING,
        raw_content="Monitor content",
        metadata={"test": True},
    )
    db.save_event(monitor_event)

    yield db

    # Clean up
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestGenerateBriefing:
    """Test briefing generation."""

    def test_generate_briefing_basic(self, temp_db_with_events):
        """Test basic briefing generation."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        briefing = generate_briefing(temp_db_with_events, today)

        assert isinstance(briefing, str)
        assert len(briefing) > 0

        # Check for required sections
        assert "# Public Health Outbreak Intelligence Brief" in briefing
        assert "## 🔴 Urgent Human Review" in briefing
        assert "## 🟡 Review Today" in briefing
        assert "## 🟢 Monitor" in briefing
        assert "## Source Health" in briefing
        assert "## Summary" in briefing

        # Check for disclaimer
        assert "DISCLAIMER" in briefing
        assert "decision-support" in briefing
        assert "human review" in briefing

    def test_generate_briefing_with_options(self, temp_db_with_events):
        """Test briefing generation with options."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        options = BriefingOptions(
            min_score=50,
            include_archive=False,
            include_source_health=True,
            max_events_per_section=10,
        )

        briefing = generate_briefing(temp_db_with_events, today, options)

        assert isinstance(briefing, str)
        assert len(briefing) > 0

        # Should include urgent and review today, but not monitor (score < 50)
        assert "## 🔴 Urgent Human Review" in briefing
        assert "## 🟡 Review Today" in briefing
        # Monitor event has score 30, so should not be included with min_score=50
        assert "International Outbreak" not in briefing

    def test_generate_briefing_include_archive(self, temp_db_with_events):
        """Test briefing generation with archive included."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Add an archive event
        archive_event = EventCard(
            event_id="archive_001",
            source_id="cdc_outbreaks",
            source_name="CDC Outbreak Investigations",
            source_url="https://www.cdc.gov/outbreaks/archive",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Routine Investigation",
            disease_or_hazard="Salmonella",
            event_type=EventType.INVESTIGATION,
            geographies=[Geography(country="United States")],
            case_count=10,
            death_count=None,
            affected_settings=["public_health"],
            official_source="CDC",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["CDC Outbreak Investigation"],
            priority_score=15,
            priority_band=PriorityBand.ARCHIVE,
            summary="Routine investigation",
            content_hash="archive_hash",
            review_status=ReviewStatus.PENDING,
            raw_content="Archive content",
            metadata={"test": True},
        )
        temp_db_with_events.save_event(archive_event)

        options = BriefingOptions(include_archive=True)
        briefing = generate_briefing(temp_db_with_events, today, options)

        assert "## ⚪ Archive" in briefing
        assert "Routine Investigation" in briefing


class TestGenerateDemoBriefing:
    """Test demo briefing generation."""

    def test_generate_demo_briefing(self):
        """Test demo briefing generation."""
        briefing = generate_demo_briefing()

        assert isinstance(briefing, str)
        assert len(briefing) > 0

        # Check for demo content
        assert "DEMO" in briefing
        assert "CDC Health Alert" in briefing
        assert "Idaho DHW" in briefing
        assert "WHO DON" in briefing

        # Check for required sections
        assert "# Public Health Outbreak Intelligence Brief" in briefing
        assert "## 🔴 Urgent Human Review" in briefing
        assert "## 🟡 Review Today" in briefing
        assert "## 🟢 Monitor" in briefing
        assert "## Source Health" in briefing
        assert "## Summary" in briefing

        # Check for disclaimer
        assert "DISCLAIMER" in briefing


class TestBriefingContent:
    """Test briefing content formatting."""

    def test_event_formatting(self, temp_db_with_events):
        """Test that events are properly formatted in briefing."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        briefing = generate_briefing(temp_db_with_events, today)

        # Check for event links
        assert "[Urgent Health Alert](https://emergency.cdc.gov/han/urgent)" in briefing
        assert "[Measles Advisory](https://healthandwelfare.idaho.gov/review)" in briefing
        assert "[International Outbreak](https://www.who.int/monitor)" in briefing

        # Check for event details
        assert "**Why surfaced**" in briefing
        assert "**Disease/Hazard**" in briefing
        assert "**Type**" in briefing
        assert "**Source**" in briefing
        assert "**Geography**" in briefing
        assert "**Explicit facts**" in briefing
        assert "**Counts**" in briefing
        assert "**Score**" in briefing

    def test_score_display(self, temp_db_with_events):
        """Test that scores are displayed correctly."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        briefing = generate_briefing(temp_db_with_events, today)

        # Check for score displays
        assert "85/100" in briefing
        assert "60/100" in briefing
        assert "30/100" in briefing


class TestBriefingEdgeCases:
    """Test briefing edge cases."""

    def test_empty_database(self):
        """Test briefing with empty database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db = Database(db_path)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            briefing = generate_briefing(db, today)

            assert isinstance(briefing, str)
            assert len(briefing) > 0
            assert "No events" not in briefing  # Should still have structure

        finally:
            db.close()
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_no_events_for_date(self, temp_db_with_events):
        """Test briefing for date with no events."""
        # Use a future date that should have no events
        future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
        briefing = generate_briefing(temp_db_with_events, future_date)

        assert isinstance(briefing, str)
        assert len(briefing) > 0
        assert future_date in briefing

    def test_briefing_with_min_score(self, temp_db_with_events):
        """Test briefing with minimum score filter."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Only include events with score >= 80
        options = BriefingOptions(min_score=80)
        briefing = generate_briefing(temp_db_with_events, today, options)

        # Should only include urgent event (score 85)
        assert "Urgent Health Alert" in briefing
        assert "Measles Advisory" not in briefing
        assert "International Outbreak" not in briefing


# Import timedelta for the test above
from datetime import timedelta
