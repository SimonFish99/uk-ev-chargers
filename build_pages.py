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
    return 54.5, -3.0  # UK geographic centre fallback


def load_towns():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Strip whitespace from town names that crept in from the source data
    return {k.strip(): v for k, v in raw.items() if k.strip()}


def generate_pages(towns):
    template = env.get_template("town.html")

    for town, chargers in towns.items():
        slug = slugify(town)
        town_dir = os.path.join(OUTPUT_DIR, slug)
        os.makedirs(town_dir, exist_ok=True)

        center_lat, center_lng = map_center(chargers)

        # Pre-serialise map data in Python so the template stays clean
        map_data = json.dumps([
            {
                "lat": c["AddressInfo"]["Latitude"],
                "lng": c["AddressInfo"]["Longitude"],
                "title": c["AddressInfo"].get("Title", ""),
                "address": c["AddressInfo"].get("AddressLine1", ""),
            }
            for c in chargers
            if c.get("AddressInfo", {}).get("Latitude") and c.get("AddressInfo", {}).get("Longitude")
        ])

        html = template.render(
            town=town,
            chargers=chargers,
            slug=slug,
            base_url=BASE_URL,
            center_lat=center_lat,
            center_lng=center_lng,
            map_data=map_data,
        )

        with open(os.path.join(town_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    print("Generated", len(towns), "town pages")


def generate_homepage(towns):
    template = env.get_template("home.html")
    town_list = [{"name": town, "slug": slugify(town)} for town in towns.keys()]
    html = template.render(towns=town_list, base_url=BASE_URL)
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
    generate_pages(towns)
    generate_homepage(towns)
    generate_sitemap(towns)
    generate_robots()


if __name__ == "__main__":
    main()
