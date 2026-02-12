# CRAIGSLIST PHONOGRAPH SCRAPER (PRO EDITION)

The "Gold Standard" in lead discovery. This tool doesn't just scrape; it **thinks**.

## Coverage Areas (Florida East Coast)

- **Jacksonville & St. Augustine** (Georgia Border down to Flagler)
- **Daytona Beach** (Palm Coast to Edgewater)
- **Space Coast & Treasure Coast** (Titusville down to Fort Pierce)

## Search Logic (The "Smart" Way)

### 1. Multi-Target Keywords

We scan for high-value terms beyond just "landscaping":
- `sod`, `pavers`, `tree removal`, `drainage`, `grading`, `yard cleanup`, `lawn care`.

### 2. AI Triage Engine

Every post is piped through an AI Brain (`ai_lead_processor.py`) that:
- **Scores Leads (1-5)**: 5 = Clear Homeowner intent, 1 = Spam or Pro Ad.
- **Classifies Tiers**: Labels leads as **DIAMOND**, **POTENTIAL HOMEOWNER**, or **PRO ADVERTISING**.
- **Calculates Real Intent**: Subtracts points for "Company Speech" (Licensed/Insured) and adds points for "Pain Points" (Need help, estimate, backyard).

### 3. Exa MCP Integration

The `pro_lead_search.py` script shows how we use **Semantic Search** to find leads on Reddit and Nextdoor using the latest MCP technology.

## How to Use

1. **Initial Setup**: `pip install requests beautifulsoup4 pandas lxml`
2. **Check Craigslist**: `python phonograph_scraper.py`
3. **Check Web-Wide (Exa)**: `python pro_lead_search.py`
4. **View Dashboard**: Open `index.html` to see your AI-ranked leads.

## Automation

Run the scraper 4x daily to stay ahead of the competition. Flagged "New" leads will appear at the top of your dashboard.

