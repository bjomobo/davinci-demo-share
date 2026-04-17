"""
Davinci Micro-Fulfillment Control Center — Data Pipeline

Loads mock CSVs, runs routing / health / rebalance logic,
and prints a summary. Outputs are stored in memory for the Streamlit app.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from transforms.load_data import load_all
from transforms.routing import route_orders
from transforms.inventory_health import check_inventory_health
from transforms.rebalance import recommend_rebalances
from transforms.kpis import compute_kpis


def run():
    # --- Load ---
    data = load_all()
    print("[OK] Loaded 6 data files\n")

    # --- Route today's orders ---
    routing = route_orders(
        data["orders_today"], data["inventory"], data["carrier_rates"], data["items"]
    )
    print(f"[OK] Routed {len(routing)} orders (today)")
    print(f"  SLA-safe: {(~routing['sla_risk']).sum()}  |  SLA-risk: {routing['sla_risk'].sum()}\n")

    # --- Inventory health ---
    health = check_inventory_health(data["inventory"], data["items"])
    critical = health[health["health_status"] == "Critical"]
    low = health[health["health_status"] == "Low Stock"]
    overstock = health[health["health_status"] == "Overstock"]
    print(f"[OK] Inventory health check across {len(health)} node-SKU combinations")
    print(f"  Critical: {len(critical)}  |  Low Stock: {len(low)}  |  Overstock: {len(overstock)}\n")

    # --- Rebalance recommendations ---
    rebalance = recommend_rebalances(data["inventory"], data["orders_today"], data["items"])
    print(f"[OK] Generated {len(rebalance)} rebalance recommendations")
    if not rebalance.empty:
        high_pri = (rebalance["priority"] == "High").sum()
        print(f"  High priority: {high_pri}  |  Medium: {len(rebalance) - high_pri}\n")

    # --- KPIs ---
    kpis = compute_kpis(routing, None, data["fulfillment"], health)
    print("[OK] KPI Summary")
    print(f"  Orders today:         {kpis['total_orders_today']}")
    print(f"  SLA risk:             {kpis['sla_risk_orders']} ({kpis['sla_risk_pct']}%)")
    print(f"  Avg fulfillment cost: ${kpis['avg_fulfillment_cost']}")
    print(f"  On-time (historical): {kpis['historical_on_time_pct']}%")
    print(f"  Critical stock:       {kpis['critical_stock_alerts']}")
    print(f"  Low stock:            {kpis['low_stock_alerts']}")
    print(f"  Overstock:            {kpis['overstock_alerts']}")
    print(f"  Channel mix:          {kpis['channel_mix']}")

    # --- Show some detail ---
    print("\n--- SLA Risk Orders ---")
    risk_orders = routing[routing["sla_risk"]]
    if not risk_orders.empty:
        print(risk_orders[["order_id", "sku", "channel", "destination_region",
                           "promised_days", "recommended_node", "transit_days",
                           "risk_reason"]].to_string(index=False))
    else:
        print("  None -- all orders can be fulfilled within SLA")

    print("\n--- Critical / Low Stock Alerts ---")
    alerts = health[health["health_status"].isin(["Critical", "Low Stock"])]
    if not alerts.empty:
        print(alerts[["sku", "name", "node", "available", "safety_stock",
                       "stock_ratio", "health_status"]].to_string(index=False))

    print("\n--- Top Rebalance Recommendations ---")
    if not rebalance.empty:
        print(rebalance[["sku", "sku_name", "from_node", "to_node",
                          "transfer_qty", "priority"]].to_string(index=False))

    return {
        "routing": routing,
        "health": health,
        "rebalance": rebalance,
        "kpis": kpis,
        "data": data,
    }


if __name__ == "__main__":
    run()
