"""
Configuration management for Public Health Outbreak Intelligence.

This module handles loading and managing configuration from YAML files
and environment variables, providing a centralized configuration system.
"""

import os
from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field

from .models import SourceConfig


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = Field("data/outbreak_intel.db", description="Path to SQLite database")

    model_config = {"frozen": True}


class HTTPConfig(BaseModel):
    """HTTP client configuration."""

    timeout: int = Field(30, description="HTTP timeout in seconds")
    max_retries: int = Field(3, description="Maximum number of retries")
    user_agent: str = Field(
        "PublicHealthOutbreakIntelligence/0.1.0 (+https://github.com/Carlosdanger96/public-health-outbreak-intelligence)",
        description="User agent string for HTTP requests",
    )

    model_config = {"frozen": True}


class ScoringConfig(BaseModel):
    """Scoring policy configuration."""

    idaho_pnw_weight: int = Field(35, description="Maximum weight for Idaho/PNW relevance")
    healthcare_ip_weight: int = Field(25, description="Maximum weight for healthcare/IP relevance")
    official_urgency_weight: int = Field(20, description="Maximum weight for official urgency")
    travel_weight: int = Field(10, description="Maximum weight for US travel relevance")
    novelty_weight: int = Field(10, description="Maximum weight for novelty")

    # Thresholds for priority bands
    urgent_threshold: int = Field(75, description="Minimum score for urgent_human_review")
    review_threshold: int = Field(45, description="Minimum score for review_today")
    monitor_threshold: int = Field(20, description="Minimum score for monitor")

    model_config = {"frozen": True}


class AppConfig(BaseModel):
    """Main application configuration."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    http: HTTPConfig = Field(default_factory=HTTPConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    sources: list[SourceConfig] = Field(default_factory=list)
    demo_mode: bool = Field(False, description="Run in demo mode with fixtures")
    log_level: str = Field("INFO", description="Logging level")

    model_config = {"frozen": True}


def get_config_path() -> Path:
    """Get the path to the main configuration file."""
    # Check if running from source or installed
    if os.path.exists("config/sources.yaml"):
        return Path("config/sources.yaml")
    elif os.path.exists("/workspace/Carlosdanger96__Handler/config/sources.yaml"):
        return Path("/workspace/Carlosdanger96__Handler/config/sources.yaml")
    else:
        # Default path relative to project root
        return Path(__file__).parent.parent.parent.parent / "config" / "sources.yaml"


def load_sources_config() -> list[SourceConfig]:
    """Load source configurations from YAML file."""
    config_path = get_config_path()

    if not config_path.exists():
        # Return default sources if config file doesn't exist
        return [
            SourceConfig(
                source_id="cdc_han",
                source_name="CDC Health Alert Network",
                source_url="https://emergency.cdc.gov/han/",
                feed_url="https://emergency.cdc.gov/han/han-rss.asp",
                enabled=True,
                priority=10,
            ),
            SourceConfig(
                source_id="cdc_outbreaks",
                source_name="CDC Outbreak Investigations",
                source_url="https://www.cdc.gov/outbreaks/index.html",
                enabled=True,
                priority=9,
            ),
            SourceConfig(
                source_id="idaho_dhw",
                source_name="Idaho Department of Health and Welfare",
                source_url="https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases",
                enabled=True,
                priority=8,
            ),
            SourceConfig(
                source_id="who_don",
                source_name="WHO Disease Outbreak News",
                source_url="https://www.who.int/emergencies/disease-outbreak-news",
                feed_url="https://www.who.int/feeds/entity/134702/rss",
                enabled=True,
                priority=7,
            ),
        ]

    with open(config_path, "r", encoding="utf-8") as f:
        sources_data = yaml.safe_load(f) or {}

    sources = []
    for source_data in sources_data.get("sources", []):
        sources.append(SourceConfig(**source_data))

    return sources


def load_scoring_config() -> ScoringConfig:
    """Load scoring configuration from YAML file."""
    config_path = get_config_path().parent / "scoring_policy.yaml"

    if not config_path.exists():
        return ScoringConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        scoring_data = yaml.safe_load(f) or {}

    return ScoringConfig(**scoring_data.get("scoring", {}))


def load_config() -> AppConfig:
    """Load complete application configuration."""
    # Load from environment variables first
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "INFO")
    db_path = os.getenv("DATABASE_PATH", "data/outbreak_intel.db")
    timeout = int(os.getenv("HTTP_TIMEOUT", "30"))
    max_retries = int(os.getenv("MAX_RETRIES", "3"))
    user_agent = os.getenv(
        "USER_AGENT",
        "PublicHealthOutbreakIntelligence/0.1.0 (+https://github.com/Carlosdanger96/public-health-outbreak-intelligence)",
    )

    # Load sources and scoring configs
    sources = load_sources_config()
    scoring = load_scoring_config()

    return AppConfig(
        database=DatabaseConfig(path=db_path),
        http=HTTPConfig(timeout=timeout, max_retries=max_retries, user_agent=user_agent),
        scoring=scoring,
        sources=sources,
        demo_mode=demo_mode,
        log_level=log_level,
    )


def get_source_config(source_id: str, config: AppConfig) -> Optional[SourceConfig]:
    """Get configuration for a specific source."""
    for source in config.sources:
        if source.source_id == source_id:
            return source
    return None
