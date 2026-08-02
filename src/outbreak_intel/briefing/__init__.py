"""
Briefing modules for Public Health Outbreak Intelligence.

This package contains modules for generating Markdown briefings
and other reports from the collected and processed events.
"""

from .markdown import generate_briefing, BriefingOptions

__all__ = [
    "generate_briefing",
    "BriefingOptions",
]
