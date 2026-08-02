"""
Base collector class for Public Health Outbreak Intelligence.

This module defines the abstract base class that all collectors must implement,
providing a consistent interface for data collection from various sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any
import httpx
from bs4 import BeautifulSoup

from ..models import EventCard, SourceConfig
from ..config import AppConfig, get_source_config


class CollectorResult:
    """Result of a collection operation."""

    def __init__(
        self,
        source_id: str,
        source_name: str,
        success: bool,
        retrieved_at: datetime,
        items: list[dict[str, Any]] = [],
        error_message: Optional[str] = None,
    ):
        self.source_id = source_id
        self.source_name = source_name
        self.success = success
        self.retrieved_at = retrieved_at
        self.items = items
        self.error_message = error_message
        self.item_count = len(items)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "success": self.success,
            "retrieved_at": self.retrieved_at.isoformat(),
            "item_count": self.item_count,
            "items": self.items,
            "error_message": self.error_message,
        }


class BaseCollector(ABC):
    """
    Abstract base class for all collectors.

    Collectors are responsible for:
    1. Fetching data from their assigned source
    2. Parsing the data into structured items
    3. Returning the items with proper metadata
    4. Handling errors gracefully
    """

    def __init__(self, config: AppConfig, source_config: Optional[SourceConfig] = None):
        """Initialize the collector."""
        self.config = config

        if source_config is None:
            # Extract source config from the main config
            source_id = self.get_source_id()
            source_config = get_source_config(source_id, config)

        if source_config is None:
            raise ValueError(f"Source configuration not found for {self.get_source_id()}")

        self.source_config = source_config
        self.client = self._create_http_client()

    @abstractmethod
    def get_source_id(self) -> str:
        """Get the unique identifier for this source."""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Get the human-readable name for this source."""
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """Get the base URL for this source."""
        pass

    def _create_http_client(self) -> httpx.Client:
        """Create an HTTP client with proper configuration."""
        timeout = self.source_config.timeout or self.config.http.timeout
        user_agent = self.source_config.user_agent or self.config.http.user_agent

        return httpx.Client(
            timeout=timeout, headers={"User-Agent": user_agent}, follow_redirects=True
        )

    def _fetch_url(self, url: str, max_retries: Optional[int] = None) -> Optional[str]:
        """Fetch a URL with retry logic."""
        if max_retries is None:
            max_retries = self.config.http.max_retries

        for attempt in range(max_retries + 1):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPStatusError as e:
                if attempt == max_retries:
                    raise
                # Wait before retrying
                import time

                time.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                if attempt == max_retries:
                    raise
                import time

                time.sleep(2**attempt)

        return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, "html.parser")

    @abstractmethod
    def collect(self) -> CollectorResult:
        """
        Collect data from the source.

        Returns:
            CollectorResult with the collected items and metadata
        """
        pass

    @abstractmethod
    def parse_item(self, item_data: dict[str, Any]) -> Optional[EventCard]:
        """
        Parse a single item into an EventCard.

        Args:
            item_data: Raw data from the source

        Returns:
            EventCard if parsing successful, None otherwise
        """
        pass

    def close(self) -> None:
        """Close the collector and clean up resources."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
