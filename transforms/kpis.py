import pandas as pd


def compute_kpis(routing_today, routing_yesterday, fulfillment, inventory_health):
    """
    Compute top-level KPIs with deltas comparing today vs yesterday.
    """
    # --- Today ---
    total_orders = len(routing_today)
    sla_risk_count = int(routing_today["sla_risk"].sum())
    avg_fulfillment_cost = routing_today["ship_cost"].mean()
    channel_mix = routing_today.groupby("channel")["order_id"].count()

    # --- Yesterday (for deltas) ---
    yesterday_orders = len(routing_yesterday) if routing_yesterday is not None else 0
    yesterday_sla_risk = int(routing_yesterday["sla_risk"].sum()) if routing_yesterday is not None and len(routing_yesterday) > 0 else 0
    yesterday_avg_cost = routing_yesterday["ship_cost"].mean() if routing_yesterday is not None and len(routing_yesterday) > 0 else None

    # Deltas (percentage change vs yesterday)
    if yesterday_orders > 0:
        orders_delta_pct = round((total_orders - yesterday_orders) / yesterday_orders * 100, 1)
    else:
        orders_delta_pct = None

    if yesterday_sla_risk > 0:
        sla_risk_delta_pct = round((sla_risk_count - yesterday_sla_risk) / yesterday_sla_risk * 100, 1)
    elif sla_risk_count > 0:
        sla_risk_delta_pct = 100.0  # went from 0 to something
    else:
        sla_risk_delta_pct = 0.0  # both zero

    if pd.notna(avg_fulfillment_cost) and pd.notna(yesterday_avg_cost) and yesterday_avg_cost > 0:
        cost_delta_pct = round((avg_fulfillment_cost - yesterday_avg_cost) / yesterday_avg_cost * 100, 1)
    else:
        cost_delta_pct = None

    # --- Historical fulfillment ---
    on_time_rate = fulfillment["delivered_on_time"].mean() * 100 if len(fulfillment) > 0 else 0
    avg_ship_cost = fulfillment["ship_cost"].mean() if len(fulfillment) > 0 else 0
    avg_transit_days = fulfillment["transit_days"].mean() if len(fulfillment) > 0 else 0

    # Weekly on-time trend
    ff = fulfillment.copy()
    ff["ship_date"] = pd.to_datetime(ff["ship_date"])
    ff["week"] = ff["ship_date"].dt.isocalendar().week.astype(int)
    weekly_on_time = ff.groupby("week")["delivered_on_time"].mean().reset_index()
    weekly_on_time.columns = ["week", "on_time_pct"]
    weekly_on_time["on_time_pct"] = (weekly_on_time["on_time_pct"] * 100).round(1)

    # Daily order volume trend
    daily_orders = ff.groupby("ship_date").size().reset_index(name="orders")

    # --- Inventory health ---
    critical_count = (inventory_health["health_status"] == "Critical").sum()
    low_stock_count = (inventory_health["health_status"] == "Low Stock").sum()
    overstock_count = (inventory_health["health_status"] == "Overstock").sum()

    return {
        "total_orders_today": total_orders,
        "orders_delta_pct": orders_delta_pct,
        "sla_risk_orders": sla_risk_count,
        "sla_risk_pct": round(sla_risk_count / total_orders * 100, 1) if total_orders > 0 else 0,
        "sla_risk_delta_pct": sla_risk_delta_pct,
        "avg_fulfillment_cost": round(avg_fulfillment_cost, 2) if pd.notna(avg_fulfillment_cost) else 0,
        "cost_delta_pct": cost_delta_pct,
        "historical_on_time_pct": round(on_time_rate, 1),
        "historical_avg_ship_cost": round(avg_ship_cost, 2),
        "historical_avg_transit_days": round(avg_transit_days, 1),
        "weekly_on_time": weekly_on_time,
        "daily_orders": daily_orders,
        "critical_stock_alerts": int(critical_count),
        "low_stock_alerts": int(low_stock_count),
        "overstock_alerts": int(overstock_count),
        "channel_mix": channel_mix.to_dict(),
    }
