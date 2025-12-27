from __future__ import annotations

from pathlib import Path

import lxml.html as LH
import pandas as pd

from .common import finalize, to_decimal

try:
    from nrlscraper.normalize import normalize_team
except Exception:
    def normalize_team(name: str) -> str:
        return (name or "").strip()


def parse(html_path: str) -> pd.DataFrame:
    root = LH.parse(str(Path(html_path))).getroot()
    rows = []
    for card in root.xpath("//a[contains(@href,'/rugby-league/australia/nrl') and .//div[contains(@class,'event-name')]]"):
        home = "".join(card.xpath(".//div[contains(@class,'participant--home')]//text()")).strip()
        away = "".join(card.xpath(".//div[contains(@class,'participant--away')]//text()")).strip()
        home_price = "".join(card.xpath(".//span[contains(@class,'odd')][1]//text()")).strip()
        away_price = "".join(card.xpath(".//span[contains(@class,'odd')][last()]//text()")).strip()
        iso_dt = "".join(card.xpath(".//time/@datetime"))
        rows.append(
            {
                "date": iso_dt[:10] if iso_dt else None,
                "home_team": normalize_team(home),
                "away_team": normalize_team(away),
                "home_odds_close": to_decimal(home_price),
                "away_odds_close": to_decimal(away_price),
            }
        )
    return finalize(pd.DataFrame(rows), "oddspedia")
