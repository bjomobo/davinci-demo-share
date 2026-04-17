import pandas as pd


# Node-to-region mapping
NODE_REGION = {
    "NODE_NJ": "Northeast", "NODE_GA": "Southeast", "NODE_TX": "South Central",
    "NODE_IL": "Midwest", "NODE_NV": "West",
}

# Feature weights
WEIGHTS = {
    "cost": 0.35,
    "sla_buffer": 0.25,
    "inventory_health": 0.25,
    "demand_pressure": 0.10,
    "on_time_history": 0.05,
}


def ai_route_orders(orders, inventory, carrier_rates, items, fulfillment):
    """
    AI-powered routing using a weighted scoring model that considers:
    - SLA buffer (more slack = less risk of late delivery)
    - Shipping cost (lower is better)
    - Inventory health (avoid depleting low-stock nodes)
    - Historical on-time performance per node
    - Demand pressure (preserve inventory at high-demand nodes)
    """
    # Precompute features
    on_time_by_node = fulfillment.groupby("node")["delivered_on_time"].mean().to_dict()
    demand_by_region = orders.groupby("destination_region")["qty"].sum().to_dict()
    max_demand = max(demand_by_region.values()) if demand_by_region else 1

    results = []

    for _, order in orders.iterrows():
        sku = order["sku"]
        qty = order["qty"]
        dest_region = order["destination_region"]
        promised_days = order["promised_days"]

        item_row = items.loc[items["sku"] == sku]
        unit_cost = item_row["unit_cost"].iloc[0] if len(item_row) > 0 else 0

        inv_candidates = inventory[
            (inventory["sku"] == sku) & (inventory["available"] >= qty)
        ]

        if inv_candidates.empty:
            results.append(_no_inventory_result(order))
            continue

        # Gather all SLA-safe options
        scored = []
        all_costs = []

        for _, inv in inv_candidates.iterrows():
            node = inv["node"]
            rates = carrier_rates[
                (carrier_rates["origin_node"] == node) &
                (carrier_rates["destination_region"] == dest_region)
            ]
            for _, rate in rates.iterrows():
                if rate["days"] <= promised_days:
                    all_costs.append(rate["cost"])

        if not all_costs:
            # No SLA-safe option exists
            results.append(_no_sla_option_result(order, inv_candidates, carrier_rates, dest_region, unit_cost))
            continue

        min_cost = min(all_costs)
        max_cost = max(all_costs)
        cost_range = max(max_cost - min_cost, 0.01)

        for _, inv in inv_candidates.iterrows():
            node = inv["node"]
            stock_ratio = inv["available"] / max(inv["safety_stock"], 1)
            rates = carrier_rates[
                (carrier_rates["origin_node"] == node) &
                (carrier_rates["destination_region"] == dest_region)
            ]

            for _, rate in rates.iterrows():
                if rate["days"] > promised_days:
                    continue

                total_cost = rate["cost"] + (unit_cost * qty)

                # Feature scores (0.0 - 1.0)
                sla_slack = (promised_days - rate["days"]) / max(promised_days, 1)
                sla_score = min(1.0, 0.5 + sla_slack)

                cost_score = 1.0 - (rate["cost"] - min_cost) / cost_range

                inv_score = min(1.0, stock_ratio / 3.0)

                hist_score = on_time_by_node.get(node, 0.75)

                src_region = NODE_REGION.get(node, "")
                src_demand = demand_by_region.get(src_region, 0)
                demand_score = 1.0 - (src_demand / max_demand)

                ai_score = (
                    WEIGHTS["sla_buffer"] * sla_score +
                    WEIGHTS["cost"] * cost_score +
                    WEIGHTS["inventory_health"] * inv_score +
                    WEIGHTS["on_time_history"] * hist_score +
                    WEIGHTS["demand_pressure"] * demand_score
                )

                scored.append({
                    "node": node,
                    "service_level": rate["service_level"],
                    "ship_cost": rate["cost"],
                    "transit_days": int(rate["days"]),
                    "total_cost": round(total_cost, 2),
                    "available_qty": int(inv["available"]),
                    "stock_ratio": round(stock_ratio, 2),
                    "sla_score": round(sla_score, 3),
                    "cost_score": round(cost_score, 3),
                    "inventory_score": round(inv_score, 3),
                    "performance_score": round(hist_score, 3),
                    "demand_score": round(demand_score, 3),
                    "ai_score": round(ai_score, 3),
                })

        if not scored:
            results.append(_no_inventory_result(order))
            continue

        scored_df = pd.DataFrame(scored).sort_values("ai_score", ascending=False)
        top = scored_df.iloc[0]

        reason = _build_reason(top, order)
        confidence = _score_to_confidence(top["ai_score"])

        results.append({
            "order_id": order["order_id"],
            "sku": sku,
            "qty": qty,
            "channel": order["channel"],
            "destination_region": dest_region,
            "promised_days": promised_days,
            "ai_node": top["node"],
            "ai_service": top["service_level"],
            "ai_ship_cost": top["ship_cost"],
            "ai_transit_days": top["transit_days"],
            "ai_total_cost": top["total_cost"],
            "ai_score": top["ai_score"],
            "ai_confidence": confidence,
            "ai_reason": reason,
            "sla_risk": False,
            "_scored_candidates": scored_df.to_dict("records"),
        })

    return pd.DataFrame(results)


