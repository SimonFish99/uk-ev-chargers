import json
import os
import re
import shutil
from datetime import date
from jinja2 import Environment, FileSystemLoader, select_autoescape

INPUT_FILE = "data/towns_filtered.json"
OUTPUT_DIR = "site/uk"
BASE_URL = "https://plugmap.co.uk"
ADSENSE_PUB = "pub-3057384336950554"

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html"]),
)
env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)


def slugify(name: str) -> str:
    slug = name.lower()
    slug = slug.replace("&", "and")
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def map_center(chargers):
    valid = [
        (c["AddressInfo"]["Latitude"], c["AddressInfo"]["Longitude"])
        for c in chargers
        if c.get("AddressInfo", {}).get("Latitude") and c.get("AddressInfo", {}).get("Longitude")
    ]
    if valid:
        return sum(v[0] for v in valid) / len(valid), sum(v[1] for v in valid) / len(valid)
    return 54.5, -3.0


def compute_centroids(towns):
    centroids = {}
    for town, chargers in towns.items():
        valid = [
            (c["AddressInfo"]["Latitude"], c["AddressInfo"]["Longitude"])
            for c in chargers
            if c.get("AddressInfo", {}).get("Latitude") and c.get("AddressInfo", {}).get("Longitude")
        ]
        if valid:
            centroids[town] = (
                sum(v[0] for v in valid) / len(valid),
                sum(v[1] for v in valid) / len(valid),
            )
    return centroids


def get_nearby_towns(town, centroids, n=4):
    if town not in centroids:
        return []
    lat, lng = centroids[town]
    distances = [
        (((lat - olat) ** 2 + (lng - olng) ** 2) ** 0.5, other)
        for other, (olat, olng) in centroids.items()
        if other != town
    ]
    distances.sort()
    return [{"name": t, "slug": slugify(t)} for _, t in distances[:n]]


def town_stats(chargers):
    def max_kw(c):
        return max(((conn.get("PowerKW") or 0) for conn in (c.get("Connections") or [])), default=0)

    rapid = sum(1 for c in chargers if max_kw(c) >= 50)
    fast = sum(1 for c in chargers if 7 <= max_kw(c) < 50)
    slow = len(chargers) - rapid - fast
    return {"total": len(chargers), "rapid": rapid, "fast": fast, "slow": slow}


def augment_charger(c):
    """Add precomputed _speed and _conn_names to each charger dict."""
    connections = c.get("Connections") or []
    max_kw = max(((conn.get("PowerKW") or 0) for conn in connections), default=0)
    conn_names = list(dict.fromkeys(
        conn["ConnectionType"]["Title"]
        for conn in connections
        if conn.get("ConnectionType", {}).get("Title")
    ))
    speed = "rapid" if max_kw >= 50 else ("fast" if max_kw >= 7 else "slow")
    return {**c, "_speed": speed, "_conn_names": conn_names, "_max_kw": max_kw}


SPEED_RANK = {"rapid": 0, "fast": 1, "slow": 2}

_UNKNOWN_OPS = {"", "(unknown operator)", "unknown", "no operator", "private individual"}


def charger_speed(c):
    max_kw = max(((conn.get("PowerKW") or 0) for conn in (c.get("Connections") or [])), default=0)
    return "rapid" if max_kw >= 50 else ("fast" if max_kw >= 7 else "slow")


def _plural(n):
    return "" if n == 1 else "s"


def _join_list(items):
    items = list(items)
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def town_facts(chargers):
    """Aggregate facts used for the intro copy and FAQ."""
    from collections import Counter
    ops = Counter()
    max_kw = 0
    for c in chargers:
        title = (c.get("OperatorInfo") or {}).get("Title") or ""
        if title.strip().lower() not in _UNKNOWN_OPS:
            ops[title.strip()] += 1
        for conn in (c.get("Connections") or []):
            kw = conn.get("PowerKW") or 0
            if kw > max_kw:
                max_kw = kw
    connectors = sorted({
        conn["ConnectionType"]["Title"]
        for c in chargers for conn in (c.get("Connections") or [])
        if conn.get("ConnectionType", {}).get("Title")
    })
    return {
        "top_operators": [o for o, _ in ops.most_common(3)],
        "operator_count": len(ops),
        "max_kw": int(max_kw) if max_kw == int(max_kw) else max_kw,
        "connectors": connectors,
    }


