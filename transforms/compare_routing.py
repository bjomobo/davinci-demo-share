import pandas as pd


def compare_rules_vs_ai(rules_routing, ai_routing, inventory):
    """
    Merge rules-based and AI routing results and compute deltas.
    """
    rules = rules_routing[["order_id", "sku", "qty", "channel", "destination_region",
                           "promised_days", "recommended_node", "service_level",
                           "ship_cost", "transit_days", "total_fulfillment_cost",
                           "sla_risk", "explanation"]].copy()
    rules.columns = ["order_id", "sku", "qty", "channel", "destination_region",
                     "promised_days", "rules_node", "rules_service",
                     "rules_ship_cost", "rules_transit", "rules_total_cost",
                     "rules_sla_risk", "rules_explanation"]

    ai = ai_routing[["order_id", "sku", "ai_node", "ai_service",
                     "ai_ship_cost", "ai_transit_days", "ai_total_cost",
                     "ai_score", "ai_confidence", "ai_reason", "sla_risk",
                     "_scored_candidates"]].copy()
    ai.columns = ["order_id", "sku", "ai_node", "ai_service",
                  "ai_ship_cost", "ai_transit", "ai_total_cost",
                  "ai_score", "ai_confidence", "ai_reason", "ai_sla_risk",
                  "_scored_candidates"]

    merged = rules.merge(ai, on=["order_id", "sku"], how="left")

    # Compute comparison fields
    merged["same_node"] = merged["rules_node"] == merged["ai_node"]
    merged["cost_delta"] = (merged["ai_ship_cost"] - merged["rules_ship_cost"]).round(2)
    merged["transit_delta"] = (merged["ai_transit"] - merged["rules_transit"])

    # Compute stock ratio at chosen node for each approach
    inv_lookup = inventory.set_index(["sku", "node"])
    for prefix, node_col in [("rules", "rules_node"), ("ai", "ai_node")]:
        ratios = []
        for _, row in merged.iterrows():
            try:
                inv_row = inv_lookup.loc[(row["sku"], row[node_col])]
                ratios.append(round(inv_row["available"] / max(inv_row["safety_stock"], 1), 2))
            except (KeyError, TypeError):
                ratios.append(None)
        merged[f"{prefix}_source_stock_ratio"] = ratios

    return merged


def compute_ai_kpis(comparison):
    """Compute summary KPIs for the AI page."""
    total = len(comparison)
    different = (~comparison["same_node"]).sum()

    valid = comparison.dropna(subset=["rules_ship_cost", "ai_ship_cost"])

    # Averages
    rules_avg_ship = valid["rules_ship_cost"].mean() if len(valid) > 0 else 0
    ai_avg_ship = valid["ai_ship_cost"].mean() if len(valid) > 0 else 0
    rules_avg_transit = valid["rules_transit"].mean() if len(valid) > 0 else 0
    ai_avg_transit = valid["ai_transit"].mean() if len(valid) > 0 else 0

    # SLA risk
    rules_risk = comparison["rules_sla_risk"].sum()
    ai_risk = comparison["ai_sla_risk"].sum()

    # Inventory health at chosen nodes
    rules_avg_stock = comparison["rules_source_stock_ratio"].mean()
    ai_avg_stock = comparison["ai_source_stock_ratio"].mean()

    # Orders pulled away from critical nodes (stock ratio < 0.5)
    rules_from_critical = (comparison["rules_source_stock_ratio"] < 0.5).sum()
    ai_from_critical = (comparison["ai_source_stock_ratio"] < 0.5).sum()

    return {
        "total_scored": total,
        "different_recommendations": int(different),
        "same_recommendations": int(total - different),
        "pct_different": round(different / total * 100, 1) if total > 0 else 0,
        "rules_avg_ship": round(rules_avg_ship, 2),
        "ai_avg_ship": round(ai_avg_ship, 2),
        "rules_avg_transit": round(rules_avg_transit, 1),
        "ai_avg_transit": round(ai_avg_transit, 1),
        "rules_sla_risk": int(rules_risk),
        "ai_sla_risk": int(ai_risk),
        "rules_avg_stock_ratio": round(rules_avg_stock, 2) if pd.notna(rules_avg_stock) else 0,
        "ai_avg_stock_ratio": round(ai_avg_stock, 2) if pd.notna(ai_avg_stock) else 0,
        "rules_from_critical": int(rules_from_critical),
        "ai_from_critical": int(ai_from_critical),
    }
