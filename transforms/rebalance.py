import pandas as pd


def recommend_rebalances(inventory, orders, items):
    """
    Compare regional demand (from open orders) against available inventory
    and suggest transfers from overstocked to understocked nodes.

    Rebalance rule:
      1. Aggregate demand per SKU per node region.
      2. Identify nodes where available < safety_stock (understocked).
      3. Identify nodes where available > safety_stock * 2.5 (overstocked).
      4. For each understocked SKU-node, find an overstocked source and suggest a transfer.
    """
    inv = inventory.merge(items[["sku", "name"]], on="sku", how="left")

    # Compute demand per SKU from open orders
    demand_by_sku = orders.groupby("sku")["qty"].sum().reset_index()
    demand_by_sku.columns = ["sku", "total_demand"]

    inv = inv.merge(demand_by_sku, on="sku", how="left")
    inv["total_demand"] = inv["total_demand"].fillna(0).astype(int)

    # Classify each node-SKU
    inv["is_understocked"] = inv["available"] < inv["safety_stock"]
    inv["is_overstocked"] = inv["available"] > inv["safety_stock"] * 2.5

    understocked = inv[inv["is_understocked"]].copy()
    overstocked = inv[inv["is_overstocked"]].copy()

    recommendations = []

    for _, low in understocked.iterrows():
        sku = low["sku"]
        dest_node = low["node"]
        deficit = low["safety_stock"] - low["available"]

        # Find overstocked source for this SKU
        sources = overstocked[overstocked["sku"] == sku].copy()
        if sources.empty:
            # Fall back: any node with surplus above safety_stock * 1.5
            sources = inv[
                (inv["sku"] == sku)
                & (inv["node"] != dest_node)
                & (inv["available"] > inv["safety_stock"] * 1.5)
            ].copy()

        if sources.empty:
            continue

        # Pick the source with the most excess
        sources["excess"] = sources["available"] - sources["safety_stock"]
        best_source = sources.sort_values("excess", ascending=False).iloc[0]

        transfer_qty = min(deficit, int(best_source["excess"] * 0.5))
        if transfer_qty <= 0:
            continue

        recommendations.append({
            "sku": sku,
            "sku_name": low["name"],
            "from_node": best_source["node"],
            "to_node": dest_node,
            "transfer_qty": transfer_qty,
            "source_available": int(best_source["available"]),
            "source_safety_stock": int(best_source["safety_stock"]),
            "dest_available": int(low["available"]),
            "dest_safety_stock": int(low["safety_stock"]),
            "priority": "High" if low["available"] < low["safety_stock"] * 0.5 else "Medium",
        })

    return pd.DataFrame(recommendations)
