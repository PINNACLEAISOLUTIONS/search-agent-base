from ai_lead_processor import AIAntiqueProcessor

# Pro Lead Discovery for Antiques (Reddit, Forums, etc.)


def run_pro_antique_search():
    print("=" * 40)
    print("PRO ANTIQUE DISCOVERY ENGINE (EXA MCP)")
    print("=" * 40)

    # Simulation of wide-web semantic search
    search_queries = [
        "antique phonograph for sale Florida",
        "Edison cylinder machine Craigslist Florida",
        "Victor Victrola VV-XVI for sale",
        "Columbia Graphophone antique marketplace",
    ]

    print(f"Executing semantic search for {len(search_queries)} collector queries...")

    processor = AIAntiqueProcessor()

    # Simulated results from Exa/Reddit
    sim_findings = [
        {
            "title": "Estate Sale: Working Edison Diamond Disc with records",
            "url": "https://reddit.com/r/antiques/test1",
        },
        {
            "title": "Vintage Victor Victrola in great condition - Orlando area",
            "url": "https://nextdoor.com/p/test2",
        },
    ]

    for lead in sim_findings:
        analysis = processor.score_lead(lead["title"])
        print(f"\nPotential Machine Found:")
        print(f"Title: {lead['title']}")
        print(f"URL: {lead['url']}")
        print(f"AI Score: {analysis['score']} - {analysis['classification']}")


if __name__ == "__main__":
    run_pro_antique_search()
