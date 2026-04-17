import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TODAY = "2026-04-04"

# ZIP3 prefix -> region mapping (matches nodes.csv regions)
ZIP3_TO_REGION = {
    "088": "Northeast",
    "100": "Northeast",
    "303": "Southeast",
    "606": "Midwest",
    "750": "South Central",
    "891": "West",
}


def _load_local():
    """Load all CSV files from local data directory."""
    return {
        "nodes": pd.read_csv(DATA_DIR / "nodes.csv"),
        "items": pd.read_csv(DATA_DIR / "netsuite_items.csv"),
        "inventory": pd.read_csv(DATA_DIR / "netsuite_inventory.csv"),
        "carrier_rates": pd.read_csv(DATA_DIR / "carrier_rates.csv"),
        "orders": pd.read_csv(DATA_DIR / "channel_orders.csv"),
        "fulfillment": pd.read_csv(DATA_DIR / "fulfillment_events.csv"),
    }


def load_all():
    """Load all data from local CSV files."""
    data = _load_local()
    source = "Local CSV"

    print(f"Data loaded from: {source}")

    # Enrich orders with destination region
    data["orders"]["destination_region"] = (
        data["orders"]["customer_zip3"].astype(str).str.zfill(3).map(ZIP3_TO_REGION)
    )

    # Split orders into today vs historical
    orders_today = data["orders"][data["orders"]["order_date"] == TODAY].copy()
    orders_historical = data["orders"][data["orders"]["order_date"] < TODAY].copy()

    data["orders_today"] = orders_today
    data["orders_historical"] = orders_historical
    data["today"] = TODAY
    data["source"] = source

    return data