def build_intro(town, stats, facts):
    """Short, factual intro paragraph (no filler)."""
    total = stats["total"]
    parts = [f"{town} has {total} public EV charging point{_plural(total)}"]
    mix = []
    if stats["rapid"]:
        mix.append(f"{stats['rapid']} rapid (50kW+)")
    if stats["fast"]:
        mix.append(f"{stats['fast']} fast (7–50kW)")
    if mix:
        parts.append(", including " + _join_list(mix) + f" charger{_plural(stats['rapid'] + stats['fast'])}")
    intro = "".join(parts) + "."
    if facts["top_operators"]:
        intro += " Networks operating here include " + _join_list(facts["top_operators"]) + "."
    intro += (" Browse every location on the map and list below — each shows its connector types, "
              "charging speed and operator, with one-tap directions to navigate straight there.")
    return intro


def build_faqs(town, stats, facts):
    total, rapid, fast = stats["total"], stats["rapid"], stats["fast"]
    faqs = []
    faqs.append((
        f"How many EV charging points are there in {town}?",
        f"There are {total} public EV charging point{_plural(total)} in {town}: "
        f"{rapid} rapid (50kW+), {fast} fast (7–50kW) and {stats['slow']} standard (under 7kW).",
    ))
    if rapid:
        faqs.append((
            f"Where can I find rapid EV chargers in {town}?",
            f"{town} has {rapid} rapid charging point{_plural(rapid)} rated at 50kW or above "
            f"(the fastest is {facts['max_kw']}kW). They're labelled “Rapid”, listed first on this page "
            f"and pinned on the map above so you can head straight to the quickest option.",
        ))
    else:
        faqs.append((
            f"Are there rapid chargers in {town}?",
            f"There are no rapid (50kW+) chargers listed in {town} right now — the fastest available is "
            f"{facts['max_kw']}kW. For rapid charging, try one of the nearby towns listed further down this page.",
        ))
    if facts["top_operators"]:
        faqs.append((
            f"Which charging networks operate in {town}?",
            f"Charge points in {town} are run by networks including {_join_list(facts['top_operators'])}. "
            f"You'll need the relevant operator's app or a contactless card to start a session at most sites.",
        ))
    faqs.append((
        f"Are the EV chargers in {town} free to use?",
        "Most public charge points require payment — usually via the operator's app, a contactless card or "
        "an RFID tag. Pricing varies by network and charging speed, so check the operator's app or the signage "
        "at the location for current tariffs.",
    ))
    return faqs


def build_faq_jsonld(faqs):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faqs
        ],
    }, ensure_ascii=False)


def build_map_data(chargers):
    items = []
    for c in chargers:
        addr = c.get("AddressInfo", {})
        lat, lng = addr.get("Latitude"), addr.get("Longitude")
        if not (lat and lng):
            continue
        connectors = [
            f"{conn['ConnectionType']['Title']}"
            + (f" · {conn['PowerKW']}kW" if conn.get("PowerKW") else "")
            for conn in (c.get("Connections") or [])
            if conn.get("ConnectionType", {}).get("Title")
        ]
        items.append({
            "lat": lat, "lng": lng,
            "title": addr.get("Title", ""),
            "address": addr.get("AddressLine1", ""),
            "connectors": connectors,
            "speed": charger_speed(c),
        })
    return json.dumps(items, ensure_ascii=False)


def build_jsonld(town, chargers, base_url, slug):
    items = []
    for i, charger in enumerate(chargers, 1):
        addr = charger.get("AddressInfo", {})
        lat, lng = addr.get("Latitude"), addr.get("Longitude")
        station = {
            "@type": "EvChargingStation",
            "name": addr.get("Title", ""),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": addr.get("AddressLine1", ""),
                "addressLocality": addr.get("Town", town),
                "postalCode": addr.get("Postcode", ""),
                "addressCountry": "GB",
            },
        }
        if lat and lng:
            station["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng}
            station["hasMap"] = f"https://www.google.com/maps?q={lat},{lng}"
        features = [
            {"@type": "LocationFeatureSpecification", "name": c["ConnectionType"]["Title"], "value": True}
            for c in (charger.get("Connections") or [])
            if c.get("ConnectionType", {}).get("Title")
        ]
        if features:
            station["amenityFeature"] = features
        items.append({"@type": "ListItem", "position": i, "item": station})
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"EV Chargers in {town}",
        "description": f"Public EV charging stations in {town}, UK",
        "url": f"{base_url}/uk/{slug}/",
        "numberOfItems": len(chargers),
        "itemListElement": items,
    }, ensure_ascii=False)


