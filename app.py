"""
Davinci Micro-Fulfillment Control Center
Interactive Streamlit dashboard with 4 screens.
"""

import streamlit as st
import plotly.express as px
import pandas as pd

from transforms.load_data import load_all
from transforms.routing import route_orders
from transforms.inventory_health import check_inventory_health
from transforms.rebalance import recommend_rebalances
from transforms.kpis import compute_kpis
from transforms.ai_routing import ai_route_orders
from transforms.compare_routing import compare_rules_vs_ai, compute_ai_kpis

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Davinci Micro-Fulfillment Control Center",
    page_icon="📦",
    layout="wide",
)

# ── Password gate ────────────────────────────────────────────────────────────
def _check_password():
    if st.session_state.get("authenticated"):
        return True
    st.markdown("## Davinci Micro-Fulfillment Demo")
    st.caption("Enter the demo password to continue.")
    pwd = st.text_input("Password", type="password", label_visibility="collapsed")
    if pwd == st.secrets.get("APP_PASSWORD", ""):
        st.session_state["authenticated"] = True
        st.rerun()
    elif pwd:
        st.error("Incorrect password")
    return False

if not _check_password():
    st.stop()

# ── Load & transform (cached) ───────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading data and running analytics pipeline...")
def load_pipeline():
    data = load_all()
    # Route today's orders
    routing = route_orders(data["orders_today"], data["inventory"], data["carrier_rates"], data["items"])
    # Route yesterday's orders for delta comparison
    yesterday = str(pd.to_datetime(data["today"]) - pd.Timedelta(days=1))[:10]
    orders_yesterday = data["orders"][data["orders"]["order_date"] == yesterday]
    routing_yesterday = route_orders(orders_yesterday, data["inventory"], data["carrier_rates"], data["items"]) if len(orders_yesterday) > 0 else None
    health = check_inventory_health(data["inventory"], data["items"])
    rebalance = recommend_rebalances(data["inventory"], data["orders_today"], data["items"])
    kpis = compute_kpis(routing, routing_yesterday, data["fulfillment"], health)
    # AI routing
    ai_routing = ai_route_orders(data["orders_today"], data["inventory"], data["carrier_rates"],
                                  data["items"], data["fulfillment"])
    comparison = compare_rules_vs_ai(routing, ai_routing, data["inventory"])
    ai_kpis = compute_ai_kpis(comparison)
    return data, routing, health, rebalance, kpis, ai_routing, comparison, ai_kpis

data, routing, health, rebalance, kpis, ai_routing, comparison, ai_kpis = load_pipeline()

