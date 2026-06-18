"""
check_domains.py
Checks domain availability via public RDAP servers (no API key required).
Scores candidates on SEO value for a UK EV charger directory and prints
the top 3 available options.
"""

import time
import requests

# --- Candidates -----------------------------------------------------------
# Roughly ordered by gut SEO feel; scoring below is what actually ranks them.
CANDIDATES = [
    # Exact keyword match
    "evchargermap.co.uk",
    "evchargemap.co.uk",
    "ukevchargers.co.uk",
    "ukevcharger.co.uk",
    "evchargersuk.co.uk",
    "evchargeruk.co.uk",
    "evchargerlocator.co.uk",
    "evchargelocator.co.uk",
    "evchargefinder.co.uk",
    "publicevchargers.co.uk",
    "publicevcharger.co.uk",
    "chargepointmap.co.uk",
    "chargepointfinder.co.uk",
    "findanev.co.uk",
    "findevcharger.co.uk",
    # Brand name (PlugMap) across TLDs
    "plugmap.co.uk",
    "plugmap.uk",
    "plugmap.com",
    # .uk variants
    "evchargermap.uk",
    "ukevchargers.uk",
    "evchargersuk.uk",
    "evchargemap.uk",
    # .com variants (global trust, weaker UK signal)
    "evchargermap.com",
    "ukevchargers.com",
    "evchargemap.com",
]

# --- SEO scoring ----------------------------------------------------------
# Points awarded for keywords present in the domain name (before the TLD).
KEYWORD_WEIGHTS = {
    "ev":       4,  # core search term
    "charger":  4,  # core search term
    "charge":   3,
    "electric": 2,
    "uk":       3,  # geographic relevance signal
    "map":      2,  # strong intent word
    "plug":     2,
    "public":   1,
    "find":     1,
    "locator":  1,
    "point":    1,
}

# .co.uk beats .uk beats .com for UK local SEO
TLD_WEIGHTS = {
    ".co.uk": 4,
    ".uk":    3,
    ".com":   1,
}


def seo_score(domain: str) -> int:
    # Strip TLD, normalise separators
    name = domain.lower()
    for tld in sorted(TLD_WEIGHTS, key=len, reverse=True):
        if name.endswith(tld):
            name = name[: -len(tld)]
            break
    name_clean = name.replace("-", " ")

    score = 0
    matched_keywords = []
    for kw, weight in KEYWORD_WEIGHTS.items():
        if kw in name_clean:
            score += weight
            matched_keywords.append(kw)

    for tld, weight in TLD_WEIGHTS.items():
        if domain.endswith(tld):
            score += weight
            break

    # Brevity bonus: shorter = more memorable and easier to type
    if len(name) <= 12:
        score += 2
    elif len(name) <= 18:
        score += 1

    return score, matched_keywords


# --- RDAP availability check ----------------------------------------------

def rdap_url(domain: str) -> str:
    if domain.endswith((".co.uk", ".uk", ".org.uk", ".me.uk")):
        return f"https://rdap.nominet.uk/uk/domain/{domain}"
    if domain.endswith(".com"):
        return f"https://rdap.verisign.com/com/v1/domain/{domain}"
    if domain.endswith(".net"):
        return f"https://rdap.verisign.com/net/v1/domain/{domain}"
    return f"https://rdap.org/domain/{domain}"


def is_available(domain: str) -> bool | None:
    """True = available, False = taken, None = couldn't determine."""
    try:
        r = requests.get(
            rdap_url(domain),
            timeout=8,
            headers={"User-Agent": "domain-availability-checker/1.0"},
        )
        if r.status_code == 200:
            return False   # RDAP returned a record → registered
        if r.status_code == 404:
            return True    # Not found in registry → available
        return None        # Unexpected status
    except requests.RequestException:
        return None


# --- Main -----------------------------------------------------------------

def main():
    print("Checking domain availability via RDAP (no API key needed)...\n")
    print(f"  {'Status':<16} {'Domain':<32} {'SEO score'}")
    print(f"  {'-'*16} {'-'*32} {'-'*9}")

    results = []
    for domain in CANDIDATES:
        available = is_available(domain)
        score, keywords = seo_score(domain)
        results.append((domain, available, score, keywords))

        if available is True:
            tag = "[AVAILABLE]"
        elif available is False:
            tag = "[taken]"
        else:
            tag = "[unknown]"

        print(f"  {tag:<16} {domain:<32} {score}")
        time.sleep(0.35)   # polite pacing for public RDAP servers

    # Filter to confirmed available, rank by SEO score
    available_results = [
        (d, sc, kws) for d, av, sc, kws in results if av is True
    ]
    available_results.sort(key=lambda x: -x[1])

    print()
    print("=" * 60)
    print("TOP 3 AVAILABLE DOMAINS (ranked by SEO score)\n")

    if not available_results:
        print("  No domains confirmed available.")
        print("  RDAP can be unreliable — try again or check manually.")
        return

    explanations = {
        "ev":       "exact EV keyword",
        "charger":  "exact charger keyword",
        "charge":   "charge keyword",
        "electric": "electric keyword",
        "uk":       "UK geographic signal",
        "map":      "intent word (map)",
        "plug":     "plug keyword",
        "public":   "public keyword",
        "find":     "intent word (find)",
        "locator":  "intent word (locator)",
        "point":    "chargepoint keyword",
    }

    for rank, (domain, score, keywords) in enumerate(available_results[:3], 1):
        reasons = ", ".join(explanations[k] for k in keywords if k in explanations)
        tld_note = ".co.uk (strongest UK local signal)" if domain.endswith(".co.uk") else (
                   ".uk (good UK signal)" if domain.endswith(".uk") else ".com (global trust)")
        print(f"  {rank}. {domain}")
        print(f"     Score : {score}")
        print(f"     TLD   : {tld_note}")
        print(f"     Why   : {reasons or 'brand name'}")
        print()


if __name__ == "__main__":
    main()
