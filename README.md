# Davinci Micro-Fulfillment Analytics Control Center

A demo operations dashboard for Davinci Micro Fulfillment that unifies order, inventory, and fulfillment data into a single control center.

## What This Demo Shows

The platform answers two core business questions:

1. **Which node should fulfill each order?** A rules-based routing engine and an AI-powered weighted scoring model evaluate candidate nodes based on cost, SLA, inventory health, and demand patterns.
2. **Where should inventory be rebalanced?** The system identifies under-stocked and over-stocked nodes and recommends transfers before service levels slip.

The dashboard walks through five screens: a network health overview, order routing, inventory health by node, rebalance recommendations, and a side-by-side comparison of rules-based vs AI-driven routing.

## Run It Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Built By

**uBIT Technologies**
