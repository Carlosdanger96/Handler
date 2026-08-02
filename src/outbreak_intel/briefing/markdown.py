"""
Markdown briefing generator for Public Health Outbreak Intelligence.

This module generates formatted Markdown briefings from processed events,
organizing them by priority band and including all required information.
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from ..models import EventCard, PriorityBand
from ..db import Database


@dataclass
class BriefingOptions:
    """Options for briefing generation."""

    min_score: Optional[int] = None
    include_archive: bool = False
    include_source_health: bool = True
    max_events_per_section: int = 50


def generate_briefing(db: Database, date: str, options: Optional[BriefingOptions] = None) -> str:
    """
    Generate a Markdown briefing for the specified date.

    Args:
        db: Database instance
        date: Date string in YYYY-MM-DD format
        options: Optional briefing options

    Returns:
        Markdown-formatted briefing string
    """
    if options is None:
        options = BriefingOptions()

    # Get events for the specified date
    events = db.get_events_by_date(date)

    # Filter by minimum score if specified
    if options.min_score is not None:
        events = [e for e in events if e.priority_score >= options.min_score]

    # Filter out archive if not including
    if not options.include_archive:
        events = [e for e in events if e.priority_band != PriorityBand.ARCHIVE]

    # Organize events by priority band
    urgent_events = [e for e in events if e.priority_band == PriorityBand.URGENT_HUMAN_REVIEW]
    review_events = [e for e in events if e.priority_band == PriorityBand.REVIEW_TODAY]
    monitor_events = [e for e in events if e.priority_band == PriorityBand.MONITOR]
    archive_events = [e for e in events if e.priority_band == PriorityBand.ARCHIVE]

    # Limit events per section
    urgent_events = urgent_events[: options.max_events_per_section]
    review_events = review_events[: options.max_events_per_section]
    monitor_events = monitor_events[: options.max_events_per_section]
    archive_events = archive_events[: options.max_events_per_section]

    # Generate the briefing
    briefing_parts = []

    # Header
    briefing_parts.append(f"# Public Health Outbreak Intelligence Brief — {date}")
    briefing_parts.append("")

    # Disclaimer
    briefing_parts.append("""> **DISCLAIMER**: This report contains public-source information only and is provided for 
> decision-support and research purposes. Every item requires qualified human review. 
> This system does not diagnose, make clinical recommendations, modify policy, or autonomously 
> escalate alerts. No patient data, Epic access, credentials, or automatic notifications are involved.""")
    briefing_parts.append("")

    # Urgent Human Review section
    if urgent_events:
        briefing_parts.append("## 🔴 Urgent Human Review")
        briefing_parts.append("")
        for event in urgent_events:
            briefing_parts.append(_format_event(event))
        briefing_parts.append("")

    # Review Today section
    if review_events:
        briefing_parts.append("## 🟡 Review Today")
        briefing_parts.append("")
        for event in review_events:
            briefing_parts.append(_format_event(event))
        briefing_parts.append("")

    # Monitor section
    if monitor_events:
        briefing_parts.append("## 🟢 Monitor")
        briefing_parts.append("")
        for event in monitor_events:
            briefing_parts.append(_format_event(event))
        briefing_parts.append("")

    # Archive section
    if options.include_archive and archive_events:
        briefing_parts.append("## ⚪ Archive")
        briefing_parts.append("")
        for event in archive_events:
            briefing_parts.append(_format_event(event))
        briefing_parts.append("")

    # Source Health section
    if options.include_source_health:
        briefing_parts.append("## Source Health")
        briefing_parts.append("")

        # Get source statistics
        source_stats = db.get_all_source_stats()
        if source_stats:
            for stat in sorted(source_stats, key=lambda x: x["source_id"]):
                status = "success" if stat["successful_runs"] > 0 else "no data"
                last_run = stat["last_run"] or "never"
                briefing_parts.append(
                    f"- **{stat['source_name']}**: {status}, last retrieved at {last_run}"
                )
        else:
            briefing_parts.append("- No source health data available")
        briefing_parts.append("")

    # Summary statistics
    total_events = len(events)
    briefing_parts.append("## Summary")
    briefing_parts.append("")
    briefing_parts.append(f"- **Total events**: {total_events}")
    briefing_parts.append(f"- **Urgent review**: {len(urgent_events)}")
    briefing_parts.append(f"- **Review today**: {len(review_events)}")
    briefing_parts.append(f"- **Monitor**: {len(monitor_events)}")
    if options.include_archive:
        briefing_parts.append(f"- **Archive**: {len(archive_events)}")
    briefing_parts.append("")

    # Footer
    briefing_parts.append("---")
    briefing_parts.append("")
    briefing_parts.append("""*This briefing was generated automatically from public sources. All information 
