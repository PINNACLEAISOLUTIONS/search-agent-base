from playwright.async_api import async_playwright
import asyncio


async def debug_selectors():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )  # Run headless to capture output
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        url = "https://miami.craigslist.org/search/atq?query=victrola"
        print(f"Navigating to {url}...")
        await page.goto(url)
        await page.wait_for_timeout(5000)  # Wait for potential JS load

        # Snapshot HTML to see what we really got
        content = await page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(content)

        print("HTML saved to debug_page.html")

        # Test selectors directly
        results = await page.query_selector_all(".cl-search-result")
        print(f"Found {len(results)} via .cl-search-result")

        results_row = await page.query_selector_all(".result-row")
        print(f"Found {len(results_row)} via .result-row")

        # Check for blocking
        title = await page.title()
        print(f"Page Title: {title}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_selectors())
