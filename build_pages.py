import json
import os
from jinja2 import Environment, FileSystemLoader

INPUT_FILE = "data/towns_filtered.json"
OUTPUT_DIR = "site/uk"

env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("town.html")


def load_towns():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_pages(towns):

    for town, chargers in towns.items():

        town_slug = town.lower().replace(" ", "-")

        town_dir = os.path.join(OUTPUT_DIR, town_slug)
        os.makedirs(town_dir, exist_ok=True)

        html = template.render(
            town=town,
            chargers=chargers
        )

        output_file = os.path.join(town_dir, "index.html")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

    print("Generated", len(towns), "town pages")

def generate_homepage(towns):

    template = env.get_template("home.html")

    town_list = []

    for town in towns.keys():
        slug = town.lower().replace(" ", "-")

        town_list.append({
            "name": town,
            "slug": slug
        })

    html = template.render(towns=town_list)

    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Generated homepage")

def generate_sitemap(towns):

    base_url = "https://uk-ev-chargers.pages.dev"

    urls = []

    urls.append(f"{base_url}/")

    for town in towns.keys():
        slug = town.lower().replace(" ", "-")
        urls.append(f"{base_url}/uk/{slug}/")

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>']
    sitemap.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for url in urls:
        sitemap.append("  <url>")
        sitemap.append(f"    <loc>{url}</loc>")
        sitemap.append("  </url>")

    sitemap.append("</urlset>")

    with open("site/sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap))

    print("Generated sitemap.xml")

def main():

    towns = load_towns()

    generate_pages(towns)

    generate_homepage(towns)

    generate_sitemap(towns)

if __name__ == "__main__":
    main()