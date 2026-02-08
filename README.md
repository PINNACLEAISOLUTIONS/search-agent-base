# CRAIGSLIST PHONOGRAPH SCRAPER

This tool monitors Craigslist for landscaping leads along the Florida East Coast, from **Fort Pierce** (Treasure Coast) up to the **Georgia Border** (Jacksonville).

## Coverage Areas
- **Treasure Coast** (Fort Pierce, Port St. Lucie, Vero Beach)
- **Space Coast** (Melbourne, Cocoa Beach, Titusville)
- **Daytona Beach** (Edgewater up to Palm Coast)
- **St. Augustine** (St. Johns County)
- **Jacksonville** (Duval County to the Georgia Line)

## Features
- **Live Search**: Pulls real-time results directly from Craigslist.
- **New Post Flagging**: Automatically tracks "seen" posts and flags only the results that are truly new since your last scan.
- **Multi-Region**: Scans all relevant East Coast subdomains in a single run.
- **History Tracking**: Saves all leads to `leads.csv` and `leads.json`.

## How to Use
1. **Run the Scraper**:
   Execute the script whenever you want to check for new leads (recommended 3-4 times a day).
   ```bash
   python phonograph_scraper.py
   ```
2. **Review Leads**:
   - Check the console output for `[NEW]` flags.
   - Open `leads.csv` in Excel to see the full list.
   - Open `index.html` to view the dashboard (requires a local server or simple open).

## Setup
- Requires Python 3.x
- Dependencies: `pip install requests beautifulsoup4 pandas lxml`

## Automation
To check 4 times a day automatically, you can set up a Windows Task Scheduler task to run `python.exe` pointing to `phonograph_scraper.py` at 8 AM, 12 PM, 4 PM, and 8 PM.
