"""
Point-in-Time (PIT) Validator.

Ensures no future data leakage in feature computation.
All features must use only data available before each match.
"""

from dataclasses import dataclass
from typing import List, Dict, Any

import pandas as pd


@dataclass
class PITViolation:
    """Record of a PIT violation that was blocked."""

    feature_name: str
    asof_timestamp: str
    future_rows_blocked: int


class PITValidator:
    """
    Point-in-Time validator to prevent data leakage.

    Usage:
        pit = PITValidator()

        # Before computing features, filter to PIT-safe data
        safe_data = pit.validate(
            "team_rolling_stats",
            historical_data,
            asof_ts=match_date,
            date_col="date"
        )

        # After all features computed, check for violations
        report = pit.report()
    """

    def __init__(self):
        self.violations: list[PITViolation] = []
        self._call_count = 0

    def validate(
        self,
        feature_name: str,
        source_df: pd.DataFrame,
        asof_ts: pd.Timestamp,
        date_col: str = "date",
    ) -> pd.DataFrame:
        """
        Filter dataframe to only include rows before asof_ts.

        Args:
            feature_name: Name of feature being computed (for logging)
            source_df: Source data to filter
            asof_ts: Point-in-time timestamp (exclusive)
            date_col: Name of date column

        Returns:
            Filtered dataframe with only past data
        """
        self._call_count += 1

        if source_df.empty:
            return source_df

        if date_col not in source_df.columns:
            return source_df

        # Convert dates
        dates = pd.to_datetime(source_df[date_col], errors="coerce")

        # Count future rows
        future_mask = dates >= asof_ts
        future_count = future_mask.sum()

        if future_count > 0:
            self.violations.append(
                PITViolation(
                    feature_name=feature_name,
                    asof_timestamp=str(asof_ts),
                    future_rows_blocked=int(future_count),
                )
            )

        # Return only past data
        return source_df[~future_mask].copy()

    def report(self) -> dict[str, Any]:
        """
        Generate PIT validation report.

        Returns:
            Dict with validation status and details
        """
        if not self.violations:
            return {
                "status": "CLEAN",
                "message": "No PIT violations detected",
                "total_calls": self._call_count,
                "violations_blocked": 0,
                "details": [],
            }

        total_blocked = sum(v.future_rows_blocked for v in self.violations)

        return {
            "status": "VIOLATIONS_BLOCKED",
            "message": f"Blocked {total_blocked} future rows across {len(self.violations)} features",
            "total_calls": self._call_count,
            "violations_blocked": len(self.violations),
            "total_rows_blocked": total_blocked,
            "details": [
                {
                    "feature": v.feature_name,
                    "asof": v.asof_timestamp,
                    "blocked": v.future_rows_blocked,
                }
                for v in self.violations[:10]  # Limit to first 10
            ],
        }

    def reset(self) -> None:
        """Reset validator state."""
        self.violations = []
        self._call_count = 0

    @property
    def is_clean(self) -> bool:
        """True if no violations were blocked."""
        return len(self.violations) == 0
