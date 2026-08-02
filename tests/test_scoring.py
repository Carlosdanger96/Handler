"""
Tests for the scoring module.

This module tests the deterministic scoring functionality,
ensuring that events are scored correctly and consistently.
"""

import pytest
from datetime import datetime

from outbreak_intel.models import EventCard, EventType, PriorityBand, ReviewStatus, Geography
from outbreak_intel.triage.scoring import (
    score_event,
    calculate_priority_band,
    ScoringResult,
    update_event_with_score,
)
from outbreak_intel.config import AppConfig


@pytest.fixture
def base_config():
    """Create a base configuration for testing."""
    return AppConfig()


@pytest.fixture
def idaho_event():
    """Create a sample event with Idaho relevance."""
    return EventCard(
        event_id="idaho_event_001",
        source_id="idaho_dhw",
        source_name="Idaho Department of Health and Welfare",
        source_url="https://healthandwelfare.idaho.gov/test",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="Measles Outbreak in Ada County, Idaho",
        disease_or_hazard="Measles",
        event_type=EventType.OUTBREAK,
        geographies=[
            Geography(country="United States", state="Idaho", county="Ada County"),
            Geography(region="Pacific Northwest"),
        ],
        case_count=15,
        death_count=None,
        affected_settings=["healthcare", "public_health", "community"],
        official_source="Idaho Department of Health and Welfare",
        explicit_facts=[],
        unknowns=["Source of infection unknown"],
        relevance_reasons=["Idaho Department of Health and Welfare", "Idaho relevance"],
        priority_score=0,
        priority_band=PriorityBand.ARCHIVE,
        summary="Measles outbreak in Ada County, Idaho",
        content_hash="test_hash_idaho",
        review_status=ReviewStatus.PENDING,
        raw_content="Test content",
        metadata={"test": True},
    )


@pytest.fixture
def cdc_han_event():
    """Create a sample CDC HAN event."""
    return EventCard(
        event_id="cdc_han_event_001",
        source_id="cdc_han",
        source_name="CDC Health Alert Network",
        source_url="https://emergency.cdc.gov/han/test",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="CDC Health Alert: Respiratory Illness Surge",
        disease_or_hazard="Respiratory Syncytial Virus",
        event_type=EventType.HEALTH_ALERT,
        geographies=[Geography(country="United States")],
        case_count=500,
        death_count=10,
        affected_settings=["healthcare", "public_health"],
        official_source="CDC Health Alert Network",
        explicit_facts=[],
        unknowns=["Cause of surge unknown"],
        relevance_reasons=["CDC Health Alert Network"],
        priority_score=0,
        priority_band=PriorityBand.ARCHIVE,
        summary="CDC Health Alert about respiratory illness surge",
        content_hash="test_hash_cdc",
        review_status=ReviewStatus.PENDING,
        raw_content="Test content",
        metadata={"test": True},
    )


@pytest.fixture
def who_event():
    """Create a sample WHO event with US relevance."""
    return EventCard(
        event_id="who_event_001",
        source_id="who_don",
        source_name="WHO Disease Outbreak News",
        source_url="https://www.who.int/test",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="Avian Influenza in Europe with US Travel Implications",
        disease_or_hazard="Avian Influenza H5N1",
        event_type=EventType.OUTBREAK,
        geographies=[
            Geography(country="France"),
            Geography(country="Germany"),
            Geography(country="United States"),  # US relevance
        ],
        case_count=None,
        death_count=None,
        affected_settings=["agriculture", "public_health"],
        official_source="World Health Organization",
        explicit_facts=[],
        unknowns=["Risk to humans being assessed"],
        relevance_reasons=["WHO Disease Outbreak News", "US travel/importation relevance"],
        priority_score=0,
        priority_band=PriorityBand.ARCHIVE,
        summary="WHO report on avian influenza with US travel implications",
        content_hash="test_hash_who",
        review_status=ReviewStatus.PENDING,
        raw_content="Test content",
        metadata={"test": True},
    )


@pytest.fixture
def low_priority_event():
    """Create a sample low-priority event."""
    return EventCard(
        event_id="low_priority_001",
        source_id="cdc_outbreaks",
        source_name="CDC Outbreak Investigations",
        source_url="https://www.cdc.gov/outbreaks/test",
        source_published_at=datetime.utcnow(),
        retrieved_at=datetime.utcnow(),
        title="Routine Foodborne Illness Investigation",
        disease_or_hazard="Salmonella",
        event_type=EventType.INVESTIGATION,
        geographies=[Geography(country="United States", state="California")],
        case_count=25,
        death_count=None,
        affected_settings=["public_health", "food_safety"],
        official_source="CDC Outbreak Investigations",
        explicit_facts=[],
        unknowns=[],
        relevance_reasons=["CDC Outbreak Investigation"],
        priority_score=0,
        priority_band=PriorityBand.ARCHIVE,
        summary="Routine investigation of salmonella outbreak",
        content_hash="test_hash_low",
        review_status=ReviewStatus.PENDING,
        raw_content="Test content",
        metadata={"test": True},
    )


