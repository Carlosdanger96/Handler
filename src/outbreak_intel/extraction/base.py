"""
Base extractor class for Public Health Outbreak Intelligence.

This module defines the abstract base class that all extractors must implement,
providing a consistent interface for extracting structured data from raw content.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any
from datetime import datetime

from ..models import EventCard


class ExtractionResult:
    """Result of an extraction operation."""

    def __init__(
        self,
        success: bool,
        event: Optional[EventCard] = None,
        extracted_data: dict[str, Any] = {},
        error_message: Optional[str] = None,
        confidence: str = "medium",
    ):
        self.success = success
        self.event = event
        self.extracted_data = extracted_data
        self.error_message = error_message
        self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "event": self.event.to_dict() if self.event else None,
            "extracted_data": self.extracted_data,
            "error_message": self.error_message,
            "confidence": self.confidence,
        }


class BaseExtractor(ABC):
    """
    Abstract base class for all extractors.

    Extractors are responsible for:
    1. Taking raw content from a source
    2. Extracting structured information (disease, geography, counts, etc.)
    3. Returning an enriched EventCard with extracted data
    4. Providing confidence levels for extracted information
    """

    @abstractmethod
    def extract(self, raw_content: str, source_url: str, source_id: str) -> ExtractionResult:
        """
        Extract structured information from raw content.

        Args:
            raw_content: The raw text content from the source
            source_url: The URL of the source
            source_id: The ID of the source

        Returns:
            ExtractionResult with the extracted data
        """
        pass

    @abstractmethod
    def extract_disease(self, text: str) -> Optional[str]:
        """Extract disease or hazard information from text."""
        pass

    @abstractmethod
    def extract_geography(self, text: str) -> list[dict[str, Any]]:
        """Extract geographic information from text."""
        pass

    @abstractmethod
    def extract_counts(self, text: str) -> dict[str, Optional[int]]:
        """Extract case and death counts from text."""
        pass

    @abstractmethod
    def extract_facts(self, text: str) -> list[dict[str, Any]]:
        """Extract explicit facts from text."""
        pass

    @abstractmethod
    def extract_unknowns(self, text: str) -> list[str]:
        """Extract unknowns and uncertainties from text."""
        pass
