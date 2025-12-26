"""
Tests for NRL Scraper (SPEC-1).

Unit tests run without network access.
Integration tests (marked) hit live RLP site.
"""
import pytest
from datetime import date

from nrlscraper import NRLScraper, normalize_team, normalize_venue
from nrlscraper.models import MatchRow
from nrlscraper.scraper import make_match_id


class TestNormalization:
    """Tests for team/venue normalization."""

    def test_team_aliases(self):
        """Test various team name formats normalize correctly."""
        assert normalize_team('broncos') == 'Brisbane Broncos'
        assert normalize_team('Panthers') == 'Penrith Panthers'
        assert normalize_team('STORM') == 'Melbourne Storm'
        assert normalize_team('north qld') == 'North Queensland Cowboys'
        assert normalize_team('souths') == 'South Sydney Rabbitohs'
        assert normalize_team('st geo illa') == 'St George Illawarra Dragons'

    def test_venue_aliases(self):
        """Test venue normalization."""
        assert normalize_venue('suncorp') == 'Suncorp Stadium'
        assert normalize_venue('brookvale') == '4 Pines Park'
        assert normalize_venue('qld country bank') == 'Queensland Country Bank Stadium'
        assert normalize_venue('AAMI Park') == 'AAMI Park'

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert normalize_team('BRONCOS') == 'Brisbane Broncos'
        assert normalize_team('Broncos') == 'Brisbane Broncos'
        assert normalize_team('broncos') == 'Brisbane Broncos'

    def test_unknown_returns_original(self):
        """Test unknown names return original."""
        assert normalize_team('Unknown Team XYZ') == 'Unknown Team XYZ'
        assert normalize_venue('Some Random Venue') == 'Some Random Venue'


class TestMatchId:
    """Tests for match_id generation."""

    def test_deterministic(self):
        """Test match_id is deterministic."""
        id1 = make_match_id(
            2024, 'Round 1', '2024-03-02',
            'Brisbane Broncos', 'Sydney Roosters', 'Suncorp Stadium'
        )
        id2 = make_match_id(
            2024, 'Round 1', '2024-03-02',
            'Brisbane Broncos', 'Sydney Roosters', 'Suncorp Stadium'
        )
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        """Test different inputs produce different IDs."""
        id1 = make_match_id(
            2024, 'Round 1', '2024-03-02',
            'Brisbane Broncos', 'Sydney Roosters', 'Suncorp Stadium'
        )
        id2 = make_match_id(
            2024, 'Round 2', '2024-03-09',
            'Brisbane Broncos', 'Sydney Roosters', 'Suncorp Stadium'
        )
        assert id1 != id2

    def test_hex_format(self):
        """Test match_id is valid hex (BLAKE2s digest_size=16 = 32 hex chars)."""
        mid = make_match_id(2024, 'Round 1', '2024-03-02', 'Brisbane', 'Sydney', 'Venue')
        assert len(mid) == 32  # BLAKE2s with digest_size=16
        assert all(c in '0123456789abcdef' for c in mid)


class TestModels:
    """Tests for Pydantic models."""

    def test_match_row_valid(self):
        """Test valid match creation."""
        match = MatchRow(
            match_id='abc123' * 7,  # 42 chars
            season=2024,
            round='Round 1',
            date=date(2024, 3, 2),
            home_team='Brisbane Broncos',
            away_team='Sydney Roosters',
            home_score=24,
            away_score=18,
            venue='Suncorp Stadium',
            referee='Ashley Klein',
            crowd=45000,
        )
        assert match.home_win is True
        assert match.margin == 6
        assert match.is_finals is False

    def test_match_row_finals(self):
        """Test finals detection."""
        match = MatchRow(
            match_id='xyz789' * 7,
            season=2024,
            round='Grand Final',
            date=date(2024, 10, 6),
            home_team='Melbourne Storm',
            away_team='Penrith Panthers',
            home_score=6,
            away_score=14,
        )
        assert match.is_finals is True
        assert match.home_win is False

    def test_match_row_validation(self):
        """Test validation rejects invalid data."""
        with pytest.raises(ValueError):
            MatchRow(
                match_id='test',
                season=2024,
                round='',  # Empty round should fail
                date=date(2024, 3, 2),
                home_team='Brisbane',
                away_team='Sydney',
                home_score=0,
                away_score=0,
            )


class TestScraper:
    """Tests for NRL Scraper."""

    def test_season_url_template(self):
        """Test RLP URL uses correct /seasons/ path (SPEC-1 guard)."""
        scraper = NRLScraper()
        url = scraper._season_url(2024)
        assert '/seasons/nrl-2024/results.html' in url
        assert '/competitions/' not in url

    def test_round_url_template(self):
        """Test round URL format."""
        scraper = NRLScraper()
        url = scraper._round_url(2024, 1)
        assert '/seasons/nrl-2024/round-1/summary.html' in url

    def test_finals_url_template(self):
        """Test finals URL format."""
        scraper = NRLScraper()
        url = scraper._finals_url(2024, 'grand-final')
        assert '/seasons/nrl-2024/grand-final/summary.html' in url


class TestRLP2024:
    """
    Integration tests against live RLP 2024 data.

    Expected: 204 regular + 9 finals = 213 total.
    These tests hit the live RLP site.
    """

    @pytest.fixture
    def season_2024_rows(self):
        """Fetch 2024 season data."""
        scraper = NRLScraper()
        return scraper.scrape_season(2024, include_finals=True)

    @pytest.mark.integration
    def test_2024_total_matches(self, season_2024_rows):
        """Test 2024 has 213 total matches."""
        assert len(season_2024_rows) == 213

    @pytest.mark.integration
    def test_2024_regular_season(self, season_2024_rows):
        """Test 2024 has 204 regular season matches."""
        regular = [r for r in season_2024_rows if 'final' not in r['round'].lower()]
        assert len(regular) == 204

    @pytest.mark.integration
    def test_2024_finals(self, season_2024_rows):
        """Test 2024 has 9 finals matches."""
        finals = [r for r in season_2024_rows if 'final' in r['round'].lower()]
        assert len(finals) == 9

    @pytest.mark.integration
    def test_2024_required_columns(self, season_2024_rows):
        """Test required columns are present."""
        required = ['match_id', 'date', 'season', 'round', 'home_team', 'away_team', 'venue', 'referee', 'crowd']
        row = season_2024_rows[0]
        for col in required:
            assert col in row, f'Missing column: {col}'
