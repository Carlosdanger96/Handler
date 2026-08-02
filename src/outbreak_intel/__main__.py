"""
Main entry point for Public Health Outbreak Intelligence.

This module allows the package to be executed directly using:
    python -m outbreak_intel
"""

from .cli import app

if __name__ == "__main__":
    app()
