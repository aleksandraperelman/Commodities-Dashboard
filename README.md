# 📊 Commodities Quant Terminal

An interactive, auto-refreshing dashboard for tracking energy & metals commodities alongside macro inputs — built in Python with Streamlit and Plotly. Dark trading-terminal UI, designed as a quant research tool.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/streamlit-app-red)

## Features

- **Live prices** for 10 commodities (crude, Brent, nat gas, gasoline, heating oil, gold, silver, copper, platinum, palladium) with auto-refresh.
- **Macro inputs** (17, opt-in): full yield curve, FX, equities, VIX, credit, Bitcoin, commodity index.
- **Performance & risk** — relative performance, rolling volatility, drawdowns, and a risk table (Sharpe, Sortino, max drawdown, skew, kurtosis).
- **Quant signals** — trend (golden/death cross), 12-1 momentum ranking, mean-reversion z-scores, and RSI.
- **Alerts** — configurable thresholds (RSI, z-score, daily move) surfaced as a live banner and tab.
- **Correlations** — commodities + macro heatmap and interactive rolling correlation for any pair.
- **Macro factor betas** — multivariate OLS of each commodity vs the macro set, with R².
- **Energy fundamentals** — EIA weekly inventories, production, refinery utilization, and nat-gas storage (free API key).
- **Seasonality** — average return by calendar month.
