from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

OUTPUT_DIR = Path("output")
TEMPLATE_DIR = Path("templates")

API_URL = "https://api.openchargemap.io/v3/poi/"
PARAMS = {
    "output": "json",
    "countrycode": "GB",
    "maxresults": 50,
}

HEADERS = {
    # Helps some APIs/proxies behave nicely
    "User-Agent": "uk-ev-site-builder/0.1 (+https://example.com)"
}


def fetch_chargers():
    print("Fetching chargers from OpenChargeMap…")
    r = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=30)
    print(f"HTTP status: {r.status_code}")
    r.raise_for_status()

    data = r.json()
    if not isinstance(data, list):
        raise ValueError(f"Expected a list from API, got: {type(data)}")

    print(f"Received {len(data)} charger locations.")
    return data


def build_page(chargers):
    print("Rendering HTML from template…")

    if not TEMPLATE_DIR.exists():
        raise FileNotFoundError("Missing templates folder. Create 'templates/'.")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("chargers.html")

    html = template.render(chargers=chargers)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"Wrote: {out_path.resolve()}")


def main():
    try:
        chargers = fetch_chargers()
        build_page(chargers)
        print("DONE ✅")
    except Exception as e:
        print("FAILED ❌")
        print(f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()