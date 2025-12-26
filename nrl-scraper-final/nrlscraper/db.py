"""
Database layer for NRL Scraper (SPEC-1).

PostgreSQL 15 via SQLAlchemy 2.0 + psycopg3.
"""
from contextlib import contextmanager
from typing import Iterable, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from nrlscraper.config import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Get or create database engine."""
    global _engine
    if _engine is None:
        if not settings.db_url:
            raise ValueError('DATABASE_URL not configured')
        # Handle Railway postgres:// -> postgresql://
        db_url = settings.db_url.replace('postgres://', 'postgresql+psycopg://')
        if 'postgresql://' in db_url and '+psycopg' not in db_url:
            db_url = db_url.replace('postgresql://', 'postgresql+psycopg://')
        _engine = create_engine(db_url, pool_pre_ping=True, pool_size=4, max_overflow=4)
    return _engine


@contextmanager
def session() -> Generator[Connection, None, None]:
    """Get transactional database connection."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


# Upsert SQL with ON CONFLICT
UPSERT_MATCH = text("""
INSERT INTO matches (
    match_id, source, source_url, season, round, date,
    home_team, away_team, home_team_id, away_team_id,
    venue, venue_id, referee, referee_id, crowd,
    home_score, away_score, home_penalties, away_penalties,
    home_team_raw, away_team_raw, venue_raw, referee_raw, updated_at
) VALUES (
    :match_id, :source, :source_url, :season, :round, :date,
    :home_team, :away_team, :home_team_id, :away_team_id,
    :venue, :venue_id, :referee, :referee_id, :crowd,
    :home_score, :away_score, :home_penalties, :away_penalties,
    :home_team_raw, :away_team_raw, :venue_raw, :referee_raw, now()
)
ON CONFLICT (match_id) DO UPDATE SET
    source = EXCLUDED.source,
    source_url = EXCLUDED.source_url,
    season = EXCLUDED.season,
    round = EXCLUDED.round,
    date = EXCLUDED.date,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    home_team_id = EXCLUDED.home_team_id,
    away_team_id = EXCLUDED.away_team_id,
    venue = EXCLUDED.venue,
    venue_id = EXCLUDED.venue_id,
    referee = EXCLUDED.referee,
    referee_id = EXCLUDED.referee_id,
    crowd = EXCLUDED.crowd,
    home_score = EXCLUDED.home_score,
    away_score = EXCLUDED.away_score,
    home_penalties = EXCLUDED.home_penalties,
    away_penalties = EXCLUDED.away_penalties,
    home_team_raw = EXCLUDED.home_team_raw,
    away_team_raw = EXCLUDED.away_team_raw,
    venue_raw = EXCLUDED.venue_raw,
    referee_raw = EXCLUDED.referee_raw,
    updated_at = now();
""")


def upsert_matches(rows: Iterable[dict]) -> int:
    """
    Upsert matches to database (idempotent).

    Args:
        rows: Iterable of match dicts

    Returns:
        Number of rows processed
    """
    count = 0
    with session() as conn:
        for row in rows:
            conn.execute(UPSERT_MATCH, row)
            count += 1
    return count


def count_matches(season: int | None = None) -> int:
    """Count matches in database."""
    with session() as conn:
        if season:
            result = conn.execute(
                text('SELECT COUNT(*) FROM matches WHERE season = :season'),
                {'season': season},
            )
        else:
            result = conn.execute(text('SELECT COUNT(*) FROM matches'))
        return result.scalar() or 0


def load_matches(season: int | None = None) -> list[dict]:
    """Load matches from database."""
    with session() as conn:
        if season:
            result = conn.execute(
                text('SELECT * FROM matches WHERE season = :season ORDER BY date'),
                {'season': season},
            )
        else:
            result = conn.execute(text('SELECT * FROM matches ORDER BY date'))
        return [dict(row._mapping) for row in result]
