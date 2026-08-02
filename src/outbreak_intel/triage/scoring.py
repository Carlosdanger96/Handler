"""
Scoring module for Public Health Outbreak Intelligence.

This module implements deterministic, transparent scoring for public health events
based on predefined criteria. All scoring is done in plain Python with no LLM
involvement, ensuring reproducibility and transparency.
"""

from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..models import EventCard, EventType, PriorityBand
from ..config import AppConfig


@dataclass
class ScoringResult:
    """Result of a scoring operation."""

    total_score: int
    priority_band: PriorityBand
    contributions: dict[str, int] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_score": self.total_score,
            "priority_band": self.priority_band.value,
            "contributions": self.contributions,
            "reasons": self.reasons,
        }


def calculate_priority_band(score: int, config: Optional[AppConfig] = None) -> PriorityBand:
    """
    Calculate the priority band based on a score.

    Args:
        score: The numeric score (0-100)
        config: Optional configuration with custom thresholds

    Returns:
        PriorityBand based on the score
    """
    if config is None:
        config = AppConfig()

    if score >= config.scoring.urgent_threshold:
        return PriorityBand.URGENT_HUMAN_REVIEW
    elif score >= config.scoring.review_threshold:
        return PriorityBand.REVIEW_TODAY
    elif score >= config.scoring.monitor_threshold:
        return PriorityBand.MONITOR
    else:
        return PriorityBand.ARCHIVE


def score_event(event: EventCard, config: Optional[AppConfig] = None) -> ScoringResult:
    """
    Score an event based on multiple criteria.

    This function implements transparent, deterministic scoring with the following factors:
    - Idaho / Pacific Northwest relevance: 0-35 points
    - Healthcare or infection-prevention relevance: 0-25 points
    - Official urgency/severity signal: 0-20 points
    - U.S. travel/importation relevance: 0-10 points
    - Novelty: 0-10 points

    Args:
        event: The EventCard to score
        config: Optional configuration with custom weights

    Returns:
        ScoringResult with the calculated score and breakdown
    """
    if config is None:
        config = AppConfig()

    contributions = {}
    reasons = []

    # Idaho / Pacific Northwest relevance (0-35 points)
    idaho_score = _score_idaho_relevance(event, config)
    contributions["idaho_pnw_relevance"] = idaho_score
    if idaho_score > 0:
        reasons.append(f"Idaho/PNW relevance: +{idaho_score}")

    # Healthcare or infection-prevention relevance (0-25 points)
    healthcare_score = _score_healthcare_relevance(event, config)
    contributions["healthcare_ip_relevance"] = healthcare_score
    if healthcare_score > 0:
        reasons.append(f"Healthcare/IP relevance: +{healthcare_score}")

    # Official urgency/severity signal (0-20 points)
    urgency_score = _score_urgency(event, config)
    contributions["official_urgency"] = urgency_score
    if urgency_score > 0:
        reasons.append(f"Official urgency/severity: +{urgency_score}")

    # U.S. travel/importation relevance (0-10 points)
    travel_score = _score_travel_relevance(event, config)
    contributions["travel_relevance"] = travel_score
    if travel_score > 0:
        reasons.append(f"US travel/importation relevance: +{travel_score}")

    # Novelty (0-10 points)
    novelty_score = _score_novelty(event, config)
    contributions["novelty"] = novelty_score
    if novelty_score > 0:
        reasons.append(f"Novelty: +{novelty_score}")

    # Calculate total score
    total_score = sum(contributions.values())

    # Ensure score is within bounds (0-100)
    total_score = max(0, min(100, total_score))

    # Calculate priority band
    priority_band = calculate_priority_band(total_score, config)

    return ScoringResult(
        total_score=total_score,
        priority_band=priority_band,
        contributions=contributions,
        reasons=reasons,
    )