class TestCalculatePriorityBand:
    """Test priority band calculation."""

    def test_urgent_band(self, base_config):
        """Test urgent priority band."""
        band = calculate_priority_band(85, base_config)
        assert band == PriorityBand.URGENT_HUMAN_REVIEW

        band = calculate_priority_band(75, base_config)
        assert band == PriorityBand.URGENT_HUMAN_REVIEW

        band = calculate_priority_band(100, base_config)
        assert band == PriorityBand.URGENT_HUMAN_REVIEW

    def test_review_today_band(self, base_config):
        """Test review today priority band."""
        band = calculate_priority_band(50, base_config)
        assert band == PriorityBand.REVIEW_TODAY

        band = calculate_priority_band(45, base_config)
        assert band == PriorityBand.REVIEW_TODAY

        band = calculate_priority_band(74, base_config)
        assert band == PriorityBand.REVIEW_TODAY

    def test_monitor_band(self, base_config):
        """Test monitor priority band."""
        band = calculate_priority_band(30, base_config)
        assert band == PriorityBand.MONITOR

        band = calculate_priority_band(20, base_config)
        assert band == PriorityBand.MONITOR

        band = calculate_priority_band(44, base_config)
        assert band == PriorityBand.MONITOR

    def test_archive_band(self, base_config):
        """Test archive priority band."""
        band = calculate_priority_band(10, base_config)
        assert band == PriorityBand.ARCHIVE

        band = calculate_priority_band(0, base_config)
        assert band == PriorityBand.ARCHIVE

        band = calculate_priority_band(19, base_config)
        assert band == PriorityBand.ARCHIVE


class TestScoreEvent:
    """Test event scoring."""

    def test_idaho_event_scoring(self, idaho_event, base_config):
        """Test scoring of Idaho event."""
        result = score_event(idaho_event, base_config)

        assert isinstance(result, ScoringResult)
        assert result.total_score > 0
        assert result.priority_band == PriorityBand.URGENT_HUMAN_REVIEW
        assert len(result.contributions) > 0
        assert len(result.reasons) > 0

        # Idaho event should score high due to Idaho relevance
        assert result.total_score >= 75

    def test_cdc_han_event_scoring(self, cdc_han_event, base_config):
        """Test scoring of CDC HAN event."""
        result = score_event(cdc_han_event, base_config)

        assert isinstance(result, ScoringResult)
        assert result.total_score > 0

        # CDC HAN with high case count and deaths should score moderately high
        # Without Idaho relevance, max score is healthcare(25) + urgency(20) + travel(10) = 55
        assert result.total_score >= 50

    def test_who_event_scoring(self, who_event, base_config):
        """Test scoring of WHO event with US relevance."""
        result = score_event(who_event, base_config)

        assert isinstance(result, ScoringResult)
        assert result.total_score > 0

        # WHO event with US relevance should score moderately
        # Without healthcare or Idaho relevance, max score is urgency(15) + travel(10) = 25
        assert result.total_score >= 20
        assert result.total_score < 75

    def test_low_priority_event_scoring(self, low_priority_event, base_config):
        """Test scoring of low priority event."""
        result = score_event(low_priority_event, base_config)

        assert isinstance(result, ScoringResult)
        assert result.total_score > 0

        # Routine investigation should score lower
        assert result.total_score < 45


class TestScoringContributions:
    """Test individual scoring contributions."""

    def test_idaho_relevance_contribution(self, idaho_event, base_config):
        """Test Idaho relevance contribution."""
        result = score_event(idaho_event, base_config)

        # Idaho event should have Idaho/PNW relevance contribution
        assert "idaho_pnw_relevance" in result.contributions
        assert result.contributions["idaho_pnw_relevance"] > 0

    def test_healthcare_relevance_contribution(self, cdc_han_event, base_config):
        """Test healthcare relevance contribution."""
        result = score_event(cdc_han_event, base_config)

        # CDC HAN event with healthcare settings should have healthcare contribution
        assert "healthcare_ip_relevance" in result.contributions
        assert result.contributions["healthcare_ip_relevance"] > 0

    def test_urgency_contribution(self, cdc_han_event, base_config):
        """Test urgency contribution."""
        result = score_event(cdc_han_event, base_config)

        # Health alert event type should have urgency contribution
        assert "official_urgency" in result.contributions
        assert result.contributions["official_urgency"] > 0

    def test_travel_relevance_contribution(self, who_event, base_config):
        """Test travel relevance contribution."""
        result = score_event(who_event, base_config)

        # WHO event with US geography should have travel contribution
        assert "travel_relevance" in result.contributions
        assert result.contributions["travel_relevance"] > 0


