"""
Database management for Public Health Outbreak Intelligence.

This module provides SQLite database operations for storing and retrieving
event cards, source metadata, and pipeline state.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

from .models import EventCard, CollectionResult, PipelineResult
from .config import load_config


# SQL schema for the database
SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_published_at TEXT,
    retrieved_at TEXT NOT NULL,
    title TEXT NOT NULL,
    disease_or_hazard TEXT,
    event_type TEXT NOT NULL,
    geographies_json TEXT NOT NULL DEFAULT '[]',
    case_count INTEGER,
    death_count INTEGER,
    affected_settings_json TEXT NOT NULL DEFAULT '[]',
    official_source TEXT NOT NULL,
    explicit_facts_json TEXT NOT NULL DEFAULT '[]',
    unknowns_json TEXT NOT NULL DEFAULT '[]',
    relevance_reasons_json TEXT NOT NULL DEFAULT '[]',
    priority_score INTEGER NOT NULL DEFAULT 0,
    priority_band TEXT NOT NULL DEFAULT 'archive',
    summary TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending',
    raw_content TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    feed_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    last_retrieved_at TEXT,
    last_success INTEGER NOT NULL DEFAULT 1,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    source_id TEXT NOT NULL,
    success INTEGER NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    new_events INTEGER NOT NULL DEFAULT 0,
    duplicate_events INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    total_new_events INTEGER NOT NULL DEFAULT 0,
    total_duplicate_events INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_events_source_id ON events(source_id);
CREATE INDEX IF NOT EXISTS idx_events_priority_score ON events(priority_score);
CREATE INDEX IF NOT EXISTS idx_events_priority_band ON events(priority_band);
CREATE INDEX IF NOT EXISTS idx_events_review_status ON events(review_status);
CREATE INDEX IF NOT EXISTS idx_events_content_hash ON events(content_hash);
CREATE INDEX IF NOT EXISTS idx_events_retrieved_at ON events(retrieved_at);
CREATE INDEX IF NOT EXISTS idx_events_source_published_at ON events(source_published_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_content_hash_unique ON events(content_hash);
"""