def _score_idaho_relevance(event: EventCard, config: AppConfig) -> int:
    """Score Idaho and Pacific Northwest relevance (0-35 points)."""
    max_score = config.scoring.idaho_pnw_weight
    score = 0

    # Check for explicit Idaho mentions
    idaho_terms = ["idaho", "boise", "meridian", "nampa", "pocatello", "coeur d'alene"]
    text_fields = [
        event.title.lower(),
        event.summary.lower(),
        event.disease_or_hazard or "",
        " ".join([f.fact_text.lower() for f in event.explicit_facts]),
        " ".join(event.unknowns).lower(),
        " ".join(event.relevance_reasons).lower(),
    ]

    for term in idaho_terms:
        for text in text_fields:
            if term in text:
                score = max_score
                break
        if score == max_score:
            break

    # Check geography
    if score < max_score:
        for geo in event.geographies:
            if geo.state == "Idaho" or geo.region == "Idaho":
                score = max_score
                break
            elif geo.region == "Pacific Northwest":
                score = max_score // 2  # Half credit for PNW
                break

    # Check source
    if score < max_score and event.source_id == "idaho_dhw":
        score = max_score

    return score


def _score_healthcare_relevance(event: EventCard, config: AppConfig) -> int:
    """Score healthcare and infection-prevention relevance (0-25 points)."""
    max_score = config.scoring.healthcare_ip_weight
    score = 0

    # Healthcare terms
    healthcare_terms = [
        "healthcare",
        "hospital",
        "clinical",
        "medical",
        "infection",
        "prevention",
        "control",
        "epidemiology",
        "public health",
        "patient",
        "nursing home",
        "long-term care",
        "dialysis",
        "surgery",
        "procedure",
        "treatment",
        "diagnosis",
    ]

    text_fields = [
        event.title.lower(),
        event.summary.lower(),
        event.disease_or_hazard or "",
        " ".join([f.fact_text.lower() for f in event.explicit_facts]),
        " ".join(event.unknowns).lower(),
        " ".join(event.relevance_reasons).lower(),
    ]

    matches = 0
    for term in healthcare_terms:
        for text in text_fields:
            if term in text:
                matches += 1
                break

    # Score based on number of matches
    if matches >= 3:
        score = max_score
    elif matches >= 2:
        score = max_score * 3 // 4
    elif matches >= 1:
        score = max_score // 2

    # Check affected settings
    healthcare_settings = ["healthcare", "hospital", "clinical", "medical"]
    for setting in event.affected_settings:
        if setting.lower() in healthcare_settings:
            score = max_score
            break

    # Check source
    if score < max_score and event.source_id in ["cdc_han", "cdc_outbreaks"]:
        score = max_score * 3 // 4

    return score


