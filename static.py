# %%
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# %%
COMMODITIES = {
    # Energy
    "WTI Crude":   "CL=F",
    "Brent Crude": "BZ=F",
    "Natural Gas": "NG=F",
    "Gasoline":    "RB=F",
    "Heating Oil": "HO=F",
    # Metals
    "Gold":        "GC=F",
    "Silver":      "SI=F",
    "Copper":      "HG=F",
    "Platinum":    "PL=F",
    "Palladium":   "PA=F",
}

MACRO = {
    "US Dollar":   "DX-Y.NYB",   # US Dollar Index
    "10Y Yield":   "^TNX",       # 10-year Treasury yield
    "S&P 500":     "^GSPC",      # equities
    "VIX":         "^VIX",       # equity volatility / fear gauge
}

LOOKBACK = "5y"
TRADING_DAYS = 252
RISK_FREE = 0.0
OUTPUT_FILE = "quant_dashboard.html"

ALL = {**COMMODITIES, **MACRO}

# %%
raw = yf.download(list(ALL.values()), period=LOOKBACK, interval="1d", progress=False)
close = raw["Close"].copy()

name_by_ticker = {t: n for n, t in ALL.items()}
close = close.rename(columns=name_by_ticker)
close = close[[n for n in ALL if n in close.columns]]
close = close.ffill().dropna(how="all")

comm_cols  = [n for n in COMMODITIES if n in close.columns]
macro_cols = [n for n in MACRO if n in close.columns]

rets = close.pct_change()
comm_rets = rets[comm_cols].dropna(how="all")

# %%
def pct_change_n(s, n):
    s = s.dropna()
    if len(s) <= n:
        return np.nan
    return (s.iloc[-1] - s.iloc[-1 - n]) / s.iloc[-1 - n] * 100

def ytd_change(s):
    s = s.dropna()
    if s.empty:
        return np.nan
    this_year = s[s.index.year == s.index[-1].year]
    if this_year.empty:
        return np.nan
    return (s.iloc[-1] - this_year.iloc[0]) / this_year.iloc[0] * 100

def max_drawdown(price):
    price = price.dropna()
    if price.empty:
        return np.nan
    cummax = price.cummax()
    dd = price / cummax - 1.0
    return dd.min() * 100

def color_for(vals):
    return ["#1a7f37" if (v is not None and v > 0) else
            "#cf222e" if (v is not None and v < 0) else "gray" for v in vals]

def table_figure(df, title, color_cols=None, height=None):
    color_cols = color_cols or []
    font_colors = []
    for c in df.columns:
        if c in color_cols:
            font_colors.append(color_for(df[c].tolist()))
        else:
            font_colors.append(["black"] * len(df))
    fig = go.Figure(go.Table(
        header=dict(values=list(df.columns), fill_color="#111827",
                    font=dict(color="white", size=12), align="left", height=28),
        cells=dict(values=[df[c] for c in df.columns], align="left",
                   font=dict(color=font_colors, size=11), height=24,
                   fill_color=[["#f9fafb", "#ffffff"] * len(df)]),
    ))
    fig.update_layout(title=title, margin=dict(t=44, b=8, l=8, r=8),
                      height=height or (60 + 26 * len(df)))
    return fig


# %%
snap_rows = []
for name in comm_cols:
    s = close[name].dropna()
    last = s.iloc[-1]
    hi = s.tail(TRADING_DAYS).max()
    lo = s.tail(TRADING_DAYS).min()
    pos = (last - lo) / (hi - lo) * 100 if hi > lo else np.nan
    snap_rows.append({
        "Commodity": name,
        "Price": round(last, 2),
        "1D %": round(pct_change_n(s, 1), 2),
        "1W %": round(pct_change_n(s, 5), 2),
        "1M %": round(pct_change_n(s, 21), 2),
        "3M %": round(pct_change_n(s, 63), 2),
        "YTD %": round(ytd_change(s), 2),
        "1Y %": round(pct_change_n(s, TRADING_DAYS), 2),
        "52w Range %": round(pos, 1),
    })
snapshot = pd.DataFrame(snap_rows)
snapshot_fig = table_figure(
    snapshot, "1. Snapshot — Price & Returns  (52w Range %: 0 = year low, 100 = year high)",
    color_cols=["1D %", "1W %", "1M %", "3M %", "YTD %", "1Y %"])

