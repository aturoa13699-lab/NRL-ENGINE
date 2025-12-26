-- SPEC-1 DDL for NRL Scraper (PostgreSQL 15)
-- Run: psql "$DATABASE_URL" -f scripts/bootstrap_db.sql

BEGIN;

-- Dimension tables
CREATE TABLE IF NOT EXISTS teams (
    team_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    aka TEXT[] DEFAULT '{}'::TEXT[]
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    aka TEXT[] DEFAULT '{}'::TEXT[],
    city TEXT,
    state TEXT,
    country TEXT
);

CREATE TABLE IF NOT EXISTS referees (
    referee_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- Core facts table
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT,
    season INT NOT NULL,
    round TEXT NOT NULL,
    date DATE NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_team_id INT REFERENCES teams(team_id),
    away_team_id INT REFERENCES teams(team_id),
    venue TEXT,
    venue_id INT REFERENCES venues(venue_id),
    referee TEXT,
    referee_id INT REFERENCES referees(referee_id),
    crowd INT,
    home_score INT NOT NULL,
    away_score INT NOT NULL,
    home_penalties INT,
    away_penalties INT,
    -- Raw fields for traceability
    home_team_raw TEXT,
    away_team_raw TEXT,
    venue_raw TEXT,
    referee_raw TEXT,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS uniq_matches_comp
    ON matches(season, date, home_team, away_team);
CREATE INDEX IF NOT EXISTS idx_matches_season_round
    ON matches(season, round);
CREATE INDEX IF NOT EXISTS idx_matches_date
    ON matches(date);

-- Extended stats table (optional enrichment)
CREATE TABLE IF NOT EXISTS match_stats (
    match_id TEXT PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
    home_possession_pct REAL,
    away_possession_pct REAL,
    home_completion_rate REAL,
    away_completion_rate REAL,
    home_run_metres INT,
    away_run_metres INT,
    home_post_contact_metres INT,
    away_post_contact_metres INT,
    source TEXT,
    scraped_at TIMESTAMPTZ DEFAULT now()
);

COMMIT;

-- Verification
SELECT 'Tables created:' AS status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
