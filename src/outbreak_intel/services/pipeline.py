"""
Pipeline service for Public Health Outbreak Intelligence.

This module implements the main data processing pipeline that orchestrates
collection, extraction, scoring, deduplication, and storage of public health events.
"""

from datetime import datetime
from typing import Optional
import logging

from ..config import AppConfig, load_config, get_source_config
from ..db import Database, get_database, init_database
from ..models import EventCard, EventType, CollectionResult, PipelineResult
from ..collectors import get_collector
from ..extraction import get_extractor
from ..triage.scoring import score_event, update_event_with_score
from ..triage.dedup import is_duplicate, deduplicate_events_in_memory


# Set up logging
logger = logging.getLogger(__name__)


def process_event(event: EventCard, config: AppConfig) -> EventCard:
    """
    Process a single event through extraction and scoring.

    Args:
        event: The EventCard to process
        config: Application configuration

    Returns:
        Processed EventCard with extraction and scoring applied
    """
    try:
        # Apply extraction if we have raw content
        if event.raw_content:
            extractor = get_extractor("heuristic")
            extraction_result = extractor.extract(
                event.raw_content, event.source_url, event.source_id
            )

            if extraction_result.success and extraction_result.event:
                # Merge extracted data with existing event
                extracted_event = extraction_result.event

                # Update event with extracted data
                event = EventCard(
                    event_id=event.event_id,
                    source_id=event.source_id,
                    source_name=event.source_name,
                    source_url=event.source_url,
                    source_published_at=event.source_published_at
                    or extracted_event.source_published_at,
                    retrieved_at=event.retrieved_at,
                    title=event.title or extracted_event.title,
                    disease_or_hazard=extracted_event.disease_or_hazard or event.disease_or_hazard,
                    event_type=extracted_event.event_type or event.event_type,
                    geographies=extracted_event.geographies or event.geographies,
                    case_count=extracted_event.case_count or event.case_count,
                    death_count=extracted_event.death_count or event.death_count,
                    affected_settings=extracted_event.affected_settings or event.affected_settings,
                    official_source=event.official_source,
                    explicit_facts=extracted_event.explicit_facts or event.explicit_facts,
                    unknowns=extracted_event.unknowns or event.unknowns,
                    relevance_reasons=event.relevance_reasons,
                    priority_score=event.priority_score,
                    priority_band=event.priority_band,
                    summary=event.summary or extracted_event.summary,
                    content_hash=event.content_hash,
                    review_status=event.review_status,
                    raw_content=event.raw_content,
                    metadata={**event.metadata, "extraction": extraction_result.to_dict()},
                )

        # Apply scoring
        scored_event = update_event_with_score(event, config)
        return scored_event

    except Exception as e:
        logger.error(f"Error processing event {event.event_id}: {e}")
        return event


def run_demo_pipeline(config: AppConfig, verbose: bool = False) -> PipelineResult:
    """
    Run the pipeline in demo mode using fixture data.

    Args:
        config: Application configuration
        verbose: Whether to show verbose output

    Returns:
        PipelineResult with the results of the demo run
    """
    started_at = datetime.utcnow()
    errors = []
    collection_results = []
    total_new_events = 0
    total_duplicate_events = 0

    try:
        # Initialize database
        db = init_database(config.database.path)

        # Create demo events from fixtures
        demo_events = _create_demo_events()

        if verbose:
            print(f"Created {len(demo_events)} demo events")

        # Process each demo event
        for demo_event in demo_events:
            try:
                # Process the event
                processed_event = process_event(demo_event, config)

                # Check for duplicates
                if is_duplicate(processed_event, db):
                    total_duplicate_events += 1
                    if verbose:
                        print(f"Duplicate event: {processed_event.title}")
                else:
                    # Save to database
                    success = db.save_event(processed_event)
                    if success:
                        total_new_events += 1
                        if verbose:
                            print(
                                f"Saved event: {processed_event.title} (score: {processed_event.priority_score})"
                            )
                    else:
                        errors.append(f"Failed to save event: {processed_event.title}")

            except Exception as e:
                errors.append(f"Error processing demo event: {str(e)}")
                if verbose:
                    print(f"Error processing demo event: {e}")

        # Create collection results for demo sources
        for source_id in ["cdc_han", "cdc_outbreaks", "idaho_dhw", "who_don"]:
            source_config = get_source_config(source_id, config)
            if source_config:
                collection_results.append(
                    CollectionResult(
                        source_id=source_id,
                        source_name=source_config.source_name,
                        success=True,
                        retrieved_at=started_at,
                        item_count=2,  # 2 items per source in demo
                        new_events=1,
                        duplicate_events=1,
                    )
                )

    except Exception as e:
        errors.append(f"Demo pipeline error: {str(e)}")
        if verbose:
            print(f"Demo pipeline error: {e}")

    completed_at = datetime.utcnow()

    return PipelineResult(
        started_at=started_at,
        completed_at=completed_at,
        collection_results=collection_results,
        total_new_events=total_new_events,
        total_duplicate_events=total_duplicate_events,
        errors=errors,
    )


