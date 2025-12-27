"""
Pydantic models for NRL match data validation (SPEC-1).
"""

from datetime import date

from pydantic import BaseModel, field_validator


class MatchRow(BaseModel):
    """Validated match row for database insertion."""

    match_id: str
    source: str = 'RLP'
    source_url: str | None = None
    season: int
    round: str
    date: date
    home_team: str
    away_team: str
    home_team_raw: str | None = None
    away_team_raw: str | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    venue: str | None = None
    venue_raw: str | None = None
    venue_id: int | None = None
    referee: str | None = None
    referee_raw: str | None = None
    referee_id: int | None = None
    crowd: int | None = None
    home_score: int
    away_score: int
    home_penalties: int | None = None
    away_penalties: int | None = None

    @field_validator('round')
    @classmethod
    def round_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('round must be non-empty')
        return v.strip()

    @field_validator('home_team', 'away_team')
    @classmethod
    def team_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('team must be non-empty')
        return v.strip()

    @property
    def is_finals(self) -> bool:
        """Check if this is a finals match."""
        return 'final' in self.round.lower()

    @property
    def home_win(self) -> bool:
        """Check if home team won."""
        return self.home_score > self.away_score

    @property
    def margin(self) -> int:
        """Get margin (positive = home win)."""
        return self.home_score - self.away_score