# ── Region assignment (towns -> UK regions by coordinates) ──────────
_NI_BBOX = (-8.2, 54.0, -5.3, 55.4)  # GB regions file excludes Northern Ireland


def load_regions():
    with open("data/uk_regions.json", encoding="utf-8") as f:
        data = json.load(f)
    regions = []
    for r in data["regions"]:
        pts = [p for ring in r["rings"] for p in ring]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        regions.append({
            "name": r["name"], "rings": r["rings"],
            "bbox": (min(xs), min(ys), max(xs), max(ys)),
        })
    return regions


def _in_ring(lat, lng, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def region_for(lat, lng, regions):
    for reg in regions:
        x0, y0, x1, y1 = reg["bbox"]
        if not (x0 <= lng <= x1 and y0 <= lat <= y1):
            continue
        if any(_in_ring(lat, lng, ring) for ring in reg["rings"]):
            return reg["name"]
    if _NI_BBOX[0] <= lng <= _NI_BBOX[2] and _NI_BBOX[1] <= lat <= _NI_BBOX[3]:
        return "Northern Ireland"
    # Fallback: nearest region by vertex distance (islands / coastal edge cases)
    best, best_d = None, 1e18
    for reg in regions:
        for ring in reg["rings"]:
            for x, y in ring:
                d = (x - lng) ** 2 + (y - lat) ** 2
                if d < best_d:
                    best_d, best = d, reg["name"]
    return best


def assign_regions(towns, centroids, regions):
    out = {}
    for town in towns:
        c = centroids.get(town)
        out[town] = region_for(c[0], c[1], regions) if c else None
    return out


def generate_region_pages(town_region, towns):
    template = env.get_template("region.html")
    by_region = {}
    for town, region in town_region.items():
        if region:
            by_region.setdefault(region, []).append(town)
    for region, names in by_region.items():
        rslug = slugify(region)
        town_list = sorted(
            ({"name": t, "slug": slugify(t), "count": len(towns[t])} for t in names),
            key=lambda x: x["name"].lower(),
        )
        total_chargers = sum(t["count"] for t in town_list)
        os.makedirs(os.path.join("site/uk/region", rslug), exist_ok=True)
        html = template.render(
            region=region, slug=rslug, base_url=BASE_URL,
            towns=town_list, total_towns=len(town_list), total_chargers=total_chargers,
            build_date=date.today().strftime("%B %Y"),
        )
        with open(os.path.join("site/uk/region", rslug, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
    print("Generated", len(by_region), "region pages")
    return by_region


def load_towns():
    """Load towns, merging case/whitespace-duplicate names and de-duping chargers by ID."""
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Group variants that differ only by case/whitespace (they collide on slug)
    groups = {}
    for name, chargers in raw.items():
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue
        groups.setdefault(name.lower(), []).append((name, chargers))
    towns = {}
    for variants in groups.values():
        # Display name = variant with most chargers, tie-break alphabetically
        variants.sort(key=lambda v: (-len(v[1]), v[0]))
        display = variants[0][0]
        seen, merged = set(), []
        for _, chargers in variants:
            for c in chargers:
                cid = c.get("ID")
                if cid is not None and cid in seen:
                    continue
                seen.add(cid)
                merged.append(c)
        towns[display] = merged
    return towns


def generate_pages(towns, centroids, town_region):
    template = env.get_template("town.html")
    # Wipe and regenerate so towns that drop out of the data leave no orphan pages
    if os.path.isdir(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for town, chargers in towns.items():
        slug = slugify(town)
        os.makedirs(os.path.join(OUTPUT_DIR, slug), exist_ok=True)

        # Rapid chargers first (most valuable to a hurried driver), then by power desc
        augmented = sorted(
            (augment_charger(c) for c in chargers),
            key=lambda c: (SPEED_RANK[c["_speed"]], -c["_max_kw"]),
        )
        connector_types = sorted(set(
            name for c in augmented for name in c["_conn_names"]
        ))
        center_lat, center_lng = map_center(chargers)
        stats = town_stats(chargers)
        facts = town_facts(chargers)
        faqs = build_faqs(town, stats, facts)

        region = town_region.get(town)
        html = template.render(
            town=town,
            chargers=augmented,
            slug=slug,
            region=region,
            region_slug=slugify(region) if region else "",
            base_url=BASE_URL,
            center_lat=center_lat,
            center_lng=center_lng,
            map_data=build_map_data(chargers),
            jsonld=build_jsonld(town, chargers, BASE_URL, slug),
            stats=stats,
            intro=build_intro(town, stats, facts),
            faqs=faqs,
            faq_jsonld=build_faq_jsonld(faqs),
            build_date=date.today().strftime("%B %Y"),
            nearby=get_nearby_towns(town, centroids, n=8),
            connector_types=connector_types,
            town_json=json.dumps(town, ensure_ascii=False),
            slug_json=json.dumps(slug, ensure_ascii=False),
        )
        with open(os.path.join(OUTPUT_DIR, slug, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
    print("Generated", len(towns), "town pages")


def generate_homepage(towns, centroids, by_region):
    template = env.get_template("home.html")
    # Alphabetical order
    town_list = [
        {"name": town, "slug": slugify(town), "count": len(chargers)}
        for town, chargers in sorted(towns.items(), key=lambda x: x[0].lower())
    ]
    total_chargers = sum(t["count"] for t in town_list)
    # Browse-by-region links (most towns first)
    region_list = sorted(
        ({"name": r, "slug": slugify(r), "town_count": len(names),
          "charger_count": sum(len(towns[t]) for t in names)}
         for r, names in by_region.items()),
        key=lambda r: -r["town_count"],
    )
    # Centroid data for client-side nearby/map features
    towns_json = json.dumps([
        {
            "name": t["name"],
            "slug": t["slug"],
            "count": t["count"],
            "lat": centroids.get(t["name"], (None, None))[0],
            "lng": centroids.get(t["name"], (None, None))[1],
        }
        for t in town_list
    ], ensure_ascii=False)
    html = template.render(
        towns=town_list,
        regions=region_list,
        base_url=BASE_URL,
        total_towns=len(town_list),
        total_chargers=total_chargers,
        towns_json=towns_json,
        jsonld=json.dumps({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "PlugMap",
            "description": "Find public EV charging stations across the UK.",
            "url": BASE_URL,
        }, ensure_ascii=False),
    )
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated homepage")


def generate_about(total_towns, total_chargers):
    template = env.get_template("about.html")
    os.makedirs("site/about", exist_ok=True)
    html = template.render(base_url=BASE_URL, total_towns=total_towns, total_chargers=total_chargers)
    with open("site/about/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated about page")


def generate_contact():
    template = env.get_template("contact.html")
    os.makedirs("site/contact", exist_ok=True)
    html = template.render(base_url=BASE_URL)
    with open("site/contact/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated contact page")


def generate_privacy():
    template = env.get_template("privacy.html")
    os.makedirs("site/privacy", exist_ok=True)
    html = template.render(base_url=BASE_URL)
    with open("site/privacy/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated privacy page")


def generate_robots():
    with open("site/robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
    print("Generated robots.txt")


def generate_ads_txt():
    with open("site/ads.txt", "w", encoding="utf-8") as f:
        f.write(f"google.com, {ADSENSE_PUB}, DIRECT, f08c47fec0942fa0\n")
    print("Generated ads.txt")


def generate_sitemap(towns, by_region):
    today = date.today().isoformat()
    urls = [
        (f"{BASE_URL}/", "1.0", "weekly"),
        (f"{BASE_URL}/about/", "0.6", "monthly"),
        (f"{BASE_URL}/contact/", "0.4", "yearly"),
        (f"{BASE_URL}/privacy/", "0.3", "yearly"),
    ]
    for region in by_region.keys():
        urls.append((f"{BASE_URL}/uk/region/{slugify(region)}/", "0.7", "weekly"))
    for town in towns.keys():
        urls.append((f"{BASE_URL}/uk/{slugify(town)}/", "0.8", "monthly"))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, priority, changefreq in urls:
        lines += [
            "  <url>",
            f"    <loc>{url}</loc>",
            f"    <lastmod>{today}</lastmod>",
            f"    <changefreq>{changefreq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")
    with open("site/sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Generated sitemap.xml")


def main():
    towns = load_towns()
    centroids = compute_centroids(towns)
    regions = load_regions()
    town_region = assign_regions(towns, centroids, regions)
    total_chargers = sum(len(c) for c in towns.values())
    generate_pages(towns, centroids, town_region)
    by_region = generate_region_pages(town_region, towns)
    generate_homepage(towns, centroids, by_region)
    generate_sitemap(towns, by_region)
    generate_robots()
    generate_ads_txt()
    generate_about(len(towns), total_chargers)
    generate_contact()
    generate_privacy()


if __name__ == "__main__":
    main()
