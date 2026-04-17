import pandas as pd


def check_inventory_health(inventory, items):
    """
    Flag SKUs that are below safety stock at any node.

    Health rule:
      - If available < safety_stock → "Low Stock"
      - If available < safety_stock * 0.5 → "Critical"
      - If available > safety_stock * 3 → "Overstock"
      - Otherwise → "Healthy"
    """
    df = inventory.merge(items[["sku", "name", "category"]], on="sku", how="left")

    def classify(row):
        if row["available"] < row["safety_stock"] * 0.5:
            return "Critical"
        elif row["available"] < row["safety_stock"]:
            return "Low Stock"
        elif row["available"] > row["safety_stock"] * 3:
            return "Overstock"
        return "Healthy"

    df["health_status"] = df.apply(classify, axis=1)
    df["stock_ratio"] = (df["available"] / df["safety_stock"]).round(2)

    return df[["sku", "name", "category", "node", "on_hand", "available",
               "reserved_orders", "safety_stock", "stock_ratio", "health_status"]]
