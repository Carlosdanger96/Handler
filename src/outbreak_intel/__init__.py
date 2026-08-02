"""
Public Health Outbreak Intelligence

A local, public-source outbreak-intelligence prototype for infection-prevention /
healthcare audiences. This package provides deterministic collection, normalization,
deduplication, scoring, and briefing generation for public health notices.

Key principles:
- Public source data only (no PHI, no patient data)
- Deterministic, transparent scoring and processing
- Human review required for all surfaced items
- No automatic notifications or alerting
- No clinical decision-making or diagnosis
"""

__version__ = "0.1.0"

from .config import get_config_path, load_config
from .db import Database, get_database, init_database
from .models import EventCard, SourceConfig

__all__ = [
    "__version__",
    "Database",
    "EventCard",
    "SourceConfig",
    "get_config_path",
    "get_database",
    "init_database",
    "load_config",
]
