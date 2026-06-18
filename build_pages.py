import json
import os
import re
from datetime import date
from jinja2 import Environment, FileSystemLoader, select_autoescape

INPUT_FILE = "data/towns_filtered.json"
OUTPUT_DIR = "site/uk"
BASE_URL = "https://uk-ev-chargers.pages.dev"

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


def load_towns():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k.strip(): v for k, v in raw.items() if k.strip()}


def generate_pages(towns, centroids):
    template = env.get_template("town.html")
    for town, chargers in towns.items():
        slug = slugify(town)
        os.makedirs(os.path.join(OUTPUT_DIR, slug), exist_ok=True)

        augmented = [augment_charger(c) for c in chargers]
        connector_types = sorted(set(
            name for c in augmented for name in c["_conn_names"]
        ))

        html = template.render(
            town=town,
            chargers=augmented,
            slug=slug,
            base_url=BASE_URL,
            center_lat=map_center(chargers)[0],
            center_lng=map_center(chargers)[1],
            map_data=build_map_data(chargers),
            jsonld=build_jsonld(town, chargers, BASE_URL, slug),
            stats=town_stats(chargers),
            nearby=get_nearby_towns(town, centroids),
            connector_types=connector_types,
            town_json=json.dumps(town, ensure_ascii=False),
            slug_json=json.dumps(slug, ensure_ascii=False),
        )
        with open(os.path.join(OUTPUT_DIR, slug, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
    print("Generated", len(towns), "town pages")


def generate_homepage(towns, centroids):
    template = env.get_template("home.html")
    # Alphabetical order
    town_list = [
        {"name": town, "slug": slugify(town), "count": len(chargers)}
        for town, chargers in sorted(towns.items(), key=lambda x: x[0].lower())
    ]
    total_chargers = sum(t["count"] for t in town_list)
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


def generate_sitemap(towns):
    today = date.today().isoformat()
    urls = [(f"{BASE_URL}/", "1.0", "weekly")]
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


def generate_robots():
    with open("site/robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
    print("Generated robots.txt")


def main():
    towns = load_towns()
    centroids = compute_centroids(towns)
    generate_pages(towns, centroids)
    generate_homepage(towns, centroids)
    generate_sitemap(towns)
    generate_robots()


if __name__ == "__main__":
    main()