# ── Sidebar navigation ──────────────────────────────────────────────────────
st.sidebar.title("Davinci Micro Fulfillment Analytics Control Center")
screen = st.sidebar.radio(
    "Navigate",
    ["Network Health Overview", "Order Routing", "Inventory Health by Node", "Rebalance Recommendations", "AI Routing Optimization"],
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<p style='color:#374151; font-weight:500; font-size:0.9rem; margin-top:0.5rem;'>"
    "Demo Built by uBIT Technologies</p>",
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — Network Health Overview
# ═══════════════════════════════════════════════════════════════════════════════
if screen == "Network Health Overview":
    st.title("Unified Network Health Overview")
    st.markdown("A unified view of fulfillment operations showing current order volume, historical delivery performance, and current inventory positioning")

    # --- Section 1: Today's Orders ---
    st.subheader("Today's Orders")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders Today", kpis["total_orders_today"],
              delta=f"{kpis['orders_delta_pct']:+.1f}% vs yesterday" if kpis["orders_delta_pct"] is not None else None)
    c2.metric("SLA Risk Orders", kpis["sla_risk_orders"],
              delta=f"{kpis['sla_risk_delta_pct']:+.1f}% vs yesterday", delta_color="inverse")
    c3.metric("Avg Shipping Cost", f"${kpis['avg_fulfillment_cost']}",
              delta=f"{kpis['cost_delta_pct']:+.1f}% vs yesterday" if kpis["cost_delta_pct"] is not None else None,
              delta_color="inverse")
    channel_df = pd.DataFrame(
        list(kpis["channel_mix"].items()), columns=["Channel", "Orders"]
    )
    c4.metric("Channels Active", len(channel_df))

    fig_ch = px.pie(channel_df, names="Channel", values="Orders",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    hole=0.4)
    fig_ch.update_traces(textinfo="label+percent", textposition="inside", textfont_size=15)
    fig_ch.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=400,
                         showlegend=False)
    st.plotly_chart(fig_ch, use_container_width=True)

    st.markdown("---")

    # --- Section 2: Historical Trends ---
    st.subheader("Historical Trends")
    h1, h2, h3 = st.columns(3)
    h1.metric("On-Time Delivery", f"{kpis['historical_on_time_pct']}%")
    h2.metric("Avg Shipping Cost", f"${kpis['historical_avg_ship_cost']}")
    h3.metric("Avg Transit Days", f"{kpis['historical_avg_transit_days']}")

    col_hist_left, col_hist_right = st.columns(2)

    with col_hist_left:
        st.markdown("**On-Time Delivery by Node**")
        ot = data["fulfillment"].copy()
        ot["delivered_on_time"] = ot["delivered_on_time"].astype(int)
        ot_by_node = ot.groupby("node")["delivered_on_time"].mean().reset_index()
        ot_by_node["on_time_pct"] = (ot_by_node["delivered_on_time"] * 100).round(1)

        def classify_ot(pct):
            if pct >= 80:
                return "Good (>=80%)"
            elif pct >= 70:
                return "Warning (70-80%)"
            else:
                return "Poor (<70%)"

        ot_by_node["performance"] = ot_by_node["on_time_pct"].apply(classify_ot)
        fig_ot = px.bar(ot_by_node, x="node", y="on_time_pct",
                        color="performance",
                        color_discrete_map={
                            "Good (>=80%)": "#22c55e",
                            "Warning (70-80%)": "#f59e0b",
                            "Poor (<70%)": "#ef4444",
                        },
                        category_orders={"performance": ["Good (>=80%)", "Warning (70-80%)", "Poor (<70%)"]},
                        labels={"on_time_pct": "On-Time %", "node": "Node", "performance": "Performance"})
        fig_ot.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300,
                             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_ot, use_container_width=True)

    with col_hist_right:
        st.markdown("**Daily Order Volume (Past 2 Weeks)**")
        daily = kpis["daily_orders"].copy()
        daily["ship_date"] = pd.to_datetime(daily["ship_date"])
        fig_daily = px.bar(daily, x="ship_date", y="orders",
                           labels={"ship_date": "Date", "orders": "Orders"},
                           color_discrete_sequence=["#3b82f6"])
        fig_daily.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300)
        st.plotly_chart(fig_daily, use_container_width=True)

    st.markdown("---")

    # --- Section 3: Inventory Positioning ---
    st.subheader("Inventory Positioning")
    st.caption("Current stock posture across nodes relative to safety-stock targets.")
    i1, i2, i3 = st.columns(3)
    i1.metric("Critical Stock Alerts", kpis["critical_stock_alerts"])
    i2.metric("Low Stock Alerts", kpis["low_stock_alerts"])
    i3.metric("Overstock Alerts", kpis["overstock_alerts"])

    # Health Status by Node (stacked bar) — replaces the SKU-level heatmap
    status_counts = health.groupby(["node", "health_status"]).size().reset_index(name="count")
    color_map = {"Critical": "#ef4444", "Low Stock": "#f59e0b", "Healthy": "#22c55e", "Overstock": "#3b82f6"}
    status_order = ["Critical", "Low Stock", "Healthy", "Overstock"]
    fig_health = px.bar(status_counts, x="node", y="count", color="health_status",
                        color_discrete_map=color_map,
                        category_orders={"health_status": status_order},
                        barmode="stack",
                        labels={"count": "SKU Count", "node": "Node", "health_status": "Status"})
    fig_health.update_layout(margin=dict(t=20, b=20), height=350, legend_title="Status",
                             legend_traceorder="reversed")
    st.plotly_chart(fig_health, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — Order Routing Simulator
# ═══════════════════════════════════════════════════════════════════════════════
elif screen == "Order Routing":
    st.title("Order Routing Simulator")
    st.markdown("Each order is evaluated through a routing algorithm that filters for nodes with sufficient inventory,  \nidentifies options that meet the delivery promise, and recommends the lowest-cost fulfillment option.")

    # --- Filters ---
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        channel_filter = st.multiselect("Channel", routing["channel"].unique(), default=list(routing["channel"].unique()))
    with filter_col2:
        region_filter = st.multiselect("Destination Region", routing["destination_region"].unique(), default=list(routing["destination_region"].unique()))
    with filter_col3:
        sla_filter = st.selectbox("SLA Status", ["All", "At Risk Only", "Safe Only"])

    filtered = routing[
        routing["channel"].isin(channel_filter) &
        routing["destination_region"].isin(region_filter)
    ]
    if sla_filter == "At Risk Only":
        filtered = filtered[filtered["sla_risk"]]
    elif sla_filter == "Safe Only":
        filtered = filtered[~filtered["sla_risk"]]

    # --- Summary metrics ---
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Filtered Orders", len(filtered))
    sc2.metric("SLA Risk", int(filtered["sla_risk"].sum()))
    avg_cost = filtered["ship_cost"].mean()
    sc3.metric("Avg Shipping Cost", f"${avg_cost:.2f}" if pd.notna(avg_cost) else "N/A")
    avg_transit = filtered["transit_days"].mean()
    sc4.metric("Avg Transit", f"{avg_transit:.1f} days" if pd.notna(avg_transit) else "N/A")

    st.markdown("---")

    # --- Routing detail table ---
    st.subheader("Routing Decisions")
    display_cols = ["order_id", "sku", "qty", "channel", "destination_region",
                    "promised_days", "recommended_node", "service_level",
                    "ship_cost", "transit_days", "total_fulfillment_cost",
                    "sla_risk", "explanation"]
    def highlight_risk_row(row):
        if row["sla_risk"]:
            return ["background-color: #fecaca"] * len(row)
        shade = "#e5e7eb" if row.name % 2 == 0 else "#f9fafb"
        return [f"background-color: {shade}"] * len(row)

    st.dataframe(
        filtered[display_cols].style.apply(highlight_risk_row, axis=1),
        use_container_width=True,
        height=500,
        column_config={
            "order_id": st.column_config.TextColumn("Order ID", width="small"),
            "sku": st.column_config.TextColumn("SKU", width="small"),
            "qty": st.column_config.NumberColumn("Qty", width="small"),
            "channel": st.column_config.TextColumn("Channel", width="small"),
            "destination_region": st.column_config.TextColumn("Destination Region", width="small"),
            "promised_days": st.column_config.NumberColumn("Promise (d)", width="small"),
            "recommended_node": st.column_config.TextColumn("Node", width="small"),
            "service_level": st.column_config.TextColumn("Service", width="small"),
            "ship_cost": st.column_config.NumberColumn("Ship $", format="%.2f", width="small"),
            "transit_days": st.column_config.NumberColumn("Transit", width="small"),
            "total_fulfillment_cost": st.column_config.NumberColumn("Total $", format="%.2f", width="small"),
            "sla_risk": st.column_config.CheckboxColumn("Risk", width="small"),
            "explanation": st.column_config.TextColumn("Explanation", width="large"),
        },
    )

    # --- Order detail drill-down ---
    st.subheader("Order Detail")
    unique_orders = filtered["order_id"].drop_duplicates().tolist()
    selected_order = st.selectbox("Select an order to inspect", unique_orders)
    if selected_order:
        # Get all lines for this order (can be 1+ SKUs)
        order_lines = data["orders"][data["orders"]["order_id"] == selected_order].copy()
        routing_lines = routing[routing["order_id"] == selected_order].copy()

        # Order-level fields (same across all lines)
        channel = order_lines["channel"].iloc[0]
        dest_region = order_lines["destination_region"].iloc[0]
        promised_days = order_lines["promised_days"].iloc[0]
        num_lines = len(order_lines)

        st.markdown(
            f"**Order {selected_order}** &nbsp;·&nbsp; {channel} &nbsp;·&nbsp; "
            f"{num_lines} line{'s' if num_lines > 1 else ''} &nbsp;·&nbsp; "
            f"to {dest_region} &nbsp;·&nbsp; promise: {promised_days} d"
        )

        # --- Table 1: Order lines (one row per SKU) ---
        st.markdown("**Order Lines**")
        items_df = data["items"][["sku", "name"]]
        lines_display = routing_lines.merge(items_df, on="sku", how="left")[
            ["sku", "name", "qty", "recommended_node", "service_level",
             "transit_days", "ship_cost", "sla_risk"]
        ].rename(columns={
            "sku": "SKU", "name": "Item", "qty": "Qty",
            "recommended_node": "Node", "service_level": "Service",
            "transit_days": "Transit (d)", "ship_cost": "Ship $", "sla_risk": "Risk",
        })
        def zebra_with_risk(row):
            if row["Risk"]:
                return ["background-color: #fecaca"] * len(row)
            shade = "#f3f4f6" if row.name % 2 == 0 else "#ffffff"
            return [f"background-color: {shade}"] * len(row)

        st.dataframe(
            lines_display.style.apply(zebra_with_risk, axis=1),
            use_container_width=True, hide_index=True,
            column_config={
                "Transit (d)": st.column_config.NumberColumn("Transit (d)", format="%.0f"),
                "Ship $": st.column_config.NumberColumn("Ship $", format="%.2f"),
                "Qty": st.column_config.NumberColumn("Qty", format="%.0f"),
            },
        )

        # --- Let user select which line to inspect ---
        if num_lines > 1:
            line_options = [f"{r['sku']} ({r['qty']} x {r['sku']})" for _, r in order_lines.iterrows()]
            selected_line_label = st.selectbox("Select a line item to see node candidates", line_options)
            selected_idx = line_options.index(selected_line_label)
        else:
            selected_idx = 0

        line = order_lines.iloc[selected_idx]
        routing_line = routing_lines.iloc[selected_idx]
        sku = line["sku"]
        qty = line["qty"]

        # Show the plain-English explanation for the selected line
        if routing_line["sla_risk"]:
            st.error(f"**{sku}:** {routing_line['explanation']}")
        else:
            st.success(f"**{sku}:** {routing_line['explanation']}")

        # --- Table 2: Node candidates for this line ---
        st.markdown(f"**Node Candidates for {sku} ({qty} x {sku})**")
        inv_candidates = data["inventory"][
            (data["inventory"]["sku"] == sku) & (data["inventory"]["available"] >= qty)
        ]

        candidates = []
        for _, inv in inv_candidates.iterrows():
            node = inv["node"]
            rates = data["carrier_rates"][
                (data["carrier_rates"]["origin_node"] == node) &
                (data["carrier_rates"]["destination_region"] == dest_region)
            ]
            for _, rate in rates.iterrows():
                item = data["items"][data["items"]["sku"] == sku].iloc[0]
                candidates.append({
                    "Node": node,
                    "Available Qty": int(inv["available"]),
                    "Service Level": rate["service_level"],
                    "Ship Cost": rate["cost"],
                    "Transit Days": rate["days"],
                    "Total Cost": round(rate["cost"] + item["unit_cost"] * qty, 2),
                    "Meets SLA": "Yes" if rate["days"] <= promised_days else "No",
                })

        if candidates:
            cand_df = pd.DataFrame(candidates)
            rec_node = routing_line["recommended_node"]
            rec_service = routing_line["service_level"]

            def zebra_candidates(row):
                is_recommended = (row["Node"] == rec_node and row["Service Level"] == rec_service)
                if is_recommended:
                    styles = ["background-color: #86efac; font-weight: 600"] * len(row)
                else:
                    shade = "#e5e7eb" if row.name % 2 == 0 else "#f9fafb"
                    styles = [f"background-color: {shade}"] * len(row)
                # Keep the SLA color coding on just that one cell (unless recommended)
                if not is_recommended:
                    sla_idx = list(row.index).index("Meets SLA")
                    if row["Meets SLA"] == "Yes":
                        styles[sla_idx] = "background-color: #bbf7d0"
                    else:
                        styles[sla_idx] = "background-color: #fecaca"
                return styles

            st.dataframe(
                cand_df.style.apply(zebra_candidates, axis=1),
                use_container_width=True, hide_index=True,
            )
        else:
            st.warning(f"No candidate nodes have sufficient inventory for {sku}.")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — Inventory Health by Node
# ═══════════════════════════════════════════════════════════════════════════════
elif screen == "Inventory Health by Node":
    st.title("Inventory Health by Node")

    # --- Filters ---
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        node_filter = st.multiselect("Node", health["node"].unique(), default=list(health["node"].unique()))
    with fc2:
        cat_filter = st.multiselect("Category", health["category"].unique(), default=list(health["category"].unique()))
    with fc3:
        status_filter = st.multiselect("Health Status", health["health_status"].unique(), default=list(health["health_status"].unique()))

    inv_filtered = health[
        health["node"].isin(node_filter) &
        health["category"].isin(cat_filter) &
        health["health_status"].isin(status_filter)
    ]

    # --- Summary ---
    ic1, ic2, ic3, ic4 = st.columns(4)
    ic1.metric("SKU-Node Combos", len(inv_filtered))
    ic2.metric("Critical", (inv_filtered["health_status"] == "Critical").sum())
    ic3.metric("Low Stock", (inv_filtered["health_status"] == "Low Stock").sum())
    ic4.metric("Overstock", (inv_filtered["health_status"] == "Overstock").sum())

    st.markdown("---")

    # --- Charts side by side ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Health Status by Node")
        status_counts = inv_filtered.groupby(["node", "health_status"]).size().reset_index(name="count")
        color_map = {"Critical": "#ef4444", "Low Stock": "#f59e0b", "Healthy": "#22c55e", "Overstock": "#3b82f6"}
        fig_status = px.bar(status_counts, x="node", y="count", color="health_status",
                            color_discrete_map=color_map,
                            category_orders={"health_status": ["Critical", "Low Stock", "Healthy", "Overstock"]},
                            barmode="stack",
                            labels={"count": "SKU Count", "node": "Node"})
        fig_status.update_layout(margin=dict(t=20, b=20), height=350, legend_title="Status",
                                 legend_traceorder="reversed")
        st.plotly_chart(fig_status, use_container_width=True)

    with col_b:
        st.subheader("Median Stock Ratio by Node")
        st.caption("**Formula:** stock_ratio = available / safety_stock  (median across SKUs at each node) &nbsp;·&nbsp; "
                   "**Below Target** (<1.0) &nbsp;·&nbsp; **On Target** (1.0–2.0) &nbsp;·&nbsp; "
                   "**Overstocked** (>2.0)")
        avg_ratio = inv_filtered.groupby("node")["stock_ratio"].median().reset_index()
        avg_ratio.columns = ["Node", "Median Stock Ratio"]
        avg_ratio["Median Stock Ratio"] = avg_ratio["Median Stock Ratio"].round(2)

        def classify_ratio(r):
            if r < 1.0:
                return "Below Target (<1.0)"
            elif r <= 2.0:
                return "On Target (1.0-2.0)"
            else:
                return "Overstocked (>2.0)"

        avg_ratio["Status"] = avg_ratio["Median Stock Ratio"].apply(classify_ratio)
        fig_ratio = px.bar(avg_ratio, x="Node", y="Median Stock Ratio",
                           text="Median Stock Ratio",
                           color="Status",
                           color_discrete_map={
                               "Below Target (<1.0)": "#ef4444",
                               "On Target (1.0-2.0)": "#22c55e",
                               "Overstocked (>2.0)": "#3b82f6",
                           },
                           category_orders={"Status": ["Below Target (<1.0)", "On Target (1.0-2.0)", "Overstocked (>2.0)"]})
        fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="#ef4444",
                            annotation_text="Safety Stock (1.0)",
                            annotation_position="top left")
        fig_ratio.add_hline(y=2.0, line_dash="dash", line_color="#3b82f6",
                            annotation_text="Overstock (2.0)",
                            annotation_position="top left")
        fig_ratio.update_traces(textposition="outside", cliponaxis=False,
                                textfont=dict(size=14, color="#111827", family="Arial"))
        fig_ratio.update_layout(margin=dict(t=20, b=20), height=380,
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_ratio, use_container_width=True)

    # --- Detail table ---
    st.subheader("Inventory Detail")

    status_colors = {
        "Critical": "background-color: #fecaca; color: #991b1b",
        "Low Stock": "background-color: #fef3c7; color: #92400e",
        "Overstock": "background-color: #dbeafe; color: #1e40af",
        "Healthy": "background-color: #dcfce7; color: #166534",
    }

    def zebra_with_status(row):
        shade = "#e5e7eb" if row.name % 2 == 0 else "#f9fafb"
        styles = [f"background-color: {shade}"] * len(row)
        # Apply the status-specific color to just the health_status cell
        status_idx = list(row.index).index("health_status")
        styles[status_idx] = status_colors.get(row["health_status"], f"background-color: {shade}")
        return styles

    inv_sorted = inv_filtered.sort_values(["health_status", "stock_ratio"]).reset_index(drop=True)
    st.dataframe(
        inv_sorted.style.apply(zebra_with_status, axis=1),
        use_container_width=True,
        height=500,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — Rebalance Recommendations
# ═══════════════════════════════════════════════════════════════════════════════
elif screen == "Rebalance Recommendations":
    st.title("Rebalance Recommendations")
    st.markdown("Transfer suggestions based on node-level surplus/deficit versus safety stock.  \n"
                "These recommendations help reposition stock before low-inventory nodes begin missing demand.")

    if rebalance.empty:
        st.success("No rebalance actions needed -- all nodes are adequately stocked.")
    else:
        # --- Summary ---
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("SKUs Requiring Transfer", len(rebalance))
        rc2.metric("High Priority SKUs", (rebalance["priority"] == "High").sum())
        rc3.metric("Total Units to Move", int(rebalance["transfer_qty"].sum()))

        st.markdown("---")

        # --- Priority filter ---
        pri_filter = st.radio("Filter by Priority", ["All", "High", "Medium"], horizontal=True)
        reb_filtered = rebalance if pri_filter == "All" else rebalance[rebalance["priority"] == pri_filter]

        # --- Transfers grouped bar + detail table ---
        st.subheader("Recommended Transfer Volume by Source and Destination Node")
        transfer_summary = reb_filtered.groupby(["from_node", "to_node"]).agg(
            skus=("sku", "count"),
            total_units=("transfer_qty", "sum"),
        ).reset_index()
        transfer_summary.columns = ["From", "To", "SKUs", "Total Units"]

        fig_transfers = px.bar(
            transfer_summary, x="From", y="Total Units", color="To",
            text="SKUs",
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"Total Units": "Units to Transfer", "From": "Source Node"},
        )
        fig_transfers.update_traces(texttemplate="%{text} SKUs", textposition="outside", cliponaxis=False,
                                    textfont=dict(size=13, color="#111827", family="Arial"))
        y_max = transfer_summary["Total Units"].max() * 1.25
        fig_transfers.update_layout(margin=dict(t=60, b=20), height=450, legend_title="Destination",
                                    yaxis=dict(range=[0, y_max]))
        st.plotly_chart(fig_transfers, use_container_width=True)

        # --- Transfer detail table ---
        st.subheader("Transfer Details")
        display_reb = reb_filtered[["sku", "sku_name", "from_node", "to_node",
                                     "transfer_qty", "source_available",
                                     "dest_available", "dest_safety_stock", "priority"]]
        st.dataframe(
            display_reb.style.applymap(
                lambda v: "background-color: #fef3c7; color: #92400e; font-weight: bold" if v == "High" else "",
                subset=["priority"]
            ),
            use_container_width=True,
            height=400,
        )

        # --- Impact summary ---
        st.subheader("Impact by Destination Node")
        impact = reb_filtered.groupby("to_node").agg(
            transfers=("transfer_qty", "count"),
            total_units=("transfer_qty", "sum"),
        ).reset_index()
        impact.columns = ["Destination Node", "# Transfers", "Total Units Incoming"]
        fig_impact = px.bar(impact, x="Destination Node", y="Total Units Incoming",
                            text="# Transfers",
                            color="Total Units Incoming",
                            color_continuous_scale=["#93c5fd", "#3b82f6"],
                            labels={"Total Units Incoming": "Units"})
        fig_impact.update_traces(texttemplate="%{text} transfers", textposition="outside", cliponaxis=False,
                                 textfont=dict(size=13, color="#111827", family="Arial"))
        y_max_impact = impact["Total Units Incoming"].max() * 1.25
        fig_impact.update_layout(margin=dict(t=60, b=20), height=380, coloraxis_showscale=False,
                                 yaxis=dict(range=[0, y_max_impact]))
        st.plotly_chart(fig_impact, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 5 — AI Routing Optimization
# ═══════════════════════════════════════════════════════════════════════════════
elif screen == "AI Routing Optimization":
    st.title("AI Routing Optimization")
    st.markdown("Compare rules-based routing with model-driven recommendations that balance cost, "
                "SLA performance, inventory health, and network efficiency.")

    # --- How it differs from rules ---
    with st.expander("How the AI model differs from the rules engine", expanded=False):
        col_diff1, col_diff2 = st.columns(2)
        with col_diff1:
            st.markdown("**Rules Engine**")
            st.markdown(
                "- Picks the **cheapest** SLA-safe option\n"
                "- Not inventory-aware: may deplete low-stock nodes\n"
                "- Not history-aware: ignores past delivery performance\n"
                "- Not demand-aware: ignores regional demand pressure"
            )
        with col_diff2:
            st.markdown("**AI Model (Weighted Scoring Model)**")
            st.markdown(
                "- Balances **5 factors**: cost (35%), SLA buffer (25%), inventory health (25%), demand pressure (10%), on-time history (5%)\n"
                "- Avoids pulling from under-stocked nodes\n"
                "- Prefers nodes with strong on-time track records\n"
                "- Preserves inventory at high-demand regions"
            )

        st.markdown("---")
        st.markdown("**Key Metrics Explained**")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("**Avg Source Stock Ratio**")
            st.markdown(
                "The average inventory health of the nodes each approach pulls from. "
                "A higher ratio means the engine is choosing well-stocked sources, "
                "keeping the network healthier after fulfillment. "
                "The AI deliberately avoids thin nodes and prefers sources with a comfortable buffer above safety stock."
            )
        with col_m2:
            st.markdown("**Orders from Critical Nodes**")
            st.markdown(
                "How many orders each approach fulfills from nodes where the SKU's stock ratio "
                "is below 0.5 (less than half of safety stock). Every order shipped from a critical node "
                "pushes it closer to being out of stock. The rules engine based on simple cost optimization doesn't see this, "
                "it just sees a cheaper rate. The AI reroutes those orders to healthier sources."
            )

        st.markdown("")
        st.markdown(
            "**The tradeoff:** Currently, the weighted AI algorithm costs more in shipping per order, but it protects low-inventory nodes "
            "from depletion. When an item is out of stock in a node, the downstream costs can be significant: orders shift to "
            "farther nodes with higher shipping costs, delivery promises get missed, or orders are canceled entirely. "
            "Quantifying the dollar value of prevented out-of-stock events is the next step toward making this tradeoff measurable. "
            "These tradeoff simulations are what this platform allows for."
        )

    # --- Section 1: KPI Cards ---
    st.subheader("AI Evaluation Summary")
    ak1, ak2 = st.columns(2)
    ak1.metric("Orders Scored", ai_kpis["total_scored"])
    ak2.metric("AI Rerouted Orders", ai_kpis["different_recommendations"],
               delta=f"{ai_kpis['pct_different']}% of orders")

    st.subheader("Rules vs AI Comparison")
    ship_delta = ai_kpis["ai_avg_ship"] - ai_kpis["rules_avg_ship"]
    transit_delta = ai_kpis["ai_avg_transit"] - ai_kpis["rules_avg_transit"]
    sla_delta = ai_kpis["ai_sla_risk"] - ai_kpis["rules_sla_risk"]

    bk1, bk2, bk3 = st.columns(3)
    bk1.metric("Avg Shipping Cost", f"${ai_kpis['rules_avg_ship']}",
               help="Rules engine")
    bk2.metric("Avg Transit", f"{ai_kpis['rules_avg_transit']} days",
               help="Rules engine")
    bk3.metric("SLA Risk Orders", ai_kpis["rules_sla_risk"],
               help="Rules engine")

    bk4, bk5, bk6 = st.columns(3)
    ship_pct = round(ship_delta / ai_kpis["rules_avg_ship"] * 100, 1) if ai_kpis["rules_avg_ship"] > 0 else 0
    transit_pct = round(transit_delta / ai_kpis["rules_avg_transit"] * 100, 1) if ai_kpis["rules_avg_transit"] > 0 else 0
    sla_pct = round(sla_delta / ai_kpis["rules_sla_risk"] * 100, 1) if ai_kpis["rules_sla_risk"] > 0 else 0

    bk4.metric("Avg Shipping Cost (AI)", f"${ai_kpis['ai_avg_ship']}",
               delta=f"{ship_pct:+.1f}% vs rules", delta_color="inverse" if ship_pct != 0 else "off")
    bk5.metric("Avg Transit (AI)", f"{ai_kpis['ai_avg_transit']} days",
               delta=f"{transit_pct:+.1f}% vs rules", delta_color="inverse" if transit_pct != 0 else "off")
    bk6.metric("SLA Risk Orders (AI)", ai_kpis["ai_sla_risk"],
               delta=f"{sla_pct:+.1f}% vs rules", delta_color="inverse" if sla_pct != 0 else "off")

    st.subheader("Network Health Impact")
    ck1, ck2, ck3, ck4 = st.columns(4)
    stock_delta = ai_kpis["ai_avg_stock_ratio"] - ai_kpis["rules_avg_stock_ratio"]
    ck1.metric("Avg Source Stock Ratio (Rules)", ai_kpis["rules_avg_stock_ratio"])
    ck2.metric("Avg Source Stock Ratio (AI)", ai_kpis["ai_avg_stock_ratio"],
               delta=f"{stock_delta:+.2f}", delta_color="normal")
    critical_delta = ai_kpis["ai_from_critical"] - ai_kpis["rules_from_critical"]
    ck3.metric("Orders from Critical Nodes (Rules)", ai_kpis["rules_from_critical"])
    ck4.metric("Orders from Critical Nodes (AI)", ai_kpis["ai_from_critical"],
               delta=f"{critical_delta:+d}", delta_color="inverse")

    st.markdown("---")

    # --- Section 2: Node distribution comparison ---
    st.subheader("Routing Distribution: Rules vs AI")
    rules_dist = comparison.dropna(subset=["rules_node"]).groupby("rules_node").size().reset_index(name="Orders")
    rules_dist.columns = ["Node", "Orders"]
    rules_dist["Engine"] = "Rules"

    ai_dist = comparison.dropna(subset=["ai_node"]).groupby("ai_node").size().reset_index(name="Orders")
    ai_dist.columns = ["Node", "Orders"]
    ai_dist["Engine"] = "AI"

    combined_dist = pd.concat([rules_dist, ai_dist], ignore_index=True)
    fig_dist = px.bar(combined_dist, x="Node", y="Orders", color="Engine",
                      text="Orders", barmode="group",
                      color_discrete_map={"Rules": "#f97316", "AI": "#3b82f6"},
                      labels={"Orders": "Order Count"})
    fig_dist.update_traces(textposition="outside", cliponaxis=False,
                           textfont=dict(size=13, color="#111827", family="Arial"))
    y_max = combined_dist["Orders"].max() * 1.3
    fig_dist.update_layout(margin=dict(t=40, b=20), height=350,
                           yaxis=dict(range=[0, y_max]),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
    st.plotly_chart(fig_dist, use_container_width=True)

    st.markdown("---")

    # --- Section 3: Comparison table ---
    st.subheader("Side-by-Side Routing Comparison")
    st.markdown("**Rows highlighted in blue indicate where the AI recommends a different node than the rules engine.**")

    compare_display = comparison[[
        "order_id", "sku", "qty", "destination_region", "promised_days",
        "rules_node", "ai_node", "same_node",
        "rules_ship_cost", "ai_ship_cost", "cost_delta",
        "rules_transit", "ai_transit", "transit_delta",
        "ai_confidence", "ai_reason",
    ]].copy()

    def highlight_comparison(row):
        if not row["same_node"]:
            return ["background-color: #e0f2fe"] * len(row)
        return [""] * len(row)

    st.dataframe(
        compare_display.style.apply(highlight_comparison, axis=1),
        use_container_width=True,
        height=450,
        hide_index=True,
        column_config={
            "order_id": st.column_config.TextColumn("Order ID", width="small"),
            "sku": st.column_config.TextColumn("SKU", width="small"),
            "qty": st.column_config.NumberColumn("Qty", width="small"),
            "destination_region": st.column_config.TextColumn("Destination Region", width="small"),
            "promised_days": st.column_config.NumberColumn("Promise", width="small"),
            "rules_node": st.column_config.TextColumn("Rules Node", width="small"),
            "ai_node": st.column_config.TextColumn("AI Node", width="small"),
            "same_node": st.column_config.CheckboxColumn("Same?", width="small"),
            "rules_ship_cost": st.column_config.NumberColumn("Rules $", format="%.2f", width="small"),
            "ai_ship_cost": st.column_config.NumberColumn("AI $", format="%.2f", width="small"),
            "cost_delta": st.column_config.NumberColumn("Cost +/-", format="%+.2f", width="small"),
            "rules_transit": st.column_config.NumberColumn("Rules Days", format="%.0f", width="small"),
            "ai_transit": st.column_config.NumberColumn("AI Days", format="%.0f", width="small"),
            "transit_delta": st.column_config.NumberColumn("Days +/-", format="%+.0f", width="small"),
            "ai_confidence": st.column_config.TextColumn("Confidence", width="small"),
            "ai_reason": st.column_config.TextColumn("AI Rationale", width="large"),
        },
    )

    st.markdown("---")

    # --- Section 4: Order drill-down ---
    st.subheader("Order Deep Dive")
    unique_ai_orders = comparison["order_id"].drop_duplicates().tolist()
    selected_ai_order = st.selectbox("Select an order to compare", unique_ai_orders, key="ai_order")

    if selected_ai_order:
        order_rows = comparison[comparison["order_id"] == selected_ai_order]

        for _, row in order_rows.iterrows():
            st.markdown(f"**{row['order_id']} / {row['sku']}** ({row['qty']} units to {row['destination_region']}, promise: {row['promised_days']}d)")

            col_r, col_a = st.columns(2)
            with col_r:
                st.markdown("##### Rules Engine")
                if pd.notna(row["rules_node"]):
                    st.metric("Node", row["rules_node"])
                    r1, r2 = st.columns(2)
                    r1.metric("Ship Cost", f"${row['rules_ship_cost']:.2f}")
                    r2.metric("Transit", f"{int(row['rules_transit'])}d")
                    st.caption(f"Reason: {row['rules_explanation']}")
                else:
                    st.warning("No route found")

            with col_a:
                st.markdown("##### AI Model")
                if pd.notna(row["ai_node"]):
                    st.metric("Node", row["ai_node"])
                    a1, a2 = st.columns(2)
                    a1.metric("Ship Cost", f"${row['ai_ship_cost']:.2f}")
                    a2.metric("Transit", f"{int(row['ai_transit'])}d")
                    st.markdown(f"**Confidence:** {row['ai_confidence']}")
                    st.caption(f"Reason: {row['ai_reason']}")
                else:
                    st.warning("No route found")

            # Show candidate scoring table
            ai_row = ai_routing[
                (ai_routing["order_id"] == selected_ai_order) & (ai_routing["sku"] == row["sku"])
            ]
            if not ai_row.empty and ai_row.iloc[0]["_scored_candidates"]:
                st.markdown("**Candidate Node Scoring**")
                candidates = pd.DataFrame(ai_row.iloc[0]["_scored_candidates"])
                if not candidates.empty:
                    display_cands = candidates[[
                        "node", "service_level", "available_qty", "ship_cost",
                        "transit_days", "total_cost", "stock_ratio",
                        "sla_score", "cost_score", "inventory_score",
                        "performance_score", "demand_score", "ai_score",
                    ]].rename(columns={
                        "node": "Node", "service_level": "Service",
                        "available_qty": "Avail Qty", "ship_cost": "Ship $",
                        "transit_days": "Transit", "total_cost": "Total $",
                        "stock_ratio": "Stock Ratio",
                        "sla_score": "SLA", "cost_score": "Cost",
                        "inventory_score": "Inventory", "performance_score": "On-Time",
                        "demand_score": "Demand", "ai_score": "AI Score",
                    }).sort_values("AI Score", ascending=False)

                    def highlight_top_candidate(r):
                        if r.name == display_cands.index[0]:
                            return ["background-color: #86efac; font-weight: 600"] * len(r)
                        shade = "#e5e7eb" if r.name % 2 == 0 else "#f9fafb"
                        return [f"background-color: {shade}"] * len(r)

                    st.dataframe(
                        display_cands.style.apply(highlight_top_candidate, axis=1),
                        use_container_width=True, hide_index=True,
                    )
                    st.caption("Feature scores range 0.0 (worst) to 1.0 (best). "
                               "AI Score is the weighted combination. Top-ranked candidate highlighted in green.")

            st.markdown("---")

    # --- Section 5: How we measure performance ---
    with st.expander("How We Measure AI Performance", expanded=False):
        st.markdown(
            "- **Difference rate:** How often the AI picks a different node than the rules engine. "
            "A higher rate indicates the model is finding optimization opportunities the rules miss.\n"
            "- **Cost delta:** The total difference in shipping cost between rules and AI recommendations. "
            "The AI may be costlier in the short term because it trades shipping cost for network resilience.\n"
            "- **SLA risk comparison:** Whether either approach fails to meet delivery promises.\n"
            "- **Node distribution shift:** How the AI redistributes order volume across nodes, "
            "typically pulling demand away from under-stocked nodes toward healthier ones."
        )

    with st.expander("Current Demo Limitations", expanded=False):
        st.markdown(
            "- **No trained ML model:** This is a fixed-weight scoring model, not a model trained on historical outcomes. "
            "The weights (35% cost, 25% SLA, 25% inventory, 10% demand, 5% on-time) are not learned from data.\n"
            "- **No backtesting:** We are not yet measuring whether the AI would have performed better on last week's orders.\n"
            "- **No cost-of-out-of-stock metric:** The AI avoids depleting low-stock nodes, "
            "but we do not yet quantify the dollar value of prevented out-of-stock events.\n"
            "- **No confidence calibration:** The High/Medium/Low confidence labels are score thresholds, "
            "not probabilistic confidence intervals.\n"
            "- **Static weights:** In production, a model like XGBoost or LightGBM could learn optimal weights "
            "from delivery outcomes, adapting as network conditions change."
        )