class Database:
    """SQLite database manager for outbreak intelligence data."""

    def __init__(self, db_path: str):
        """Initialize the database connection."""
        self.db_path = db_path
        self._ensure_directory()
        self._initialize()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _initialize(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    @contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        """Close the database connection (no-op for SQLite, but provided for interface consistency)."""
        pass

    def init_database(self) -> bool:
        """Initialize or reinitialize the database schema."""
        try:
            self._initialize()
            return True
        except Exception as e:
            print(f"Error initializing database: {e}")
            return False

    def save_event(self, event: EventCard) -> bool:
        """Save an event to the database."""
        import json

        try:
            with self._get_connection() as conn:
                # Check for duplicate content hash
                existing = conn.execute(
                    "SELECT event_id FROM events WHERE content_hash = ?", (event.content_hash,)
                ).fetchone()

                if existing:
                    return False  # Duplicate event

                # Convert complex types to JSON
                geographies_json = json.dumps([g.model_dump() for g in event.geographies])
                affected_settings_json = json.dumps(event.affected_settings)
                explicit_facts_json = json.dumps([f.model_dump() for f in event.explicit_facts])
                unknowns_json = json.dumps(event.unknowns)
                relevance_reasons_json = json.dumps(event.relevance_reasons)
                metadata_json = json.dumps(event.metadata)

                conn.execute(
                    """
                    INSERT INTO events (
                        event_id, source_id, source_name, source_url, 
                        source_published_at, retrieved_at, title, disease_or_hazard, 
                        event_type, geographies_json, case_count, death_count, 
                        affected_settings_json, official_source, explicit_facts_json, 
                        unknowns_json, relevance_reasons_json, priority_score, 
                        priority_band, summary, content_hash, review_status, 
                        raw_content, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                    (
                        event.event_id,
                        event.source_id,
                        event.source_name,
                        event.source_url,
                        event.source_published_at.isoformat()
                        if event.source_published_at
                        else None,
                        event.retrieved_at.isoformat(),
                        event.title,
                        event.disease_or_hazard,
                        event.event_type.value,
                        geographies_json,
                        event.case_count,
                        event.death_count,
                        affected_settings_json,
                        event.official_source,
                        explicit_facts_json,
                        unknowns_json,
                        relevance_reasons_json,
                        event.priority_score,
                        event.priority_band.value,
                        event.summary,
                        event.content_hash,
                        event.review_status.value,
                        event.raw_content,
                        metadata_json,
                    ),
                )

                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving event: {e}")
            return False

    def get_event(self, event_id: str) -> Optional[EventCard]:
        """Get a single event by ID."""
        import json

        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()

            if not row:
                return None

            return self._row_to_event(row)

    def _row_to_event(self, row: sqlite3.Row) -> EventCard:
        """Convert a database row to an EventCard."""
        import json
        from .models import Geography, ExplicitFact, PriorityBand, ReviewStatus, EventType

        geographies = [Geography(**g) for g in json.loads(row["geographies_json"] or "[]")]
        affected_settings = json.loads(row["affected_settings_json"] or "[]")
        explicit_facts = [ExplicitFact(**f) for f in json.loads(row["explicit_facts_json"] or "[]")]
        unknowns = json.loads(row["unknowns_json"] or "[]")
        relevance_reasons = json.loads(row["relevance_reasons_json"] or "[]")
        metadata = json.loads(row["metadata_json"] or "{}")

        return EventCard(
            event_id=row["event_id"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            source_url=row["source_url"],
            source_published_at=datetime.fromisoformat(row["source_published_at"])
            if row["source_published_at"]
            else None,
            retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
            title=row["title"],
            disease_or_hazard=row["disease_or_hazard"],
            event_type=EventType(row["event_type"]),
            geographies=geographies,
            case_count=row["case_count"],
            death_count=row["death_count"],
            affected_settings=affected_settings,
            official_source=row["official_source"],
            explicit_facts=explicit_facts,
            unknowns=unknowns,
            relevance_reasons=relevance_reasons,
            priority_score=row["priority_score"],
            priority_band=PriorityBand(row["priority_band"]),
            summary=row["summary"],
            content_hash=row["content_hash"],
            review_status=ReviewStatus(row["review_status"]),
            raw_content=row["raw_content"],
            metadata=metadata,
        )

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        priority_band: Optional[str] = None,
        review_status: Optional[str] = None,
        source_id: Optional[str] = None,
        min_score: Optional[int] = None,
    ) -> list[EventCard]:
        """List events with optional filtering."""
        query = "SELECT * FROM events"
        params: list[Any] = []
        conditions = []

        if priority_band:
            conditions.append("priority_band = ?")
            params.append(priority_band)

        if review_status:
            conditions.append("review_status = ?")
            params.append(review_status)

        if source_id:
            conditions.append("source_id = ?")
            params.append(source_id)

        if min_score is not None:
            conditions.append("priority_score >= ?")
            params.append(min_score)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY priority_score DESC, retrieved_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_event(row) for row in rows]

    def count_events(
        self, priority_band: Optional[str] = None, review_status: Optional[str] = None
    ) -> int:
        """Count events with optional filtering."""
        query = "SELECT COUNT(*) FROM events"
        params: list[Any] = []
        conditions = []

        if priority_band:
            conditions.append("priority_band = ?")
            params.append(priority_band)

        if review_status:
            conditions.append("review_status = ?")
            params.append(review_status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self._get_connection() as conn:
            result = conn.execute(query, params).fetchone()
            return result[0] if result else 0

    def get_events_by_date(self, date: str) -> list[EventCard]:
        """Get events retrieved on a specific date."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE DATE(retrieved_at) = ? ORDER BY priority_score DESC",
                (date,),
            ).fetchall()
            return [self._row_to_event(row) for row in rows]

    def get_events_by_content_hash(self, content_hash: str) -> list[EventCard]:
        """Get events by content hash (for deduplication)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE content_hash = ?", (content_hash,)
            ).fetchall()
            return [self._row_to_event(row) for row in rows]

    def update_event_review_status(self, event_id: str, status: str) -> bool:
        """Update the review status of an event."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE events SET review_status = ?, updated_at = CURRENT_TIMESTAMP WHERE event_id = ?",
                    (status, event_id),
                )
                conn.commit()
                return conn.total_changes > 0
        except Exception as e:
            print(f"Error updating event review status: {e}")
            return False

    def save_collection_result(self, result: CollectionResult) -> bool:
        """Save a collection result."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO collection_runs (
                        run_id, started_at, completed_at, source_id, 
                        success, item_count, new_events, duplicate_events, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.run_id
                        if hasattr(result, "run_id")
                        else f"{result.source_id}_{result.retrieved_at.isoformat()}",
                        result.retrieved_at.isoformat(),
                        result.retrieved_at.isoformat(),  # completed_at same as retrieved_at for now
                        result.source_id,
                        1 if result.success else 0,
                        result.item_count,
                        result.new_events,
                        result.duplicate_events,
                        result.error_message,
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving collection result: {e}")
            return False

    def save_pipeline_result(self, result: PipelineResult) -> bool:
        """Save a pipeline result."""
        import json

        try:
            with self._get_connection() as conn:
                errors_json = json.dumps(result.errors)

                conn.execute(
                    """
                    INSERT INTO pipeline_runs (
                        run_id, started_at, completed_at, 
                        total_new_events, total_duplicate_events, errors_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.run_id
                        if hasattr(result, "run_id")
                        else f"pipeline_{result.started_at.isoformat()}",
                        result.started_at.isoformat(),
                        result.completed_at.isoformat(),
                        result.total_new_events,
                        result.total_duplicate_events,
                        errors_json,
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving pipeline result: {e}")
            return False

    def get_source_stats(self, source_id: str) -> dict[str, Any]:
        """Get statistics for a specific source."""
        with self._get_connection() as conn:
            # Get source info
            source_row = conn.execute(
                "SELECT * FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()

            # Get collection run stats
            runs = conn.execute(
                "SELECT COUNT(*) as total_runs, SUM(success) as successful_runs, MAX(started_at) as last_run FROM collection_runs WHERE source_id = ?",
                (source_id,),
            ).fetchone()

            # Get event counts
            events = conn.execute(
                "SELECT COUNT(*) as total_events, COUNT(DISTINCT content_hash) as unique_events FROM events WHERE source_id = ?",
                (source_id,),
            ).fetchone()

            return {
                "source_id": source_id,
                "source_name": source_row["source_name"] if source_row else source_id,
                "total_runs": runs["total_runs"] if runs else 0,
                "successful_runs": runs["successful_runs"] if runs else 0,
                "last_run": runs["last_run"] if runs else None,
                "total_events": events["total_events"] if events else 0,
                "unique_events": events["unique_events"] if events else 0,
            }

    def get_all_source_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all sources."""
        with self._get_connection() as conn:
            sources = conn.execute("SELECT source_id FROM sources").fetchall()
            return [self.get_source_stats(source["source_id"]) for source in sources]


# Global database instance
_database: Optional[Database] = None


def init_database(db_path: Optional[str] = None) -> Database:
    """Initialize the global database instance."""
    global _database

    if db_path is None:
        config = load_config()
        db_path = config.database.path

    _database = Database(db_path)
    return _database


def get_database() -> Database:
    """Get the global database instance."""
    global _database

    if _database is None:
        _database = init_database()

    return _database
