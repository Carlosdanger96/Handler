"""
Data models for Public Health Outbreak Intelligence.

This module defines the core Pydantic models used throughout the system,
ensuring type safety and data validation for all outbreak intelligence data.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict
import hashlib
import json


class PriorityBand(str, Enum):
    """Priority bands for event triage."""

    URGENT_HUMAN_REVIEW = "urgent_human_review"
    REVIEW_TODAY = "review_today"
    MONITOR = "monitor"
    ARCHIVE = "archive"


class ReviewStatus(str, Enum):
    """Review status for events."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"


class EventType(str, Enum):
    """Types of public health events."""

    OUTBREAK = "outbreak"
    HEALTH_ALERT = "health_alert"
    INVESTIGATION = "investigation"
    ADVISORY = "advisory"
    UPDATE = "update"
    UNKNOWN = "unknown"


class SourceConfig(BaseModel):
    """Configuration for a data source."""

    source_id: str = Field(..., description="Unique identifier for the source")
    source_name: str = Field(..., description="Human-readable name of the source")
    source_url: str = Field(..., description="Base URL for the source")
    feed_url: Optional[str] = Field(None, description="RSS/Atom feed URL if available")
    enabled: bool = Field(True, description="Whether this source is enabled")
    priority: int = Field(1, description="Source priority (1-10)")
    timeout: int = Field(30, description="HTTP timeout in seconds")
    user_agent: Optional[str] = Field(None, description="Custom user agent for this source")

    model_config = ConfigDict(frozen=True)


class Geography(BaseModel):
    """Geographic information for an event."""

    country: Optional[str] = Field(None, description="Country name")
    state: Optional[str] = Field(None, description="State or province")
    county: Optional[str] = Field(None, description="County or local region")
    city: Optional[str] = Field(None, description="City or municipality")
    region: Optional[str] = Field(None, description="Broader region (e.g., Pacific Northwest)")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")


class ExplicitFact(BaseModel):
    """A single explicit fact extracted from a source."""

    fact_text: str = Field(..., description="The factual statement")
    fact_type: str = Field(
        ..., description="Type of fact (e.g., case_count, death_count, transmission)"
    )
    source_attribution: str = Field(..., description="Source attribution for this fact")
    confidence: str = Field("high", description="Confidence level: high, medium, low")


class EventCard(BaseModel):
    """
    Core data model representing a normalized public health event.

    This model captures all essential information about a public health notice
    and provides deterministic methods for hashing and comparison.
    """

    event_id: str = Field(..., description="Unique identifier for this event")
    source_id: str = Field(..., description="ID of the source that provided this event")
    source_name: str = Field(..., description="Human-readable name of the source")
    source_url: str = Field(..., description="URL of the original source notice")
    source_published_at: Optional[datetime] = Field(
        None, description="When the source published this notice"
    )
    retrieved_at: datetime = Field(..., description="When this event was retrieved/ingested")
    title: str = Field(..., description="Title of the event/notice")
    disease_or_hazard: Optional[str] = Field(None, description="Primary disease or hazard involved")
    event_type: EventType = Field(EventType.UNKNOWN, description="Type of event")
    geographies: list[Geography] = Field(
        default_factory=list, description="Affected geographic areas"
    )
    case_count: Optional[int] = Field(None, description="Number of cases (if explicitly stated)")
    death_count: Optional[int] = Field(None, description="Number of deaths (if explicitly stated)")
    affected_settings: list[str] = Field(
        default_factory=list, description="Settings affected (e.g., healthcare, schools)"
    )
    official_source: str = Field(..., description="Official source organization")
    explicit_facts: list[ExplicitFact] = Field(
        default_factory=list, description="Explicit facts from the source"
    )
    unknowns: list[str] = Field(
        default_factory=list, description="Explicitly stated unknowns or uncertainties"
    )
    relevance_reasons: list[str] = Field(
        default_factory=list, description="Reasons this event is relevant"
    )
    priority_score: int = Field(0, description="Calculated priority score (0-100)")
    priority_band: PriorityBand = Field(
        PriorityBand.ARCHIVE, description="Priority band based on score"
    )
    summary: str = Field(..., description="Brief summary of the event")
    content_hash: str = Field(..., description="Hash of the content for deduplication")
    review_status: ReviewStatus = Field(ReviewStatus.PENDING, description="Current review status")
    raw_content: Optional[str] = Field(None, description="Raw content from source (for archival)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(frozen=True)

    @classmethod
    def generate_event_id(
        cls, source_id: str, source_url: str, published_at: Optional[datetime] = None
    ) -> str:
        """Generate a deterministic event ID from source information."""
        if published_at:
            timestamp = published_at.isoformat()
        else:
            timestamp = datetime.utcnow().isoformat()

        content = f"{source_id}:{source_url}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @classmethod
    def generate_content_hash(cls, content: str, source_url: str) -> str:
        """Generate a content hash for deduplication."""
        combined = f"{source_url}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, handling datetime serialization."""
        data = self.model_dump()
        if self.source_published_at:
            data["source_published_at"] = self.source_published_at.isoformat()
        data["retrieved_at"] = self.retrieved_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventCard":
        """Create EventCard from dictionary, handling datetime deserialization."""
        if isinstance(data.get("source_published_at"), str):
            data["source_published_at"] = datetime.fromisoformat(data["source_published_at"])
        if isinstance(data.get("retrieved_at"), str):
            data["retrieved_at"] = datetime.fromisoformat(data["retrieved_at"])
        return cls(**data)


class CollectionResult(BaseModel):
    """Result of a collection operation."""

    source_id: str
    source_name: str
    success: bool
    retrieved_at: datetime
    item_count: int = 0
    error_message: Optional[str] = None
    new_events: int = 0
    duplicate_events: int = 0

    model_config = ConfigDict(frozen=True)


class PipelineResult(BaseModel):
    """Result of a complete pipeline run."""

    started_at: datetime
    completed_at: datetime
    collection_results: list[CollectionResult] = Field(default_factory=list)
    total_new_events: int = 0
    total_duplicate_events: int = 0
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
