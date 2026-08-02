"""
Command-line interface for Public Health Outbreak Intelligence.

This module provides the main CLI entry point using Typer, with commands
for database initialization, data collection, briefing generation, and
event management.
"""

import sys
from datetime import datetime
from typing import Optional
import typer

from .config import load_config
from .db import init_database, get_database
from .services.pipeline import run_pipeline, run_demo_pipeline
from .briefing.markdown import generate_briefing, BriefingOptions

app = typer.Typer(
    name="outbreak-intel",
    help="Public Health Outbreak Intelligence - Local outbreak monitoring and briefing generation",
    add_completion=False,
)


def get_config():
    """Get the application configuration."""
    return load_config()


@app.command()
def init_db(
    db_path: Optional[str] = typer.Option(
        None, "--db-path", help="Path to the SQLite database file"
    ),
):
    """Initialize the outbreak intelligence database."""
    try:
        config = get_config()
        if db_path:
            config.database.path = db_path

        db = init_database(config.database.path)
        typer.echo(f"Database initialized at: {db.db_path}")
        typer.echo("Database schema created successfully.")
    except Exception as e:
        typer.echo(f"Error initializing database: {e}", err=True)
        sys.exit(1)


@app.command()
def run(
    demo: bool = typer.Option(False, "--demo", help="Run in demo mode using fixture data"),
    live: bool = typer.Option(False, "--live", help="Run live collection from approved sources"),
    source: Optional[str] = typer.Option(
        None, "--source", help="Run collection for a specific source only"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output"),
):
    """Run the outbreak intelligence pipeline."""
    if not demo and not live:
        typer.echo("Please specify either --demo or --live mode")
        sys.exit(1)

    if demo and live:
        typer.echo("Please specify only one of --demo or --live mode")
        sys.exit(1)

    try:
        config = get_config()

        if demo:
            typer.echo("Running in DEMO mode with fixture data...")
            result = run_demo_pipeline(config, verbose=verbose)
        else:
            typer.echo("Running LIVE collection from approved sources...")
            result = run_pipeline(config, source_id=source, verbose=verbose)

        typer.echo(f"Pipeline completed at: {result.completed_at}")
        typer.echo(f"New events: {result.total_new_events}")
        typer.echo(f"Duplicate events: {result.total_duplicate_events}")

        if result.errors:
            typer.echo("Errors encountered:")
            for error in result.errors:
                typer.echo(f"  - {error}", err=True)

        if not demo:
            typer.echo("\nSource Health:")
            for cr in result.collection_results:
                status = "success" if cr.success else "failed"
                typer.echo(f"  - {cr.source_name}: {status}, retrieved at {cr.retrieved_at}")
                if cr.error_message:
                    typer.echo(f"    Error: {cr.error_message}")

    except Exception as e:
        typer.echo(f"Error running pipeline: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@app.command()
def brief(
    date: Optional[str] = typer.Option(
        None, "--date", help="Date for the briefing (YYYY-MM-DD). Defaults to today."
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path. Defaults to stdout."
    ),
    min_score: Optional[int] = typer.Option(
        None, "--min-score", help="Minimum priority score to include in briefing"
    ),
    include_archive: bool = typer.Option(
        False, "--include-archive", help="Include archived items in the briefing"
    ),
):
    """Generate a Markdown briefing for the specified date."""
    try:
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        config = get_config()
        db = get_database()

        options = BriefingOptions(min_score=min_score, include_archive=include_archive)

        briefing = generate_briefing(db, date, options)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(briefing)
            typer.echo(f"Briefing saved to: {output}")
        else:
            typer.echo(briefing)

    except Exception as e:
        typer.echo(f"Error generating briefing: {e}", err=True)
        sys.exit(1)


@app.command()
def events(
    list_all: bool = typer.Option(False, "--list", help="List all events"),
    show_id: Optional[str] = typer.Option(
        None, "--show", help="Show details for a specific event ID"
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum number of events to list"),
    priority: Optional[str] = typer.Option(
        None,
        "--priority",
        "-p",
        help="Filter by priority band (urgent_human_review, review_today, monitor, archive)",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by review status (pending, reviewed, dismissed, archived)",
    ),
    source: Optional[str] = typer.Option(None, "--source", help="Filter by source ID"),
):
    """Manage and view events."""
    if not list_all and not show_id:
        typer.echo("Please specify either --list or --show EVENT_ID")
        sys.exit(1)

    try:
        db = get_database()

        if show_id:
            event = db.get_event(show_id)
            if event:
                typer.echo(f"Event ID: {event.event_id}")
                typer.echo(f"Source: {event.source_name} ({event.source_url})")
                typer.echo(f"Published: {event.source_published_at}")
                typer.echo(f"Retrieved: {event.retrieved_at}")
                typer.echo(f"Title: {event.title}")
                typer.echo(f"Disease/Hazard: {event.disease_or_hazard or 'N/A'}")
                typer.echo(f"Event Type: {event.event_type.value}")
                typer.echo(f"Priority Score: {event.priority_score}")
                typer.echo(f"Priority Band: {event.priority_band.value}")
                typer.echo(f"Review Status: {event.review_status.value}")
                typer.echo(f"\nSummary: {event.summary}")

                if event.geographies:
                    typer.echo(f"\nGeographies:")
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
                        typer.echo(f"  - {', '.join(parts)}")

                if event.explicit_facts:
                    typer.echo(f"\nExplicit Facts:")
                    for fact in event.explicit_facts:
                        typer.echo(f"  - {fact.fact_text} ({fact.fact_type}, {fact.confidence})")

                if event.unknowns:
                    typer.echo(f"\nUnknowns:")
                    for unknown in event.unknowns:
                        typer.echo(f"  - {unknown}")

                if event.relevance_reasons:
                    typer.echo(f"\nRelevance Reasons:")
                    for reason in event.relevance_reasons:
                        typer.echo(f"  - {reason}")
            else:
                typer.echo(f"Event not found: {show_id}", err=True)
                sys.exit(1)

        elif list_all:
            events = db.list_events(
                limit=limit, priority_band=priority, review_status=status, source_id=source
            )

            if not events:
                typer.echo("No events found.")
                return

            typer.echo(f"Found {len(events)} events:\n")

            for event in events:
                status_emoji = {
                    "urgent_human_review": "🔴",
                    "review_today": "🟡",
                    "monitor": "🟢",
                    "archive": "⚪",
                }.get(event.priority_band.value, "⚪")

                typer.echo(
                    f"{status_emoji} {event.event_id[:8]} | {event.priority_score:3d} | {event.priority_band.value:20s} | {event.source_id:15s} | {event.title[:60]}"
                )

            typer.echo(f"\nTotal: {len(events)} events")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
def sources(
    list_all: bool = typer.Option(False, "--list", help="List all configured sources"),
    stats: bool = typer.Option(False, "--stats", help="Show collection statistics for sources"),
):
    """Manage and view sources."""
    if not list_all and not stats:
        typer.echo("Please specify either --list or --stats")
        sys.exit(1)

    try:
        config = get_config()
        db = get_database()

        if list_all:
            typer.echo("Configured Sources:\n")
            for source in config.sources:
                enabled = "✅" if source.enabled else "❌"
                typer.echo(
                    f"{enabled} {source.source_id:15s} | {source.source_name:30s} | {source.source_url}"
                )

            typer.echo(f"\nTotal: {len(config.sources)} sources")

        if stats:
            source_stats = db.get_all_source_stats()
            typer.echo("Source Collection Statistics:\n")
            for stat in source_stats:
                success_rate = (
                    (stat["successful_runs"] / stat["total_runs"] * 100)
                    if stat["total_runs"] > 0
                    else 0
                )
                typer.echo(
                    f"{stat['source_id']:15s} | Runs: {stat['total_runs']:3d} | Success: {success_rate:5.1f}% | Events: {stat['total_events']:4d} | Unique: {stat['unique_events']:4d}"
                )

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
def health():
    """Check the health and status of the system."""
    try:
        config = get_config()
        db = get_database()

        typer.echo("Public Health Outbreak Intelligence - System Health\n")
        typer.echo("=" * 50)

        # Database status
        typer.echo("\n🗃️  Database:")
        typer.echo(f"   Path: {db.db_path}")
        typer.echo(f"   Exists: {'✅' if os.path.exists(db.db_path) else '❌'}")

        # Event counts
        total_events = db.count_events()
        urgent_events = db.count_events(priority_band="urgent_human_review")
        review_events = db.count_events(priority_band="review_today")
        monitor_events = db.count_events(priority_band="monitor")
        archive_events = db.count_events(priority_band="archive")

        typer.echo(f"   Total Events: {total_events}")
        typer.echo(f"   - Urgent Review: {urgent_events}")
        typer.echo(f"   - Review Today: {review_events}")
        typer.echo(f"   - Monitor: {monitor_events}")
        typer.echo(f"   - Archive: {archive_events}")

        # Source status
        typer.echo(f"\n📡 Sources:")
        typer.echo(f"   Configured: {len(config.sources)}")
        enabled_sources = sum(1 for s in config.sources if s.enabled)
        typer.echo(f"   Enabled: {enabled_sources}")

        # Configuration
        typer.echo(f"\n⚙️  Configuration:")
        typer.echo(f"   Demo Mode: {'✅' if config.demo_mode else '❌'}")
        typer.echo(f"   Log Level: {config.log_level}")
        typer.echo(f"   HTTP Timeout: {config.http.timeout}s")
        typer.echo(f"   Max Retries: {config.http.max_retries}")

        typer.echo("\n✅ System is healthy and ready.")

    except Exception as e:
        typer.echo(f"❌ Health check failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
