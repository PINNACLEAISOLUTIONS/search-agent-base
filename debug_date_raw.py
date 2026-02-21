import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await stealth_async(context)
        page = await context.new_page()
        url = "https://miami.craigslist.org/search/atq?query=victrola&sort=date"
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        items = soup.select(".cl-search-result, .cl-static-search-result, .result-row")
        for item in items[:3]:
            span = item.select_one("span[title]")
            if span:
                print(f"TITLE: {span.get('title')}")
            time_tag = item.select_one("time")
            if time_tag:
                print(f"TIME TAG: {time_tag.get('datetime')}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
