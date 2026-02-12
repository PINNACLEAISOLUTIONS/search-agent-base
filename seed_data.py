# Targeted sweep script to get immediate data

import json
import datetime
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
from ai_lead_processor import AIAntiqueProcessor
import pandas as pd

# Just 3 top regions to get immediate results quickly
REGIONS = {
    "Miami": "https://miami.craigslist.org",
    "Tampa": "https://tampa.craigslist.org",
    "Orlando": "https://orlando.craigslist.org",
}

# Targeted Antique Keywords (High probability only)
SEARCH_KEYWORDS = ["victrola", "phonograph", "antique"]


async def scrape():
    print("Running FAST sweep for immediate leads...")
    leads = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await stealth_async(page)

        processor = AIAntiqueProcessor()

        for region, url in REGIONS.items():
            for kw in SEARCH_KEYWORDS:
                try:
                    print(f"Scanning {region} for {kw}...")
                    await page.goto(f"{url}/search/atq?query={kw}", timeout=30000)
                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")

                    for res in soup.select(".result-row"):
                        try:
                            a = res.select_one(".titlestring")
                            if not a:
                                continue

                            title = a.get_text().strip()
                            link = a["href"]
                            if not link.startswith("http"):
                                link = f"{url}{link}"

                            analysis = processor.score_lead(title)

                            leads.append(
                                {
                                    "id": link.split("/")[-1].split(".")[0],
                                    "title": title,
                                    "link": link,
                                    "region": region,
                                    "keyword": kw,
                                    "score": analysis["score"],
                                    "classification": analysis["classification"],
                                    "timestamp": datetime.datetime.now().isoformat(),
                                    "is_new": True,
                                }
                            )
                            print(f"  Found: {title}")
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Skipping {region}: {e}")

        await browser.close()

    print(f"Found {len(leads)} leads. Saving...")

    # Save lead files
    with open("leads.json", "w") as f:
        json.dump(leads, f)

    pd.DataFrame(leads).to_csv("leads.csv", index=False)


if __name__ == "__main__":
    asyncio.run(scrape())