def _score_urgency(event: EventCard, config: AppConfig) -> int:
    """Score official urgency and severity signals (0-20 points)."""
    max_score = config.scoring.official_urgency_weight
    score = 0

    # Check event type
    urgency_by_type = {
        EventType.HEALTH_ALERT: max_score,
        EventType.OUTBREAK: max_score * 3 // 4,
        EventType.INVESTIGATION: max_score // 2,
        EventType.ADVISORY: max_score // 4,
        EventType.UPDATE: 0,
    }

    score = urgency_by_type.get(event.event_type, 0)

    # Check source - CDC HAN is typically high urgency
    if event.source_id == "cdc_han":
        score = max(score, max_score * 3 // 4)

    # Check for urgency keywords
    urgency_terms = [
        "urgent",
        "emergency",
        "critical",
        "severe",
        "high alert",
        "immediate action",
        "public health emergency",
        "pandemic",
        "epidemic",
        "widespread",
        "rapid spread",
    ]

    text_fields = [
        event.title.lower(),
        event.summary.lower(),
        " ".join([f.fact_text.lower() for f in event.explicit_facts]),
        " ".join(event.relevance_reasons).lower(),
    ]

    for term in urgency_terms:
        for text in text_fields:
            if term in text:
                score = max(score, max_score * 3 // 4)
                break
        if score >= max_score * 3 // 4:
            break

    # Check case and death counts for severity
    if event.case_count and event.case_count > 100:
        score = max(score, max_score // 2)
    if event.death_count and event.death_count > 0:
        score = max(score, max_score * 3 // 4)
    if event.case_count and event.case_count > 1000:
        score = max(score, max_score)

    return score


def _score_travel_relevance(event: EventCard, config: AppConfig) -> int:
    """Score US travel and importation relevance (0-10 points)."""
    max_score = config.scoring.travel_weight
    score = 0

    # Check for US travel/importation terms
    travel_terms = [
        "united states",
        "usa",
        "us",
        "america",
        "north america",
        "travel",
        "imported",
        "importation",
        "cross-border",
        "international travel",
        "airport",
        "border",
        "port of entry",
    ]

    text_fields = [
        event.title.lower(),
        event.summary.lower(),
        " ".join([f.fact_text.lower() for f in event.explicit_facts]),
        " ".join(event.unknowns).lower(),
        " ".join(event.relevance_reasons).lower(),
    ]

    for term in travel_terms:
        for text in text_fields:
            if term in text:
                score = max_score
                break
        if score == max_score:
            break

    # Check geography for US
    if score < max_score:
        for geo in event.geographies:
            if geo.country == "United States":
                score = max_score
                break

    # WHO DON often has international relevance
    if event.source_id == "who_don":
        score = max(score, max_score // 2)

    return score


def _score_novelty(event: EventCard, config: AppConfig) -> int:
    """Score novelty of the event (0-10 points)."""
    max_score = config.scoring.novelty_weight
    score = 0

    # Check for novelty keywords
    novelty_terms = [
        "novel",
        "new",
        "emerging",
        "unusual",
        "unexpected",
        "first time",
        "first case",
        "first detection",
        "never before",
        "rare",
        "uncommon",
        "atypical",
        "mutant",
        "variant",
    ]

    text_fields = [
        event.title.lower(),
        event.summary.lower(),
        event.disease_or_hazard or "",
        " ".join([f.fact_text.lower() for f in event.explicit_facts]),
        " ".join(event.unknowns).lower(),
    ]

    matches = 0
    for term in novelty_terms:
        for text in text_fields:
            if term in text:
                matches += 1
                break

    # Score based on number of matches
    if matches >= 2:
        score = max_score
    elif matches >= 1:
        score = max_score // 2

    # Check if disease is novel/emerging
    if event.disease_or_hazard:
        novel_diseases = [
            "novel coronavirus",
            "sars-cov-2",
            "covid-19",
            "mpox",
            "emerging pathogen",
            "unknown pathogen",
        ]
        disease_lower = event.disease_or_hazard.lower()
        for novel_disease in novel_diseases:
            if novel_disease in disease_lower:
                score = max_score
                break

    return score


def update_event_with_score(event: EventCard, config: Optional[AppConfig] = None) -> EventCard:
    """
    Update an event with its calculated score and priority band.

    Args:
        event: The EventCard to update
        config: Optional configuration

    Returns:
        Updated EventCard with score and priority band
    """
    scoring_result = score_event(event, config)

    # Create a new event with updated score and band
    return EventCard(
        event_id=event.event_id,
        source_id=event.source_id,
        source_name=event.source_name,
        source_url=event.source_url,
        source_published_at=event.source_published_at,
        retrieved_at=event.retrieved_at,
        title=event.title,
        disease_or_hazard=event.disease_or_hazard,
        event_type=event.event_type,
        geographies=event.geographies,
        case_count=event.case_count,
        death_count=event.death_count,
        affected_settings=event.affected_settings,
        official_source=event.official_source,
        explicit_facts=event.explicit_facts,
        unknowns=event.unknowns,
        relevance_reasons=event.relevance_reasons + scoring_result.reasons,
        priority_score=scoring_result.total_score,
        priority_band=scoring_result.priority_band,
        summary=event.summary,
        content_hash=event.content_hash,
        review_status=event.review_status,
        raw_content=event.raw_content,
        metadata={**event.metadata, "scoring": scoring_result.to_dict()},
    )
