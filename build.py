from pathlib import Path
import os

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from dotenv import load_dotenv

OUTPUT_DIR = Path("output")
TEMPLATE_DIR = Path("templates")

API_URL = "https://api.openchargemap.io/v3/poi/"
PARAMS = {
    "output": "json",
    "countrycode": "GB",
    "maxresults": 50,
}

def build_headers() -> dict:
    """
    OpenChargeMap often requires an API key now.
    We read it from .env as OCM_API_KEY.
    """
    headers = {
        "User-Agent": "uk-ev-site-builder/0.1",
        "Accept": "application/json",
    }

    api_key = os.getenv("OCM_API_KEY", "").strip()
    if api_key:
        # Common header name used by OCM
        headers["X-API-Key"] = api_key

    return headers


def fetch_chargers():
    print("Fetching chargers from OpenChargeMap…")

    headers = build_headers()
    has_key = "X-API-Key" in headers
    print(f"API key provided: {'YES' if has_key else 'NO'}")

    r = requests.get(API_URL, params=PARAMS, headers=headers, timeout=30)
    print(f"HTTP status: {r.status_code}")

    if r.status_code == 403:
        # Friendly message for the exact problem you hit
        raise RuntimeError(
            "OpenChargeMap returned 403 Forbidden.\n\n"
            "This usually means an API key is required.\n"
            "Fix:\n"
            "1) Get a free OpenChargeMap API key.\n"
            "2) Put it in a .env file as: OCM_API_KEY=your_key\n"
            "3) Re-run: python build.py\n"
        )

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
    # Load .env into environment variables
    load_dotenv()

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