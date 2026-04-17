"""
Generate 2 weeks of mock data for the Davinci Micro-Fulfillment demo.
Produces realistic daily variation in orders, fulfillment, and inventory.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).parent / "data"

# ── Constants ────────────────────────────────────────────────────────────────
START_DATE = date(2026, 3, 22)  # Sunday
END_DATE = date(2026, 4, 4)    # Saturday (2 full weeks)
TODAY = END_DATE

NODES = ["NODE_NJ", "NODE_GA", "NODE_TX", "NODE_IL", "NODE_NV"]
REGIONS = ["Northeast", "Southeast", "South Central", "Midwest", "West"]
ZIP3S = {"Northeast": "100", "Southeast": "303", "South Central": "750", "Midwest": "606", "West": "891"}
CHANNELS = ["Amazon", "Walmart", "Target"]
SERVICE_LEVELS = ["Standard", "Expedited", "Next-Day"]

SKUS = [
    ("SKU-1001", "Wireless Earbuds Pro", "Electronics", 18.50, 0.3),
    ("SKU-1002", "Bluetooth Speaker Mini", "Electronics", 22.00, 1.2),
    ("SKU-1003", "USB-C Charging Cable 6ft", "Electronics", 3.25, 0.2),
    ("SKU-1004", "Phone Case Universal", "Accessories", 4.10, 0.15),
    ("SKU-1005", "Screen Protector 2-Pack", "Accessories", 2.80, 0.1),
    ("SKU-1006", "Laptop Stand Adjustable", "Office", 15.75, 3.5),
    ("SKU-1007", "Wireless Mouse Ergonomic", "Office", 12.00, 0.5),
    ("SKU-1008", "Mechanical Keyboard Compact", "Office", 28.00, 2.1),
    ("SKU-1009", "Webcam HD 1080p", "Electronics", 16.50, 0.6),
    ("SKU-1010", "LED Desk Lamp", "Office", 11.25, 2.8),
    ("SKU-1011", "Portable Charger 10000mAh", "Electronics", 14.00, 0.5),
    ("SKU-1012", "HDMI Cable 10ft", "Electronics", 5.50, 0.4),
    ("SKU-1013", "Notebook 3-Pack Lined", "Office Supplies", 3.00, 1.0),
    ("SKU-1014", "Gel Pen Set 12ct", "Office Supplies", 4.50, 0.6),
    ("SKU-1015", "Desk Organizer Bamboo", "Office", 9.80, 1.8),
    ("SKU-1016", "Water Bottle Insulated 32oz", "Lifestyle", 8.25, 0.9),
    ("SKU-1017", "Fitness Tracker Band", "Electronics", 19.00, 0.2),
    ("SKU-1018", "Sunglasses Polarized", "Accessories", 7.50, 0.15),
    ("SKU-1019", "Travel Backpack 30L", "Lifestyle", 21.00, 2.0),
    ("SKU-1020", "Yoga Mat Premium", "Lifestyle", 13.50, 3.0),
    ("SKU-1021", "Wireless Charger Pad", "Electronics", 10.00, 0.4),
    ("SKU-1022", "Smart Plug 2-Pack", "Electronics", 11.50, 0.5),
    ("SKU-1023", "Reusable Tote Bag Set", "Lifestyle", 5.00, 0.6),
    ("SKU-1024", "Stainless Steel Tumbler", "Lifestyle", 7.00, 0.7),
    ("SKU-1025", "Portable Bluetooth Keyboard", "Electronics", 16.00, 0.8),
]

SKU_IDS = [s[0] for s in SKUS]

# Safety stock by SKU (consistent with original data)
SAFETY_STOCK = {
    "SKU-1001": 30, "SKU-1002": 20, "SKU-1003": 50, "SKU-1004": 25, "SKU-1005": 40,
    "SKU-1006": 15, "SKU-1007": 20, "SKU-1008": 15, "SKU-1009": 20, "SKU-1010": 15,
    "SKU-1011": 25, "SKU-1012": 40, "SKU-1013": 30, "SKU-1014": 20, "SKU-1015": 10,
    "SKU-1016": 25, "SKU-1017": 20, "SKU-1018": 30, "SKU-1019": 10, "SKU-1020": 10,
    "SKU-1021": 20, "SKU-1022": 15, "SKU-1023": 35, "SKU-1024": 25, "SKU-1025": 15,
}

# Base inventory levels per node (some intentionally low)
# Format: {node: {sku: base_available}}
BASE_INVENTORY = {}
for node in NODES:
    BASE_INVENTORY[node] = {}
    for sku in SKU_IDS:
        ss = SAFETY_STOCK[sku]
        if node == "NODE_NV":
            # NV is chronically understocked on many items
            BASE_INVENTORY[node][sku] = random.randint(int(ss * 0.1), int(ss * 1.5))
        elif node == "NODE_IL":
            # IL has a few gaps
            BASE_INVENTORY[node][sku] = random.randint(int(ss * 0.3), int(ss * 2.5))
        else:
            # Other nodes generally well-stocked
            BASE_INVENTORY[node][sku] = random.randint(int(ss * 1.0), int(ss * 4.0))

# Make specific SKUs scarce network-wide (for SLA risk tension)
for node in NODES:
    BASE_INVENTORY[node]["SKU-1009"] = random.randint(0, 4)
    BASE_INVENTORY[node]["SKU-1020"] = random.randint(0, 5)


# ── Carrier rates (unchanged) ───────────────────────────────────────────────
RATE_DATA = {
    # (origin_node, dest_region): {service_level: (cost, days)}
}
# Base rates: closer regions are cheaper/faster
NODE_REGION = {"NODE_NJ": "Northeast", "NODE_GA": "Southeast", "NODE_TX": "South Central",
               "NODE_IL": "Midwest", "NODE_NV": "West"}

REGION_DISTANCE = {
    ("Northeast", "Northeast"): 0, ("Northeast", "Southeast"): 1, ("Northeast", "South Central"): 2,
    ("Northeast", "Midwest"): 1, ("Northeast", "West"): 3,
    ("Southeast", "Northeast"): 1, ("Southeast", "Southeast"): 0, ("Southeast", "South Central"): 1,
    ("Southeast", "Midwest"): 1, ("Southeast", "West"): 2,
    ("South Central", "Northeast"): 2, ("South Central", "Southeast"): 1, ("South Central", "South Central"): 0,
    ("South Central", "Midwest"): 1, ("South Central", "West"): 1,
    ("Midwest", "Northeast"): 1, ("Midwest", "Southeast"): 1, ("Midwest", "South Central"): 1,
    ("Midwest", "Midwest"): 0, ("Midwest", "West"): 2,
    ("West", "Northeast"): 3, ("West", "Southeast"): 2, ("West", "South Central"): 1,
    ("West", "Midwest"): 2, ("West", "West"): 0,
}


def build_carrier_rates():
    rows = []
    for node in NODES:
        origin_region = NODE_REGION[node]
        for dest_region in REGIONS:
            dist = REGION_DISTANCE[(origin_region, dest_region)]
            # Standard
            std_days = 3 + dist
            std_cost = round(4.00 + dist * 1.75 + random.uniform(-0.5, 0.5), 2)
            # Expedited
            exp_days = max(1, 2 + (dist // 2))
            exp_cost = round(8.00 + dist * 2.25 + random.uniform(-0.5, 0.5), 2)
            # Next-Day
            nd_days = 1
            nd_cost = round(13.50 + dist * 2.75 + random.uniform(-0.5, 0.5), 2)

            rows.append([node, dest_region, "Standard", std_cost, std_days])
            rows.append([node, dest_region, "Expedited", exp_cost, exp_days])
            rows.append([node, dest_region, "Next-Day", nd_cost, nd_days])
    return rows


# ── Generate orders across 2 weeks ──────────────────────────────────────────
def generate_orders():
    rows = []
    order_num = 3001
    # Start with a base volume and drift by ~5% each day
    base_volume = 42
    d = START_DATE
    while d <= END_DATE:
        # Drift base by -5% to +5%
        drift = random.uniform(-0.05, 0.05)
        base_volume = max(30, min(55, int(base_volume * (1 + drift))))
        # Small weekend dip (~10-15% less, not 50%)
        dow = d.weekday()
        if dow == 5:  # Saturday
            num_orders = max(28, int(base_volume * random.uniform(0.85, 0.92)))
        elif dow == 6:  # Sunday
            num_orders = max(26, int(base_volume * random.uniform(0.82, 0.90)))
        else:
            num_orders = base_volume

        for _ in range(num_orders):
            channel = random.choice(CHANNELS)
            # Weight channels: Amazon heavier
            if random.random() < 0.45:
                channel = "Amazon"
            elif random.random() < 0.55:
                channel = "Walmart"
            else:
                channel = "Target"

            dest_region = random.choice(REGIONS)
            zip3 = ZIP3S[dest_region]
            sku = random.choice(SKU_IDS)
            qty = random.choices([1, 2, 3, 4, 5, 8, 10], weights=[30, 25, 15, 10, 8, 2, 1])[0]

            # Promise days: tighter promises more common on Amazon
            if channel == "Amazon":
                promised_days = random.choices([1, 2, 3], weights=[25, 50, 25])[0]
            elif channel == "Walmart":
                promised_days = random.choices([1, 2, 3], weights=[10, 40, 50])[0]
            else:
                promised_days = random.choices([1, 2, 3], weights=[15, 45, 40])[0]

            # Inject some tension: scarce SKUs with tight SLAs
            # Skip injection on today/yesterday — we add controlled ones below
            if d not in (TODAY, TODAY - timedelta(days=1)):
                if sku in ("SKU-1009", "SKU-1020") and random.random() < 0.4:
                    qty = random.randint(4, 8)
                    promised_days = 1

            rows.append([
                f"ORD-{order_num}", channel, d.isoformat(), zip3, sku, qty, promised_days
            ])
            order_num += 1

        # Add controlled SLA-risk orders for yesterday (4) and today (3)
        yesterday = TODAY - timedelta(days=1)
        if d == yesterday:
            # 4 SLA-risk orders yesterday
            for scarce_sku in ["SKU-1009", "SKU-1009", "SKU-1020", "SKU-1020"]:
                region = random.choice(REGIONS)
                rows.append([
                    f"ORD-{order_num}", "Amazon", d.isoformat(),
                    ZIP3S[region], scarce_sku, 10, 1
                ])
                order_num += 1
        elif d == TODAY:
            # 3 SLA-risk orders today (-25% vs yesterday)
            for scarce_sku in ["SKU-1009", "SKU-1020", "SKU-1009"]:
                region = random.choice(REGIONS)
                rows.append([
                    f"ORD-{order_num}", "Amazon", d.isoformat(),
                    ZIP3S[region], scarce_sku, 10, 1
                ])
                order_num += 1

        d += timedelta(days=1)
    return rows


# ── Generate fulfillment events (for completed orders, not today) ────────────
def generate_fulfillment(orders):
    rows = []
    for order in orders:
        order_id, channel, order_date_str, zip3, sku, qty, promised_days = order
        order_date = date.fromisoformat(order_date_str)

        # Don't generate fulfillment for today's orders (they're pending)
        if order_date >= TODAY:
            continue

        # Pick a fulfillment node (weighted toward closer nodes)
        dest_region = [r for r, z in ZIP3S.items() if z == zip3][0]
        # Prefer local node but sometimes use others
        local_nodes = [n for n in NODES if NODE_REGION[n] == dest_region]
        if local_nodes and random.random() < 0.5:
            node = local_nodes[0]
        else:
            node = random.choice(NODES)

        origin_region = NODE_REGION[node]
        dist = REGION_DISTANCE[(origin_region, dest_region)]

        # Pick service level based on promise
        if promised_days == 1:
            service = "Next-Day"
            base_transit = 1
            base_cost = 13.50 + dist * 2.75
        elif promised_days == 2:
            service = random.choice(["Expedited", "Next-Day"])
            base_transit = max(1, 2 + (dist // 2)) if service == "Expedited" else 1
            base_cost = (8.00 + dist * 2.25) if service == "Expedited" else (13.50 + dist * 2.75)
        else:
            service = random.choice(["Standard", "Expedited"])
            base_transit = (3 + dist) if service == "Standard" else max(1, 2 + (dist // 2))
            base_cost = (4.00 + dist * 1.75) if service == "Standard" else (8.00 + dist * 2.25)

        ship_cost = round(base_cost + random.uniform(-1.0, 1.0), 2)
        transit_days = base_transit + (1 if random.random() < 0.12 else 0)  # 12% chance of delay
        delivered_on_time = transit_days <= promised_days

        ship_date = order_date  # assume ships same day

        rows.append([
            order_id, node, ship_date.isoformat(), ship_cost, transit_days,
            promised_days, str(delivered_on_time).lower()
        ])

    return rows


# ── Generate inventory (point-in-time snapshot as of today) ──────────────────
def generate_inventory():
    rows = []
    for node in NODES:
        for sku in SKU_IDS:
            base = BASE_INVENTORY[node][sku]
            # Add some daily noise
            available = max(0, base + random.randint(-3, 3))
            reserved = random.randint(1, max(2, int(available * 0.1)))
            on_hand = available + reserved
            safety_stock = SAFETY_STOCK[sku]
            rows.append([sku, node, on_hand, available, reserved, safety_stock])
    return rows


# ── Write everything ─────────────────────────────────────────────────────────
def main():
    # nodes.csv (unchanged)
    with open(DATA_DIR / "nodes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node", "name", "region", "city", "state", "zip3", "lat", "lon"])
        w.writerow(["NODE_NJ", "Davinci NJ Hub", "Northeast", "Edison", "NJ", "088", 40.5187, -74.4121])
        w.writerow(["NODE_GA", "Davinci GA Hub", "Southeast", "Atlanta", "GA", "303", 33.7490, -84.3880])
        w.writerow(["NODE_TX", "Davinci TX Hub", "South Central", "Dallas", "TX", "750", 32.7767, -96.7970])
        w.writerow(["NODE_IL", "Davinci IL Hub", "Midwest", "Chicago", "IL", "606", 41.8781, -87.6298])
        w.writerow(["NODE_NV", "Davinci NV Hub", "West", "Las Vegas", "NV", "891", 36.1699, -115.1398])

    # netsuite_items.csv (unchanged)
    with open(DATA_DIR / "netsuite_items.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sku", "name", "category", "unit_cost", "weight_lbs", "is_active"])
        for s in SKUS:
            w.writerow([s[0], s[1], s[2], s[3], s[4], "true"])

    # carrier_rates.csv
    with open(DATA_DIR / "carrier_rates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["origin_node", "destination_region", "service_level", "cost", "days"])
        for row in build_carrier_rates():
            w.writerow(row)

    # channel_orders.csv (2 weeks)
    orders = generate_orders()
    with open(DATA_DIR / "channel_orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "channel", "order_date", "customer_zip3", "sku", "qty", "promised_days"])
        for row in orders:
            w.writerow(row)

    # fulfillment_events.csv (all days except today)
    fulfillment = generate_fulfillment(orders)
    with open(DATA_DIR / "fulfillment_events.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "node", "ship_date", "ship_cost", "transit_days", "promised_days", "delivered_on_time"])
        for row in fulfillment:
            w.writerow(row)

    # netsuite_inventory.csv
    inventory = generate_inventory()
    with open(DATA_DIR / "netsuite_inventory.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sku", "node", "on_hand", "available", "reserved_orders", "safety_stock"])
        for row in inventory:
            w.writerow(row)

    # Print summary
    today_orders = [o for o in orders if o[2] == TODAY.isoformat()]
    print(f"Generated data from {START_DATE} to {END_DATE} ({(END_DATE - START_DATE).days + 1} days)")
    print(f"  Total orders:       {len(orders)}")
    print(f"  Today's orders:     {len(today_orders)}")
    print(f"  Fulfillment events: {len(fulfillment)}")
    print(f"  Inventory rows:     {len(inventory)}")


if __name__ == "__main__":
    main()