def run_pipeline(
    config: AppConfig, source_id: Optional[str] = None, verbose: bool = False
) -> PipelineResult:
    """
    Run the complete pipeline for live data collection.

    Args:
        config: Application configuration
        source_id: Optional specific source to run (None for all sources)
        verbose: Whether to show verbose output

    Returns:
        PipelineResult with the results of the pipeline run
    """
    started_at = datetime.utcnow()
    errors = []
    collection_results = []
    total_new_events = 0
    total_duplicate_events = 0

    try:
        # Initialize database
        db = init_database(config.database.path)

        # Determine which sources to run
        sources = config.sources
        if source_id:
            sources = [s for s in sources if s.source_id == source_id]

        # Filter to enabled sources
        sources = [s for s in sources if s.enabled]

        if verbose:
            print(f"Running pipeline for {len(sources)} sources")

        # Process each source
        for source_config in sources:
            try:
                if verbose:
                    print(f"Processing source: {source_config.source_name}")

                # Get collector for this source
                collector = get_collector(source_config.source_id, config)

                # Collect data
                collector_result = collector.collect()

                if collector_result.success:
                    if verbose:
                        print(
                            f"  Collected {collector_result.item_count} items from {source_config.source_name}"
                        )

                    # Process each collected item
                    new_events = 0
                    duplicate_events = 0

                    for item_data in collector_result.items:
                        try:
                            # Parse item into event
                            event = collector.parse_item(item_data)

                            if event:
                                # Process the event (extraction, scoring)
                                processed_event = process_event(event, config)

                                # Check for duplicates
                                if is_duplicate(processed_event, db):
                                    duplicate_events += 1
                                    if verbose:
                                        print(f"  Duplicate: {processed_event.title}")
                                else:
                                    # Save to database
                                    success = db.save_event(processed_event)
                                    if success:
                                        new_events += 1
                                        if verbose:
                                            print(
                                                f"  Saved: {processed_event.title} (score: {processed_event.priority_score})"
                                            )
                                    else:
                                        errors.append(
                                            f"Failed to save event from {source_config.source_name}: {processed_event.title}"
                                        )

                        except Exception as e:
                            errors.append(
                                f"Error processing item from {source_config.source_name}: {str(e)}"
                            )
                            if verbose:
                                print(f"  Error processing item: {e}")

                    # Save collection result
                    collection_result = CollectionResult(
                        source_id=source_config.source_id,
                        source_name=source_config.source_name,
                        success=True,
                        retrieved_at=collector_result.retrieved_at,
                        item_count=collector_result.item_count,
                        new_events=new_events,
                        duplicate_events=duplicate_events,
                    )

                    total_new_events += new_events
                    total_duplicate_events += duplicate_events

                else:
                    # Collection failed
                    errors.append(
                        f"Collection failed for {source_config.source_name}: {collector_result.error_message}"
                    )
                    collection_result = CollectionResult(
                        source_id=source_config.source_id,
                        source_name=source_config.source_name,
                        success=False,
                        retrieved_at=collector_result.retrieved_at,
                        error_message=collector_result.error_message,
                    )

                collection_results.append(collection_result)

                # Clean up collector
                collector.close()

            except Exception as e:
                errors.append(f"Error processing source {source_config.source_name}: {str(e)}")
                collection_results.append(
                    CollectionResult(
                        source_id=source_config.source_id,
                        source_name=source_config.source_name,
                        success=False,
                        retrieved_at=datetime.utcnow(),
                        error_message=str(e),
                    )
                )
                if verbose:
                    print(f"Error processing source {source_config.source_name}: {e}")

    except Exception as e:
        errors.append(f"Pipeline error: {str(e)}")
        if verbose:
            print(f"Pipeline error: {e}")

    completed_at = datetime.utcnow()

    return PipelineResult(
        started_at=started_at,
        completed_at=completed_at,
        collection_results=collection_results,
        total_new_events=total_new_events,
        total_duplicate_events=total_duplicate_events,
        errors=errors,
    )


