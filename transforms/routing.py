import pandas as pd


def _explain_decision(best, sla_safe_count, total_candidate_nodes, promised_days, is_risk, risk_reason):
    """Generate a plain-English explanation for a routing decision."""
    node = best["node"] if best is not None else None

    if is_risk and node is None:
        return "No fulfillment node has enough inventory to fill this order."

    if is_risk and risk_reason and risk_reason.startswith("Best transit"):
        return (
            f"Recommended {node} as the fastest fallback, "
            f"but transit still exceeds the delivery promise."
        )

    # Normal SLA-safe pick
    service = best["service_level"]

    if sla_safe_count == 1:
        return (
            f"Recommended {node} because it is the only node with inventory "
            f"that can meet the delivery promise via {service}."
        )

    return (
        f"Recommended {node} because it has inventory available, meets the "
        f"delivery promise via {service}, and is the lowest-cost SLA-safe option."
    )


def route_orders(orders, inventory, carrier_rates, items):
    """
    For each order, find candidate fulfillment nodes and recommend the best one.

    Routing rule:
      1. Keep nodes that have enough available inventory for the order qty.
      2. Keep nodes that can meet the promised delivery window.
      3. Among remaining candidates, pick the lowest-cost option.
      4. If no node meets the promise window, flag as SLA risk and show best fallback.
    """
    results = []

    for _, order in orders.iterrows():
        sku = order["sku"]
        qty = order["qty"]
        dest_region = order["destination_region"]
        promised_days = order["promised_days"]

        # Get unit cost for total cost calc
        item_row = items.loc[items["sku"] == sku]
        unit_cost = item_row["unit_cost"].iloc[0] if len(item_row) > 0 else 0

        # Find nodes with enough inventory
        inv_candidates = inventory[
            (inventory["sku"] == sku) & (inventory["available"] >= qty)
        ]

        if inv_candidates.empty:
            total_nodes = len(inventory[inventory["sku"] == sku])
            explanation = _explain_decision(
                None, 0, total_nodes, promised_days,
                is_risk=True, risk_reason="No node has sufficient inventory",
            )
            results.append({
                "order_id": order["order_id"],
                "sku": sku,
                "qty": qty,
                "channel": order["channel"],
                "destination_region": dest_region,
                "promised_days": promised_days,
                "recommended_node": None,
                "service_level": None,
                "ship_cost": None,
                "transit_days": None,
                "total_fulfillment_cost": None,
                "sla_risk": True,
                "risk_reason": "No node has sufficient inventory",
                "explanation": explanation,
            })
            continue

        # For each candidate node, find the cheapest shipping option
        candidates = []
        for _, inv in inv_candidates.iterrows():
            node = inv["node"]
            rates = carrier_rates[
                (carrier_rates["origin_node"] == node)
                & (carrier_rates["destination_region"] == dest_region)
            ].copy()

            if rates.empty:
                continue

            for _, rate in rates.iterrows():
                total_cost = rate["cost"] + (unit_cost * qty)
                candidates.append({
                    "order_id": order["order_id"],
                    "sku": sku,
                    "qty": qty,
                    "channel": order["channel"],
                    "destination_region": dest_region,
                    "promised_days": promised_days,
                    "node": node,
                    "available_qty": inv["available"],
                    "service_level": rate["service_level"],
                    "ship_cost": rate["cost"],
                    "transit_days": rate["days"],
                    "total_fulfillment_cost": round(total_cost, 2),
                    "meets_sla": rate["days"] <= promised_days,
                })

        if not candidates:
            explanation = _explain_decision(
                None, 0, len(inv_candidates), promised_days,
                is_risk=True, risk_reason="No carrier rate available",
            )
            results.append({
                "order_id": order["order_id"],
                "sku": sku,
                "qty": qty,
                "channel": order["channel"],
                "destination_region": dest_region,
                "promised_days": promised_days,
                "recommended_node": None,
                "service_level": None,
                "ship_cost": None,
                "transit_days": None,
                "total_fulfillment_cost": None,
                "sla_risk": True,
                "risk_reason": "No carrier rate available",
                "explanation": explanation,
            })
            continue

        cdf = pd.DataFrame(candidates)

        # Prefer options that meet the SLA
        sla_safe = cdf[cdf["meets_sla"]]
        total_candidate_nodes = cdf["node"].nunique()

        if not sla_safe.empty:
            best = sla_safe.sort_values("total_fulfillment_cost").iloc[0]
            sla_safe_nodes = sla_safe["node"].nunique()
            explanation = _explain_decision(
                best, sla_safe_nodes, total_candidate_nodes, promised_days,
                is_risk=False, risk_reason=None,
            )
            results.append({
                "order_id": best["order_id"],
                "sku": best["sku"],
                "qty": best["qty"],
                "channel": best["channel"],
                "destination_region": best["destination_region"],
                "promised_days": best["promised_days"],
                "recommended_node": best["node"],
                "service_level": best["service_level"],
                "ship_cost": best["ship_cost"],
                "transit_days": best["transit_days"],
                "total_fulfillment_cost": best["total_fulfillment_cost"],
                "sla_risk": False,
                "risk_reason": None,
                "explanation": explanation,
            })
        else:
            # No option meets SLA - pick the fastest fallback
            best = cdf.sort_values("transit_days").iloc[0]
            risk_reason = f"Best transit {int(best['transit_days'])}d exceeds promise {int(best['promised_days'])}d"
            explanation = _explain_decision(
                best, 0, total_candidate_nodes, promised_days,
                is_risk=True, risk_reason=risk_reason,
            )
            results.append({
                "order_id": best["order_id"],
                "sku": best["sku"],
                "qty": best["qty"],
                "channel": best["channel"],
                "destination_region": best["destination_region"],
                "promised_days": best["promised_days"],
                "recommended_node": best["node"],
                "service_level": best["service_level"],
                "ship_cost": best["ship_cost"],
                "transit_days": best["transit_days"],
                "total_fulfillment_cost": best["total_fulfillment_cost"],
                "sla_risk": True,
                "risk_reason": risk_reason,
                "explanation": explanation,
            })

    return pd.DataFrame(results)
