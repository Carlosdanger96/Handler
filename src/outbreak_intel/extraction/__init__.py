"""
Extraction modules for Public Health Outbreak Intelligence.

This package contains modules for extracting structured information from
raw source data using deterministic rules and heuristics.
"""

from .base import BaseExtractor, ExtractionResult
from .heuristic import HeuristicExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "HeuristicExtractor",
]


def get_extractor(extractor_type: str = "heuristic") -> BaseExtractor:
    """Get the appropriate extractor."""
    extractors = {
        "heuristic": HeuristicExtractor,
    }

    extractor_class = extractors.get(extractor_type)
    if extractor_class:
        return extractor_class()
    else:
        raise ValueError(f"Unknown extractor type: {extractor_type}")