def _create_demo_events() -> list[EventCard]:
    """Create demo events for testing and demonstration."""
    from ..models import EventCard, EventType, PriorityBand, ReviewStatus, Geography, ExplicitFact
    from datetime import datetime, timedelta

    demo_events = []

    # Demo event 1: CDC HAN - High priority
    demo_events.append(
        EventCard(
            event_id="demo_cdc_han_001",
            source_id="cdc_han",
            source_name="CDC Health Alert Network",
            source_url="https://emergency.cdc.gov/han/2024/han00512.asp",
            source_published_at=datetime.utcnow() - timedelta(days=1),
            retrieved_at=datetime.utcnow(),
            title="CDC Health Alert: Increased Respiratory Illness Activity in Idaho",
            disease_or_hazard="Respiratory Syncytial Virus (RSV)",
            event_type=EventType.HEALTH_ALERT,
            geographies=[
                Geography(country="United States", state="Idaho"),
                Geography(region="Pacific Northwest"),
            ],
            case_count=245,
            death_count=3,
            affected_settings=["healthcare", "public_health", "pediatric"],
            official_source="CDC Health Alert Network",
            explicit_facts=[
                ExplicitFact(
                    fact_text="15% increase in RSV hospitalizations",
                    fact_type="trend",
                    source_attribution="CDC HAN",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Pediatric cases rising significantly",
                    fact_type="demographic",
                    source_attribution="CDC HAN",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Healthcare capacity concerned",
                    fact_type="impact",
                    source_attribution="CDC HAN",
                    confidence="medium",
                ),
            ],
            unknowns=["Source of increased transmission unknown"],
            relevance_reasons=[
                "CDC Health Alert Network",
                "Idaho relevance",
                "Healthcare relevance",
            ],
            priority_score=0,  # Will be calculated
            priority_band=PriorityBand.ARCHIVE,  # Will be calculated
            summary="CDC Health Alert regarding increased RSV activity in Idaho with healthcare impact concerns",
            content_hash=EventCard.generate_content_hash(
                "CDC Health Alert: Increased Respiratory Illness Activity in Idaho - RSV cases rising",
                "https://emergency.cdc.gov/han/2024/han00512.asp",
            ),
            review_status=ReviewStatus.PENDING,
            raw_content="CDC Health Alert Network notification about increased RSV activity...",
            metadata={"demo": True, "source_type": "han"},
        )
    )

    # Demo event 2: Idaho DHW - Medium priority
    demo_events.append(
        EventCard(
            event_id="demo_idaho_dhw_001",
            source_id="idaho_dhw",
            source_name="Idaho Department of Health and Welfare",
            source_url="https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases",
            source_published_at=datetime.utcnow() - timedelta(days=2),
            retrieved_at=datetime.utcnow(),
            title="Measles Exposure Advisory - Ada County",
            disease_or_hazard="Measles",
            event_type=EventType.ADVISORY,
            geographies=[
                Geography(country="United States", state="Idaho", county="Ada County"),
                Geography(region="Pacific Northwest"),
            ],
            case_count=1,
            death_count=None,
            affected_settings=["healthcare", "public_health", "community"],
            official_source="Idaho Department of Health and Welfare",
            explicit_facts=[
                ExplicitFact(
                    fact_text="Single confirmed case of measles",
                    fact_type="case_count",
                    source_attribution="Idaho DHW",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Exposure at local hospital emergency department",
                    fact_type="exposure_location",
                    source_attribution="Idaho DHW",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Contact tracing underway",
                    fact_type="response_action",
                    source_attribution="Idaho DHW",
                    confidence="high",
                ),
            ],
            unknowns=[
                "Source of infection unknown",
                "Potential additional exposures not identified",
            ],
            relevance_reasons=[
                "Idaho Department of Health and Welfare",
                "Idaho relevance",
                "Healthcare relevance",
            ],
            priority_score=0,
            priority_band=PriorityBand.ARCHIVE,
            summary="Idaho DHW advisory regarding measles exposure in Ada County with contact tracing in progress",
            content_hash=EventCard.generate_content_hash(
                "Measles Exposure Advisory - Ada County - Single confirmed case",
                "https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases",
            ),
            review_status=ReviewStatus.PENDING,
            raw_content="Idaho Department of Health and Welfare measles exposure advisory...",
            metadata={"demo": True, "source_type": "state_health"},
        )
    )

    # Demo event 3: CDC Outbreaks - Medium priority
    demo_events.append(
        EventCard(
            event_id="demo_cdc_outbreaks_001",
            source_id="cdc_outbreaks",
            source_name="CDC Outbreak Investigations",
            source_url="https://www.cdc.gov/outbreaks/salmonella-2024.html",
            source_published_at=datetime.utcnow() - timedelta(days=3),
            retrieved_at=datetime.utcnow(),
            title="Multistate Salmonella Outbreak Linked to Contaminated Produce",
            disease_or_hazard="Salmonella",
            event_type=EventType.OUTBREAK,
            geographies=[
                Geography(country="United States"),
                Geography(state="California"),
                Geography(state="Oregon"),
            ],
            case_count=127,
            death_count=None,
            affected_settings=["public_health", "food_safety", "retail"],
            official_source="CDC Outbreak Investigations",
            explicit_facts=[
                ExplicitFact(
                    fact_text="127 cases reported across 15 states",
                    fact_type="case_count",
                    source_attribution="CDC Outbreaks",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Linked to contaminated leafy greens",
                    fact_type="source",
                    source_attribution="CDC Outbreaks",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Investigation ongoing",
                    fact_type="status",
                    source_attribution="CDC Outbreaks",
                    confidence="medium",
                ),
            ],
            unknowns=[
                "Specific product source not yet identified",
                "Distribution chain under investigation",
            ],
            relevance_reasons=["CDC Outbreak Investigation", "Multistate impact"],
            priority_score=0,
            priority_band=PriorityBand.ARCHIVE,
            summary="CDC investigation of multistate Salmonella outbreak linked to contaminated produce",
            content_hash=EventCard.generate_content_hash(
                "Multistate Salmonella Outbreak Linked to Contaminated Produce - 127 cases",
                "https://www.cdc.gov/outbreaks/salmonella-2024.html",
            ),
            review_status=ReviewStatus.PENDING,
            raw_content="CDC outbreak investigation report on Salmonella cases...",
            metadata={"demo": True, "source_type": "outbreak_investigation"},
        )
    )

    # Demo event 4: WHO DON - Lower priority
    demo_events.append(
        EventCard(
            event_id="demo_who_don_001",
            source_id="who_don",
            source_name="WHO Disease Outbreak News",
            source_url="https://www.who.int/emergencies/disease-outbreak-news/item/2024-DON567",
            source_published_at=datetime.utcnow() - timedelta(days=4),
            retrieved_at=datetime.utcnow(),
            title="Avian Influenza A(H5N1) in Poultry - Europe",
            disease_or_hazard="Avian Influenza H5N1",
            event_type=EventType.OUTBREAK,
            geographies=[
                Geography(country="France"),
                Geography(country="Germany"),
                Geography(region="Europe"),
            ],
            case_count=None,
            death_count=None,
            affected_settings=["agriculture", "public_health", "wildlife"],
            official_source="World Health Organization",
            explicit_facts=[
                ExplicitFact(
                    fact_text="Multiple poultry outbreaks reported",
                    fact_type="outbreak",
                    source_attribution="WHO DON",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="No human cases confirmed",
                    fact_type="human_impact",
                    source_attribution="WHO DON",
                    confidence="high",
                ),
                ExplicitFact(
                    fact_text="Wild bird migration suspected",
                    fact_type="transmission",
                    source_attribution="WHO DON",
                    confidence="medium",
                ),
            ],
            unknowns=[
                "Risk to humans being assessed",
                "Potential for zoonotic transmission under review",
            ],
            relevance_reasons=["WHO Disease Outbreak News", "US travel/importation relevance"],
            priority_score=0,
            priority_band=PriorityBand.ARCHIVE,
            summary="WHO report on avian influenza outbreaks in European poultry with no confirmed human cases",
            content_hash=EventCard.generate_content_hash(
                "Avian Influenza A(H5N1) in Poultry - Europe - No human cases",
                "https://www.who.int/emergencies/disease-outbreak-news/item/2024-DON567",
            ),
            review_status=ReviewStatus.PENDING,
            raw_content="WHO Disease Outbreak News report on avian influenza in Europe...",
            metadata={"demo": True, "source_type": "international_outbreak"},
        )
    )

    return demo_events
