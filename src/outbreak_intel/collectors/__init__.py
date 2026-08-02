"""
Collectors for Public Health Outbreak Intelligence.

This package contains modules for collecting data from various public health
sources, including CDC HAN, CDC Outbreaks, Idaho DHW, and WHO DON.
"""

from .base import BaseCollector, CollectorResult
from .cdc_han import CDC_HAN_Collector
from .cdc_outbreaks import CDC_Outbreaks_Collector
from .idaho_dhw import Idaho_DHW_Collector
from .who_don import WHO_DON_Collector

__all__ = [
    "BaseCollector",
    "CollectorResult",
    "CDC_HAN_Collector",
    "CDC_Outbreaks_Collector",
    "Idaho_DHW_Collector",
    "WHO_DON_Collector",
]


def get_collector(source_id: str, config) -> BaseCollector:
    """Get the appropriate collector for a source ID."""
    collectors = {
        "cdc_han": CDC_HAN_Collector,
        "cdc_outbreaks": CDC_Outbreaks_Collector,
        "idaho_dhw": Idaho_DHW_Collector,
        "who_don": WHO_DON_Collector,
    }

    collector_class = collectors.get(source_id)
    if collector_class:
        return collector_class(config)
    else:
        raise ValueError(f"Unknown source ID: {source_id}")
