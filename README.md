# Davinci Micro-Fulfillment Analytics Control Center

A demo operations dashboard for Davinci Micro Fulfillment that unifies order, inventory, and fulfillment data into a single control center.

## What This Demo Shows

The dashboard walks through five screens:

- **Network Health Overview** — a top-level KPI snapshot of the fulfillment network: today's order volume, SLA risk, average fulfillment cost, historical on-time rate, and live inventory alerts across every node.
- **Order Routing** — a rules-based routing simulator that shows, for each of today's orders, which node was picked to fulfill it and why. You can drill into any order to see the candidate nodes that were considered, their shipping cost, transit time, and inventory position.
- **Inventory Health by Node** — every SKU at every node classified as Critical, Low Stock, Healthy, or Overstock based on its ratio to safety stock, so operators can spot where the network is thin or sitting on excess.
- **Rebalance Recommendations** — suggested transfers from overstocked nodes to deficit nodes, prioritized by urgency, so inventory can be moved before service levels slip.
- **AI Routing Optimization** — a side-by-side comparison of the rules-based engine versus an AI-driven weighted scoring model that balances cost, SLA slack, inventory health, demand pressure, and each node's historical on-time performance. This screen is a **simulation of what's possible**: it illustrates how a smarter routing layer would shift decisions, and what the projected impact on cost, SLA, and inventory health would look like if Davinci moved beyond simple cost-minimization rules.

## Run It Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 in your browser.