class TestUpdateEventWithScore:
    """Test updating events with scores."""

    def test_update_event_with_score(self, idaho_event, base_config):
        """Test updating an event with its score."""
        updated_event = update_event_with_score(idaho_event, base_config)

        assert updated_event.priority_score > 0
        assert updated_event.priority_band != PriorityBand.ARCHIVE
        assert len(updated_event.relevance_reasons) > len(idaho_event.relevance_reasons)
        assert "scoring" in updated_event.metadata

    def test_score_consistency(self, idaho_event, base_config):
        """Test that scoring is consistent."""
        # Score the same event multiple times
        result1 = score_event(idaho_event, base_config)
        result2 = score_event(idaho_event, base_config)

        assert result1.total_score == result2.total_score
        assert result1.priority_band == result2.priority_band


class TestScoringEdgeCases:
    """Test edge cases in scoring."""

    def test_minimum_score(self, base_config):
        """Test minimum possible score."""
        # Create an event with minimal scoring factors
        event = EventCard(
            event_id="min_score_001",
            source_id="test",
            source_name="Test",
            source_url="https://test.com",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Test Event",
            disease_or_hazard=None,
            event_type=EventType.UPDATE,
            geographies=[Geography(country="Other")],
            case_count=None,
            death_count=None,
            affected_settings=[],
            official_source="Test",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=[],
            priority_score=0,
            priority_band=PriorityBand.ARCHIVE,
            summary="Test",
            content_hash="test",
            review_status=ReviewStatus.PENDING,
            raw_content="Test",
            metadata={},
        )

        result = score_event(event, base_config)
        assert result.total_score >= 0
        assert result.total_score <= 100

    def test_maximum_score(self, base_config):
        """Test maximum possible score."""
        # Create an event that should score maximum
        event = EventCard(
            event_id="max_score_001",
            source_id="idaho_dhw",
            source_name="Idaho Department of Health and Welfare",
            source_url="https://idaho.gov/health",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Idaho Healthcare Emergency: Novel Pathogen Outbreak",
            disease_or_hazard="Novel Coronavirus",
            event_type=EventType.HEALTH_ALERT,
            geographies=[
                Geography(country="United States", state="Idaho"),
                Geography(region="Pacific Northwest"),
            ],
            case_count=10000,
            death_count=100,
            affected_settings=["healthcare", "public_health", "hospitals"],
            official_source="Idaho Department of Health and Welfare",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=["Idaho relevance", "Healthcare relevance"],
            priority_score=0,
            priority_band=PriorityBand.ARCHIVE,
            summary="Major healthcare emergency in Idaho",
            content_hash="test",
            review_status=ReviewStatus.PENDING,
            raw_content="Test",
            metadata={},
        )

        result = score_event(event, base_config)
        assert result.total_score <= 100
        assert result.total_score >= 75  # Should be urgent


class TestCustomScoringConfig:
    """Test scoring with custom configuration."""

    def test_custom_weights(self):
        """Test scoring with custom weights."""
        # Create custom config with different weights
        custom_config = AppConfig(
            scoring=AppConfig().scoring.model_copy(
                update={
                    "idaho_pnw_weight": 50,
                    "healthcare_ip_weight": 30,
                    "official_urgency_weight": 10,
                    "travel_weight": 5,
                    "novelty_weight": 5,
                }
            )
        )

        # Create an Idaho event
        event = EventCard(
            event_id="custom_001",
            source_id="idaho_dhw",
            source_name="Idaho Department of Health and Welfare",
            source_url="https://idaho.gov",
            source_published_at=datetime.utcnow(),
            retrieved_at=datetime.utcnow(),
            title="Idaho Health Alert",
            disease_or_hazard="Test",
            event_type=EventType.HEALTH_ALERT,
            geographies=[Geography(country="United States", state="Idaho")],
            case_count=None,
            death_count=None,
            affected_settings=["healthcare"],
            official_source="Idaho DHW",
            explicit_facts=[],
            unknowns=[],
            relevance_reasons=[],
            priority_score=0,
            priority_band=PriorityBand.ARCHIVE,
            summary="Test",
            content_hash="test",
            review_status=ReviewStatus.PENDING,
            raw_content="Test",
            metadata={},
        )

        result = score_event(event, custom_config)

        # With higher Idaho weight, this should score higher
        assert result.total_score > 0
        assert result.contributions["idaho_pnw_relevance"] > 35  # Higher than default