# %%
metric_rows = []
for name in comm_cols:
    r = comm_rets[name].dropna()
    if r.empty:
        continue
    ann_ret = r.mean() * TRADING_DAYS * 100
    ann_vol = r.std() * np.sqrt(TRADING_DAYS) * 100
    sharpe = (ann_ret - RISK_FREE * 100) / ann_vol if ann_vol else np.nan
    downside = r[r < 0].std() * np.sqrt(TRADING_DAYS) * 100
    sortino = (ann_ret - RISK_FREE * 100) / downside if downside else np.nan
    metric_rows.append({
        "Commodity": name,
        "Ann Return %": round(ann_ret, 1),
        "Ann Vol %": round(ann_vol, 1),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2),
        "Max DD %": round(max_drawdown(close[name]), 1),
        "Skew": round(r.skew(), 2),
        "Kurtosis": round(r.kurtosis(), 2),
    })
metrics = pd.DataFrame(metric_rows)
metrics_fig = table_figure(
    metrics, f"2. Risk / Return Metrics  (annualized over {LOOKBACK}, risk-free = 0)",
    color_cols=["Ann Return %", "Sharpe", "Sortino", "Max DD %"])


# %%
norm = close[comm_cols] / close[comm_cols].bfill().iloc[0] * 100
perf_fig = go.Figure()
for name in comm_cols:
    perf_fig.add_trace(go.Scatter(x=norm.index, y=norm[name], name=name, mode="lines"))
perf_fig.update_layout(title=f"3. Relative Performance — rebased to 100 ({LOOKBACK})",
                       xaxis_title="Date", yaxis_title="Index (start = 100)",
                       template="plotly_white", hovermode="x unified", height=520)


# %%
n_cols = 3
n_rows = (len(comm_cols) + n_cols - 1) // n_cols
grid_fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=comm_cols,
                         vertical_spacing=0.07, horizontal_spacing=0.05)
for i, name in enumerate(comm_cols):
    r, c = divmod(i, n_cols); r += 1; c += 1
    s = close[name]
    grid_fig.add_trace(go.Scatter(x=s.index, y=s, line=dict(color="#1f77b4", width=1.3),
                                  showlegend=False), row=r, col=c)
    grid_fig.add_trace(go.Scatter(x=s.index, y=s.rolling(20).mean(),
                                  line=dict(color="orange", width=0.9), showlegend=False), row=r, col=c)
    grid_fig.add_trace(go.Scatter(x=s.index, y=s.rolling(50).mean(),
                                  line=dict(color="green", width=0.9), showlegend=False), row=r, col=c)
    grid_fig.add_trace(go.Scatter(x=s.index, y=s.rolling(200).mean(),
                                  line=dict(color="red", width=0.9), showlegend=False), row=r, col=c)
grid_fig.update_layout(
    title="4. Price History + Moving Averages  (blue=price, orange=20d, green=50d, red=200d)",
    template="plotly_white", height=260 * n_rows)

# %%
roll_vol = comm_rets.rolling(30).std() * np.sqrt(TRADING_DAYS) * 100
vol_fig = go.Figure()
for name in comm_cols:
    vol_fig.add_trace(go.Scatter(x=roll_vol.index, y=roll_vol[name], name=name, mode="lines"))
vol_fig.update_layout(title="5. Rolling 30-day Annualized Volatility (%)",
                      xaxis_title="Date", yaxis_title="Annualized vol %",
                      template="plotly_white", hovermode="x unified", height=480)

# %%
dd_fig = go.Figure()
for name in comm_cols:
    p = close[name].dropna()
    dd = (p / p.cummax() - 1.0) * 100
    dd_fig.add_trace(go.Scatter(x=dd.index, y=dd, name=name, mode="lines"))
dd_fig.update_layout(title="6. Drawdowns — % below prior peak (underwater curve)",
                     xaxis_title="Date", yaxis_title="Drawdown %",
                     template="plotly_white", hovermode="x unified", height=480)

# %%
corr = rets[comm_cols + macro_cols].dropna().corr().round(2)
heat_fig = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index,
                                zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
                                text=corr.values, texttemplate="%{text}",
                                textfont=dict(size=9)))
heat_fig.update_layout(title="7. Correlation of Daily Returns — Commodities + Macro",
                       height=680, template="plotly_white")


# %%
rc_fig = go.Figure()
pairs = []
if "US Dollar" in macro_cols:
    pairs += [("WTI Crude", "US Dollar"), ("Gold", "US Dollar"), ("Copper", "US Dollar")]
if "S&P 500" in macro_cols:
    pairs += [("Copper", "S&P 500"), ("WTI Crude", "S&P 500")]
for a, b in pairs:
    if a in rets.columns and b in rets.columns:
        rcorr = rets[a].rolling(60).corr(rets[b])
        rc_fig.add_trace(go.Scatter(x=rcorr.index, y=rcorr, name=f"{a} vs {b}", mode="lines"))