def _score_to_confidence(score):
    """Convert raw AI score to a confidence label."""
    if score >= 0.75:
        return "High"
    elif score >= 0.55:
        return "Medium"
    return "Low"


def _build_reason(top, order):
    """Generate a plain-English explanation for the AI recommendation."""
    drivers = []
    if top["inventory_score"] >= 0.5:
        drivers.append("healthy inventory at source")
    elif top["inventory_score"] < 0.3:
        drivers.append("limited alternatives with sufficient stock")
    if top["performance_score"] >= 0.82:
        drivers.append("strong historical on-time performance")
    if top["cost_score"] >= 0.8:
        drivers.append("competitive shipping cost")
    if top["sla_score"] >= 0.7:
        drivers.append("comfortable SLA buffer")
    if top["demand_score"] >= 0.6:
        drivers.append("preserves inventory at busier nodes, ships from low demand regions")

    if not drivers:
        return f"AI recommends {top['node']} as the best balanced option across all factors."

    return f"AI recommends {top['node']} based on: {', '.join(drivers)}."


def _no_inventory_result(order):
    return {
        "order_id": order["order_id"],
        "sku": order["sku"],
        "qty": order["qty"],
        "channel": order["channel"],
        "destination_region": order["destination_region"],
        "promised_days": order["promised_days"],
        "ai_node": None,
        "ai_service": None,
        "ai_ship_cost": None,
        "ai_transit_days": None,
        "ai_total_cost": None,
        "ai_score": None,
        "ai_confidence": None,
        "ai_reason": "No node has sufficient inventory.",
        "sla_risk": True,
        "_scored_candidates": [],
    }


def _no_sla_option_result(order, inv_candidates, carrier_rates, dest_region, unit_cost):
    """When inventory exists but no service meets SLA, pick fastest fallback."""
    best = None
    for _, inv in inv_candidates.iterrows():
        node = inv["node"]
        rates = carrier_rates[
            (carrier_rates["origin_node"] == node) &
            (carrier_rates["destination_region"] == dest_region)
        ]
        for _, rate in rates.iterrows():
            total = rate["cost"] + (unit_cost * order["qty"])
            if best is None or rate["days"] < best["transit"]:
                best = {"node": node, "service": rate["service_level"],
                        "cost": rate["cost"], "transit": int(rate["days"]), "total": round(total, 2)}

    if best:
        return {
            "order_id": order["order_id"],
            "sku": order["sku"],
            "qty": order["qty"],
            "channel": order["channel"],
            "destination_region": order["destination_region"],
            "promised_days": order["promised_days"],
            "ai_node": best["node"],
            "ai_service": best["service"],
            "ai_ship_cost": best["cost"],
            "ai_transit_days": best["transit"],
            "ai_total_cost": best["total"],
            "ai_score": None,
            "ai_confidence": "Low",
            "ai_reason": f"No option meets SLA. Recommended {best['node']} as the fastest fallback.",
            "sla_risk": True,
            "_scored_candidates": [],
        }

    return _no_inventory_result(order)
