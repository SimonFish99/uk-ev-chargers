import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path

# Load API key from .env
load_dotenv()
API_KEY = os.getenv("OCM_API_KEY")

# API endpoint
API_URL = "https://api.openchargemap.io/v3/poi"

# Where we save the downloaded data
DATA_FILE = Path("data/chargers.json")

# API parameters
PARAMS = {
    "output": "json",
    "countrycode": "GB",
    "maxresults": 20000,
    "key": API_KEY
}


def fetch_chargers():
    print("Requesting charger data from OpenChargeMap...")

    response = requests.get(API_URL, params=PARAMS)

    print("HTTP status:", response.status_code)

    response.raise_for_status()

    chargers = response.json()

    print(f"Downloaded {len(chargers)} charger locations")

    return chargers


def save_data(chargers):
    DATA_FILE.parent.mkdir(exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(chargers, f, indent=2)

    print(f"Saved data to {DATA_FILE}")


def main():
    chargers = fetch_chargers()
    save_data(chargers)


if __name__ == "__main__":
    main()