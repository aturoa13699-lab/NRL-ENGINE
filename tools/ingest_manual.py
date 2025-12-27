from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd

from ingestors import oddspedia


def main() -> int:
    rows = []
    for file_path in glob.glob("manual_feeds/*/oddspedia*_auto.html"):
        try:
            rows.append(oddspedia.parse(file_path))
        except Exception as exc:  # noqa: BLE001
            print("Parse fail", file_path, exc)

    if not rows:
        print("No scraped HTML found; skip.")
        return 0

    df = pd.concat(rows, ignore_index=True).drop_duplicates(
        subset=["date", "home_team", "away_team"], keep="last"
    )
    out = Path("data/sources/odds.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        base = pd.read_csv(out)
        df = (
            pd.concat([base, df], ignore_index=True)
            .drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")
        )

    df.sort_values(["date", "home_team", "away_team"], inplace=True)
    df.to_csv(out, index=False)
    print("Wrote", out, "rows", len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
