import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await stealth_async(context)
        page = await context.new_page()
        url = "https://miami.craigslist.org/search/atq?query=victrola"
        print(f"Visiting {url}...")
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Page content saved to debug_page.html")

        # Check for results
        results = await page.query_selector_all(".cl-search-result")
        print(f"Found {len(results)} .cl-search-result items")

        results_static = await page.query_selector_all(".cl-static-search-result")
        print(f"Found {len(results_static)} .cl-static-search-result items")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