requires verification by qualified public health professionals.*
""")

    return "\n".join(briefing_parts)


def _format_event(event: EventCard) -> str:
    """Format a single event for the briefing."""
    lines = []

    # Title with link
    lines.append(f"- [{event.title}]({event.source_url})")

    # Why surfaced
    if event.relevance_reasons:
        reasons = "; ".join(event.relevance_reasons[:3])  # Limit to 3 reasons
        lines.append(f"  - **Why surfaced**: {reasons}")

    # Disease/Hazard
    if event.disease_or_hazard:
        lines.append(f"  - **Disease/Hazard**: {event.disease_or_hazard}")

    # Event type and source
    lines.append(f"  - **Type**: {event.event_type.value} | **Source**: {event.official_source}")

    # Geography
    if event.geographies:
        geo_parts = []
        for geo in event.geographies:
            parts = []
            if geo.country:
                parts.append(geo.country)
            if geo.state:
                parts.append(geo.state)
            if geo.county:
                parts.append(geo.county)
            if geo.city:
                parts.append(geo.city)
            if geo.region:
                parts.append(f"({geo.region})")
            if parts:
                geo_parts.append(", ".join(parts))
        if geo_parts:
            lines.append(f"  - **Geography**: {'; '.join(geo_parts)}")

    # Explicit facts
    if event.explicit_facts:
        facts = [f.fact_text for f in event.explicit_facts[:5]]  # Limit to 5 facts
        lines.append(f"  - **Explicit facts**: {'; '.join(facts)}")

    # Unknowns
    if event.unknowns:
        unknowns = event.unknowns[:3]  # Limit to 3 unknowns
        lines.append(f"  - **Unknowns**: {'; '.join(unknowns)}")

    # Case and death counts
    counts = []
    if event.case_count is not None:
        counts.append(f"{event.case_count} cases")
    if event.death_count is not None:
        counts.append(f"{event.death_count} deaths")
    if counts:
        lines.append(f"  - **Counts**: {', '.join(counts)}")

    # Score
    lines.append(f"  - **Score**: {event.priority_score}/100")

    return "\n".join(lines)


def generate_demo_briefing() -> str:
    """Generate a demo briefing with sample data."""
    briefing_parts = []

    # Header
    briefing_parts.append("# Public Health Outbreak Intelligence Brief — DEMO")
    briefing_parts.append("")

    # Disclaimer
    briefing_parts.append("""> **DISCLAIMER**: This is a demo briefing containing sample data. This report contains 
> public-source information only and is provided for decision-support and research purposes. 
> Every item requires qualified human review. This system does not diagnose, make clinical 
> recommendations, modify policy, or autonomously escalate alerts.""")
    briefing_parts.append("")

    # Sample urgent event
    briefing_parts.append("## 🔴 Urgent Human Review")
    briefing_parts.append("")
    briefing_parts.append("""- [CDC Health Alert: Increased Respiratory Illness Activity](https://emergency.cdc.gov/han/2024/han00512.asp)
  - **Why surfaced**: Idaho relevance; CDC Health Alert; Healthcare relevance
  - **Disease/Hazard**: Respiratory Syncytial Virus (RSV)
  - **Type**: health_alert | **Source**: CDC Health Alert Network
  - **Geography**: United States (Idaho)
  - **Explicit facts**: 15% increase in RSV hospitalizations; Pediatric cases rising; Healthcare capacity concerned
  - **Counts**: 245 cases, 3 deaths
  - **Score**: 82/100""")
    briefing_parts.append("")

    # Sample review today event
    briefing_parts.append("## 🟡 Review Today")
    briefing_parts.append("")
    briefing_parts.append("""- [Idaho DHW: Measles Exposure Advisory](https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases)
  - **Why surfaced**: Idaho relevance; Healthcare relevance
  - **Disease/Hazard**: Measles
  - **Type**: advisory | **Source**: Idaho Department of Health and Welfare
  - **Geography**: United States, Idaho (Ada County)
  - **Explicit facts**: Single confirmed case; Exposure at local hospital; Contact tracing underway
  - **Unknowns**: Source of infection unknown
  - **Counts**: 1 case
  - **Score**: 65/100""")
    briefing_parts.append("")

    # Sample monitor event
    briefing_parts.append("## 🟢 Monitor")
    briefing_parts.append("")
    briefing_parts.append("""- [WHO DON: Avian Influenza in Poultry](https://www.who.int/emergencies/disease-outbreak-news)
  - **Why surfaced**: US travel/importation relevance
  - **Disease/Hazard**: Avian Influenza H5N1
  - **Type**: outbreak | **Source**: World Health Organization
  - **Geography**: Europe (France, Germany)
  - **Explicit facts**: Poultry outbreaks reported; No human cases confirmed
  - **Score**: 35/100""")
    briefing_parts.append("")

    # Source Health
    briefing_parts.append("## Source Health")
    briefing_parts.append("")
    briefing_parts.append(
        "- **CDC Health Alert Network**: success, last retrieved at 2024-01-15T10:30:00"
    )
    briefing_parts.append(
        "- **Idaho Department of Health and Welfare**: success, last retrieved at 2024-01-15T10:35:00"
    )
    briefing_parts.append(
        "- **WHO Disease Outbreak News**: success, last retrieved at 2024-01-15T10:40:00"
    )
    briefing_parts.append("")

    # Summary
    briefing_parts.append("## Summary")
    briefing_parts.append("")
    briefing_parts.append("- **Total events**: 3")
    briefing_parts.append("- **Urgent review**: 1")
    briefing_parts.append("- **Review today**: 1")
    briefing_parts.append("- **Monitor**: 1")
    briefing_parts.append("")

    # Footer
    briefing_parts.append("---")
    briefing_parts.append("")
    briefing_parts.append("""*This demo briefing was generated from sample data. All information requires verification 
by qualified public health professionals.*
""")

    return "\n".join(briefing_parts)
