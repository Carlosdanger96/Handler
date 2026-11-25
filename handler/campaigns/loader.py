"""Load and validate campaign definitions from JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Campaign


def campaign_from_dict(data: dict) -> Campaign:
    if not isinstance(data, dict):
        raise ValueError("campaign definition must be a JSON object")
    return Campaign.from_dict(data)


def load_campaign(path: str | Path) -> Campaign:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"campaign file not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"campaign file {source} is not valid JSON: {exc}") from exc
    return campaign_from_dict(data)
