from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

TARGETS = {
    "oddspedia": "https://oddspedia.com/rugby-league/australia/nrl/odds",
    "oddschecker_outrights": "https://www.oddschecker.com/rugby-league/australia/nrl/regular-season-winner",
}
STEALTH = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",
    "--disable-dev-shm-usage",
]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def scrape() -> None:
    today = datetime.utcnow().strftime("%Y%m%d")
    base = Path(f"manual_feeds/{today}")
    base.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=STEALTH)
        context = await browser.new_context(
            user_agent=UA, viewport={"width": 1920, "height": 1080}, locale="en-AU"
        )
        for name, url in TARGETS.items():
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)
                title = await page.title()
                if any(flag in title for flag in ["Just a moment", "Access denied", "Cloudflare"]):
                    print(f"BLOCKED: {name}")
                else:
                    html = await page.content()
                    (base / f"{name}_auto.html").write_text(html, encoding="utf-8")
                    print("SAVED:", base / f"{name}_auto.html")
            except Exception as exc:  # noqa: BLE001
                print("SCRAPE ERROR", name, exc)
            finally:
                await page.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape())