rc_fig.add_hline(y=0, line_dash="dash", line_color="gray")
rc_fig.update_layout(title="8. Rolling 60-day Correlation vs Macro Drivers",
                     xaxis_title="Date", yaxis_title="Correlation",
                     template="plotly_white", hovermode="x unified", height=480)

# %%
beta_fig = None
if macro_cols:
    joined = rets[comm_cols + macro_cols].dropna()
    X = joined[macro_cols].values
    X = np.column_stack([np.ones(len(X)), X])
    beta_rows = []
    for name in comm_cols:
        y = joined[name].values
        try:
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            yhat = X @ coef
            ss_res = np.sum((y - yhat) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot else np.nan
            row = {"Commodity": name}
            for j, m in enumerate(macro_cols):
                row[f"β {m}"] = round(coef[j + 1], 2)
            row["R²"] = round(r2, 2)
            beta_rows.append(row)
        except Exception:
            pass
    if beta_rows:
        betas = pd.DataFrame(beta_rows)
        beta_fig = table_figure(
            betas, "9. Macro Factor Betas — sensitivity of daily returns to macro moves "
                   "(multivariate regression; R² = share of variance explained)",
            color_cols=[c for c in betas.columns if c.startswith("β")])


# %%
monthly = close[comm_cols].resample("ME").last().pct_change() * 100
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
seas = monthly.groupby(monthly.index.month).mean().reindex(range(1, 13))
seas.index = month_names
season_fig = go.Figure(go.Heatmap(
    z=seas.T.values, x=month_names, y=comm_cols,
    colorscale="RdBu", reversescale=True, zmid=0,
    text=np.round(seas.T.values, 1), texttemplate="%{text}", textfont=dict(size=9)))
season_fig.update_layout(title="10. Seasonality — Average Monthly Return % (by calendar month)",
                         height=500, template="plotly_white")

# %%
hist_fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=comm_cols,
                         vertical_spacing=0.07, horizontal_spacing=0.05)
for i, name in enumerate(comm_cols):
    r, c = divmod(i, n_cols); r += 1; c += 1
    vals = comm_rets[name].dropna() * 100
    hist_fig.add_trace(go.Histogram(x=vals, nbinsx=60, showlegend=False,
                                    marker_color="#1f77b4"), row=r, col=c)
hist_fig.update_layout(title="11. Daily Return Distributions (%)",
                       template="plotly_white", height=260 * n_rows, bargap=0.02)

# %%
spread_fig = make_subplots(rows=1, cols=2,
                           subplot_titles=["WTI − Brent spread ($/bbl)",
                                           "Gasoline Crack Spread ($/bbl)  [RB×42 − WTI]"])
if {"WTI Crude", "Brent Crude"} <= set(close.columns):
    wb = (close["WTI Crude"] - close["Brent Crude"]).dropna()
    spread_fig.add_trace(go.Scatter(x=wb.index, y=wb, line=dict(color="#1f77b4"),
                                    showlegend=False), row=1, col=1)
    spread_fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
if {"Gasoline", "WTI Crude"} <= set(close.columns):
    crack = (close["Gasoline"] * 42 - close["WTI Crude"]).dropna()
    spread_fig.add_trace(go.Scatter(x=crack.index, y=crack, line=dict(color="#d62728"),
                                    showlegend=False), row=1, col=2)
spread_fig.update_layout(title="12. Key Energy Spreads — relative-value & refining-margin signals",
                         template="plotly_white", height=420)


# %%
print("Building dashboard...")
header = f"""
<div style="font-family:sans-serif">
  <h1 style="margin-bottom:0">Commodities Quant Dashboard</h1>
  <p style="color:#555;margin-top:4px">
     Energy &amp; Metals + Macro inputs &nbsp;|&nbsp; lookback {LOOKBACK}
     &nbsp;|&nbsp; data: Yahoo Finance via yfinance.
     Returns are daily % unless noted. Educational use only — not investment advice.
  </p><hr>
</div>"""

figs = [snapshot_fig, metrics_fig, perf_fig, grid_fig, vol_fig, dd_fig,
        heat_fig, rc_fig]
if beta_fig is not None:
    figs.append(beta_fig)
figs += [season_fig, hist_fig, spread_fig]

parts = [header, figs[0].to_html(full_html=False, include_plotlyjs="cdn")]
parts += [f.to_html(full_html=False, include_plotlyjs=False) for f in figs[1:]]

html = ("<html><head><meta charset='utf-8'></head>"
        "<body style='max-width:1180px;margin:auto;background:#fff'>"
        + "".join(parts) + "</body></html>")
Path(OUTPUT_FILE).write_text(html, encoding="utf-8")
webbrowser.open("file://" + str(Path(OUTPUT_FILE).resolve()))
print(f"Done! Saved + opened '{OUTPUT_FILE}'.")


