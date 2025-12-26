"""
NRL Scraper - Main scraper implementation (SPEC-1).

Primary source: Rugby League Project (RLP)
URL pattern: https://www.rugbyleagueproject.org/seasons/nrl-{year}/results.html
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime, date
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from nrlscraper.config import settings
from nrlscraper.models import MatchRow
from nrlscraper.normalize import normalize_team, normalize_venue

logger = logging.getLogger('nrlscraper')


class FetchError(Exception):
    """HTTP fetch error (retriable)."""
    pass


class ParseError(Exception):
    """HTML parsing error."""
    pass


def log_event(**kv):
    """Emit structured JSON log line."""
    print(json.dumps(kv, separators=(',', ':')))


def make_match_id(
    season: int,
    round_label: str,
    date_iso: str,
    home: str,
    away: str,
    venue: str | None,
) -> str:
    """
    Generate stable, deterministic match_id.

    Uses BLAKE2s hash of canonical fields for collision resistance.
    """
    key = '|'.join([
        str(season),
        round_label.strip().lower(),
        date_iso,
        home.strip().lower(),
        away.strip().lower(),
        (venue or '').strip().lower(),
    ])
    return hashlib.blake2s(key.encode('utf-8'), digest_size=16).hexdigest()


class NRLScraper:
    """
    NRL match data scraper.

    Scrapes from Rugby League Project (RLP) with rate limiting and retries.
    """

    RLP_BASE = 'https://www.rugbyleagueproject.org'

    def __init__(self):
        self.client = httpx.Client(
            follow_redirects=True,
            headers={'User-Agent': settings.user_agent},
            timeout=settings.req_timeout_s,
        )
        self._last_request_time = 0.0

    def _season_url(self, year: int) -> str:
        """Build RLP season results URL."""
        return f'{self.RLP_BASE}/seasons/nrl-{year}/results.html'

    def _round_url(self, year: int, round_num: int) -> str:
        """Build RLP round URL."""
        return f'{self.RLP_BASE}/seasons/nrl-{year}/round-{round_num}/summary.html'

    def _finals_url(self, year: int, finals_type: str) -> str:
        """Build RLP finals URL."""
        return f'{self.RLP_BASE}/seasons/nrl-{year}/{finals_type}/summary.html'

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.retries),
        wait=wait_exponential_jitter(initial=0.5, max=6),
        retry=retry_if_exception_type((httpx.HTTPError, FetchError)),
    )
    def _get(self, url: str) -> httpx.Response:
        """Fetch URL with retry and rate limiting."""
        # Rate limiting (politeness)
        elapsed = time.time() - self._last_request_time
        sleep_time = (1.0 / settings.rate_limit_rps) - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        start = time.time()
        response = self.client.get(url)
        elapsed_ms = int((time.time() - start) * 1000)

        self._last_request_time = time.time()

        log_event(event='fetch', url=url, status=response.status_code, ms=elapsed_ms)

        if response.status_code >= 500:
            raise FetchError(f'Server error {response.status_code}')

        response.raise_for_status()
        return response

    def scrape_season(self, year: int, include_finals: bool = True) -> list[dict]:
        """
        Scrape all matches for a season.

        Args:
            year: Season year (1998-2025)
            include_finals: Include finals series

        Returns:
            List of validated match dicts
        """
        if year < settings.season_start or year > settings.season_end:
            raise ValueError(
                f'Season {year} out of range '
                f'({settings.season_start}-{settings.season_end})'
            )

        logger.info(f'Scraping season {year}...')
        all_rows: list[dict] = []

        # Scrape round-by-round (more reliable than results page)
        max_round = 27 if year >= 2007 else 26 if year >= 1998 else 22
        empty_streak = 0

        for round_num in range(1, max_round + 1):
            try:
                rows = self._scrape_round(year, round_num)
                if rows:
                    all_rows.extend(rows)
                    empty_streak = 0
                else:
                    empty_streak += 1
                    if empty_streak >= 3 and round_num > 10:
                        logger.debug(f'Stopping at round {round_num} after empty streak')
                        break
            except Exception as e:  # noqa: BLE001
                logger.warning(f'Failed to scrape round {round_num}: {e}')

        # Scrape finals
        if include_finals:
            finals_rows = self._scrape_finals(year)
            all_rows.extend(finals_rows)

        logger.info(f'Scraped {len(all_rows)} matches for {year}')
        return all_rows

    def _scrape_round(self, year: int, round_num: int) -> list[dict]:
        """Scrape a single round."""
        url = self._round_url(year, round_num)
        try:
            response = self._get(url)
        except Exception:  # noqa: BLE001
            return []

        return self._parse_results_page(response.text, year, url)

    def _scrape_finals(self, year: int) -> list[dict]:
        """Scrape finals series."""
        finals_types = [
            'qualif-final',
            'elim-final',
            'semi-final',
            'prelim-final',
            'grand-final',
        ]

        all_finals: list[dict] = []

        for finals_type in finals_types:
            url = self._finals_url(year, finals_type)
            try:
                response = self._get(url)
                rows = self._parse_results_page(response.text, year, url)
                all_finals.extend(rows)
            except Exception as e:  # noqa: BLE001
                logger.debug(f'Finals {finals_type} not found or failed: {e}')

        return all_finals

    def _parse_results_page(self, html: str, year: int, source_url: str) -> list[dict]:
        """
        Parse RLP results page HTML.

        Extracts match data from result text blocks.
        """
        soup = BeautifulSoup(html, 'lxml')
        page_text = soup.get_text()
        rows: list[dict] = []

        # Split by match indicators
        blocks = re.split(r'(?:>|View)\s+', page_text)

        for block in blocks:
            row = self._parse_match_block(block, year, source_url)
            if row:
                rows.append(row)

        return rows

    def _parse_match_block(self, block: str, year: int, source_url: str) -> Optional[dict]:
        """Parse a single match block."""
        try:
            # Pattern: "Team A NN (scorers...) defeated/drew Team B NN (scorers...) at Venue."
            patterns = [
                # Full pattern with scorers
                r'([A-Za-z\s]+?)\s+(\d+)\s+\([^)]+\)\s+(defeated|drew with|lost to)\s+([A-Za-z\s]+?)\s+(\d+)\s+\([^)]+\)\s+at\s+([^.]+)',
                # Simple pattern without scorers
                r'([A-Za-z\s]+?)\s+(\d+)\s+(defeated|drew with)\s+([A-Za-z\s]+?)\s+(\d+)\s+at\s+([^.]+)',
            ]

            result_match = None
            for pattern in patterns:
                result_match = re.search(pattern, block, re.IGNORECASE)
                if result_match:
                    break

            if not result_match:
                return None

            home_raw = result_match.group(1).strip()
            home_score = int(result_match.group(2))
            away_raw = result_match.group(4).strip()
            away_score = int(result_match.group(5))
            venue_raw = result_match.group(6).strip()

            # Normalize
            home_team = normalize_team(home_raw)
            away_team = normalize_team(away_raw)
            venue = normalize_venue(venue_raw)

            # Extract round label
            round_match = re.search(r'Round\s+(\d+)', block, re.IGNORECASE)
            if round_match:
                round_label = f'Round {round_match.group(1)}'
            else:
                # Check for finals
                for finals_name in ['Qualifying Final', 'Elimination Final', 'Semi Final',
                                   'Preliminary Final', 'Grand Final']:
                    if finals_name.lower() in block.lower():
                        round_label = finals_name
                        break
                else:
                    # Try to extract from URL
                    url_round = re.search(r'round-(\d+)', source_url)
                    if url_round:
                        round_label = f'Round {url_round.group(1)}'
                    else:
                        for ft in ['qualif-final', 'elim-final', 'semi-final', 'prelim-final', 'grand-final']:
                            if ft in source_url:
                                round_label = ft.replace('-', ' ').title()
                                break
                        else:
                            round_label = 'Unknown'

            # Extract date
            date_match = re.search(r'Date:\s*([A-Za-z]+,?\s*\d+[a-z]*\s+[A-Za-z]+)', block)
            if date_match:
                match_date = self._parse_date(date_match.group(1), year)
            else:
                # Estimate from round
                match_date = date(year, 3, 1)

            # Extract referee
            ref_match = re.search(r'Referee:\s*([A-Za-z\s\.]+?)(?:\.|Crowd)', block)
            referee_raw = ref_match.group(1).strip() if ref_match else None
            referee = referee_raw  # No normalization needed for referees

            # Extract crowd
            crowd_match = re.search(r'Crowd:\s*([\d,]+)', block)
            crowd = int(crowd_match.group(1).replace(',', '')) if crowd_match else None

            # Extract penalties
            pen_match = re.search(r'Penalties:\s*[A-Za-z]+\s+(\d+)-(\d+)', block)
            home_penalties = int(pen_match.group(1)) if pen_match else None
            away_penalties = int(pen_match.group(2)) if pen_match else None

            # Generate match_id
            date_iso = match_date.isoformat()
            match_id = make_match_id(year, round_label, date_iso, home_team, away_team, venue)

            # Build row
            row_data = {
                'match_id': match_id,
                'source': 'RLP',
                'source_url': source_url,
                'season': year,
                'round': round_label,
                'date': match_date,
                'home_team': home_team,
                'away_team': away_team,
                'home_team_raw': home_raw,
                'away_team_raw': away_raw,
                'venue': venue,
                'venue_raw': venue_raw,
                'referee': referee,
                'referee_raw': referee_raw,
                'crowd': crowd,
                'home_score': home_score,
                'away_score': away_score,
                'home_penalties': home_penalties,
                'away_penalties': away_penalties,
            }

            # Validate with Pydantic
            validated = MatchRow(**row_data)

            log_event(
                event='row',
                season=year,
                round=round_label,
                home=home_team,
                away=away_team,
            )

            return validated.model_dump()

        except Exception as e:  # noqa: BLE001
            logger.debug(f'Parse error: {e}')
            return None

    def _parse_date(self, date_str: str, year: int) -> date:
        """Parse RLP date format."""
        try:
            # Remove ordinal suffixes
            date_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            date_clean = date_clean.replace(',', '').strip()

            for fmt in ['%a %d %B', '%A %d %B', '%d %B']:
                try:
                    dt = datetime.strptime(date_clean, fmt)
                    return dt.replace(year=year).date()
                except ValueError:
                    continue

            return date(year, 1, 1)
        except Exception:  # noqa: BLE001
            return date(year, 1, 1)

    def scrape_historical(
        self,
        start_year: int,
        end_year: int,
        include_finals: bool = True,
    ) -> list[dict]:
        """
        Scrape multiple seasons sequentially.

        Args:
            start_year: First season
            end_year: Last season (inclusive)
            include_finals: Include finals series

        Returns:
            List of all match dicts
        """
        all_rows: list[dict] = []

        for year in range(start_year, end_year + 1):
            try:
                rows = self.scrape_season(year, include_finals=include_finals)
                all_rows.extend(rows)
                log_event(event='season_complete', season=year, matches=len(rows))
            except Exception as e:  # noqa: BLE001
                logger.error(f'Failed to scrape {year}: {e}')
                log_event(event='season_failed', season=year, error=str(e))

        return all_rows
