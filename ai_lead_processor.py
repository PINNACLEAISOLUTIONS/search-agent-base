# This is the Specialized Antique AI Processor for OldTimeCrank Search.


class AIAntiqueProcessor:
    def __init__(self):
        # Major Collector Brands
        self.high_value_brands = [
            "edison",
            "victor",
            "columbia",
            "victrola",
            "gramophone",
            "graphophone",
        ]
        # Key Antique terms
        self.antique_indicators = [
            "antique",
            "vintage",
            "old",
            "early",
            "cylinder",
            "crank",
            "horn",
            "78rpm",
        ]
        # Modern/Reproduction flags (to be wary of)
        self.red_flags = [
            "repro",
            "reproduction",
            "crosley",
            "modern",
            "fake",
            "replica",
            "bluetooth",
            "usb",
        ]

    def score_lead(self, title, content=""):
        text = (title + " " + content).lower()
        score = 1.0

        # 1. Check for Brands
        brand_matches = [b for b in self.high_value_brands if b in text]
        if brand_matches:
            score += len(brand_matches) * 1.5

        # 2. Check for Antique Context
        context_matches = [c for c in self.antique_indicators if c in text]
        if context_matches:
            score += len(context_matches) * 0.5

        # 3. Penalize Repros (The "Crosley" rule)
        repro_matches = [r for r in self.red_flags if r in text]
        if repro_matches:
            score -= len(repro_matches) * 2.0

        # 4. Classification
        classification = "POTENTIAL FIND"
        if score >= 4.0:
            classification = "HIGH-VALUE ANTIQUE"
        elif score <= 1.5:
            classification = "LOW INTEREST / MODERN"
        elif any(b in text for b in ["edison", "victrola"]):
            classification = "BRAND NAME SIGHTING"

        return {
            "score": round(max(0, min(5, score)), 1),
            "classification": classification,
            "analysis": f"Found {len(brand_matches)} brands and {len(context_matches)} context terms. Repro flags: {len(repro_matches)}.",
        }

    def process_leads(self, leads):
        processed = []
        for lead in leads:
            analysis = self.score_lead(lead["title"])
            lead.update(analysis)
            processed.append(lead)
        return processed


if __name__ == "__main__":
    p = AIAntiqueProcessor()
    test = [
        "Edison Cylinder Phonograph with horn",
        "Modern Victrola Bluetooth record player",
        "Old Columbia Graphophone found in attic",
        "Victor Talking Machine Victrola VV-XVI",
    ]
    for t in test:
        print(f"'{t}' -> {p.score_lead(t)}")
