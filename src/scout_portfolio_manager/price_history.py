"""Fixture-backed daily-close price history reader.

Mirrors portfolio.py's reader shape with a Protocol and one fixture-backed
implementation. This module has no live price-history source.
"""

import json
from pathlib import Path
from typing import Optional, Protocol, Union

from .contracts import AssetPriceHistory


class PriceHistoryReader(Protocol):
    """Read-only source of an asset's daily-close price history."""

    def series(self, asset: str) -> Optional[AssetPriceHistory]: ...


class FixturePriceHistoryReader:
    """Reads a synthetic, deterministic daily-close series from a JSON fixture."""

    def __init__(self, fixture_path: Union[str, Path]) -> None:
        self.fixture_path = Path(fixture_path)

    def series(self, asset: str) -> Optional[AssetPriceHistory]:
        """Return the validated history for ``asset``, or None if unobserved.

        None (never an exception) both when the asset key is absent from the
        fixture and when the fixture file itself does not exist, matching the
        existing observed/calculated/assumed/unknown idiom: a caller turns a
        None into an "unknown" entry rather than crashing.
        """
        try:
            raw = json.loads(self.fixture_path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        entry = raw.get(asset.upper())
        if entry is None:
            return None
        return AssetPriceHistory.model_validate(
            {
                "asset": asset.upper(),
                "source": entry["source"],
                "points": entry["daily_close"],
            }
        )
