# ============================================================================
# COMMODITIES QUANT TERMINAL — interactive, auto-refreshing (Streamlit)
# ----------------------------------------------------------------------------
# Install once:
#     python3 -m pip install streamlit streamlit-autorefresh yfinance pandas numpy plotly requests
#
# Run (NOT "python3 app.py" — use streamlit):
#     cd ~/Desktop/commodities-dashboard
#     streamlit run app.py
#
# Theme is set in .streamlit/config.toml (dark) + CSS below. Energy tab needs a
# free EIA key (https://www.eia.gov/opendata/register.php) entered in sidebar.
# ============================================================================

import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
COMMODITIES = {
    "WTI Crude": "CL=F", "Brent Crude": "BZ=F", "Natural Gas": "NG=F",
    "Gasoline": "RB=F", "Heating Oil": "HO=F",
    "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
    "Platinum": "PL=F", "Palladium": "PA=F",
}
MACRO = {
    "US Dollar": "DX-Y.NYB", "EUR/USD": "EURUSD=X", "USD/JPY": "JPY=X",
    "13W Yield": "^IRX", "5Y Yield": "^FVX", "10Y Yield": "^TNX", "30Y Yield": "^TYX",
    "20Y+ Treasury": "TLT",
    "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "China FXI": "FXI", "Emerging Mkts": "EEM",
    "VIX": "^VIX", "High Yield": "HYG", "Bitcoin": "BTC-USD",
    "Gold Miners": "GDX", "Commodity Index": "DBC",
}
MACRO_DEFAULT = ["US Dollar", "10Y Yield", "S&P 500", "VIX"]
EIA_SERIES = {
    "Crude stocks excl. SPR (Mbbl)": ("PET.WCESTUS1.W", "Thousand barrels"),
    "Cushing crude stocks (Mbbl)":   ("PET.W_EPC0_SAX_YCUOK_MBBL.W", "Thousand barrels"),
    "Crude production (Mbbl/d)":      ("PET.WCRFPUS2.W", "Thousand barrels/day"),
    "Refinery utilization (%)":       ("PET.WPULEUS3.W", "Percent"),
    "Gasoline stocks (Mbbl)":         ("PET.WGTSTUS1.W", "Thousand barrels"),
    "Distillate stocks (Mbbl)":       ("PET.WDISTUS1.W", "Thousand barrels"),
    "Nat-gas storage L48 (Bcf)":      ("NG.NW2_EPG0_SWO_R48_BCF.W", "Bcf"),
}
EIA_DEFAULT = ["Crude stocks excl. SPR (Mbbl)", "Crude production (Mbbl/d)",
               "Nat-gas storage L48 (Bcf)"]
TRADING_DAYS = 252
LOOKBACK_YEARS = {"1y": 1, "2y": 2, "3y": 3, "5y": 5}

# ---- terminal palette ------------------------------------------------------
BG, PANEL, GRID = "#0B0E14", "#131722", "#1C2230"
TXT, SUB = "#C9D1D9", "#8B949E"
GREEN, RED = "#16A34A", "#DC2626"
MONO = "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
# distinct multi-series colors that read well on near-black
SERIES = ["#58A6FF", "#F5A623", "#3FB950", "#DB6D28", "#A371F7",
          "#39C5CF", "#D2A8FF", "#E3B341", "#FF7B72", "#7EE787"]
# diverging red→green for correlation / seasonality heatmaps
RG_SCALE = [[0.0, RED], [0.5, "#0B0E14"], [1.0, GREEN]]
# sequential red(low)→green(high) for performance heatmap
RYG = [[0.0, "#7F1D1D"], [0.5, "#1C2230"], [1.0, "#14532D"]]

st.set_page_config(page_title="Commodities Quant Terminal", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# CSS — terminal look, compact, sidebar reflow fix
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"], .stApp {{ font-family:{MONO}; }}
.stApp {{ background:{BG}; }}

/* compact main container, full width */
div.block-container {{ padding:0.6rem 1.1rem 1rem 1.1rem; max-width:100%; }}
[data-testid="stVerticalBlock"] {{ gap:0.45rem; }}
[data-testid="stHorizontalBlock"] {{ gap:0.5rem; }}

/* SIDEBAR: width only when expanded → collapsing reflows the main page */
section[data-testid="stSidebar"][aria-expanded="true"] {{ min-width:250px; max-width:250px; }}
section[data-testid="stSidebar"] {{ background:#0E121A; border-right:1px solid {GRID}; }}
section[data-testid="stSidebar"] .block-container {{ padding-top:0.6rem; }}
[data-testid="stSidebar"] * {{ font-size:0.78rem; }}

/* strip default chrome (keep header so the sidebar collapse arrow stays) */
#MainMenu, footer {{ visibility:hidden; }}
header[data-testid="stHeader"] {{ background:transparent; }}

/* headings → terminal section labels */
h2, h3 {{ font-size:0.74rem !important; text-transform:uppercase; letter-spacing:0.09em;
         color:{SUB} !important; font-weight:600; margin:0.3rem 0 0.15rem 0 !important; }}

/* custom header bar */
.term-head {{ display:flex; justify-content:space-between; align-items:center;
   border-bottom:1px solid {GRID}; padding:0.1rem 0 0.5rem 0; margin-bottom:0.4rem; }}
.term-title {{ font-size:1.0rem; font-weight:700; letter-spacing:0.12em; color:#E6EDF3; }}
.term-title .dot {{ color:{GREEN}; }}
.term-meta {{ font-size:0.7rem; color:{SUB}; letter-spacing:0.04em; }}
.term-live {{ color:{GREEN}; }}

/* metric tiles → terminal panels */
[data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {GRID}; border-radius:3px;
   padding:6px 9px; }}
[data-testid="stMetricValue"] {{ font-size:1.0rem; font-weight:700; color:#E6EDF3; }}
[data-testid="stMetricLabel"] {{ font-size:0.66rem; text-transform:uppercase;
   letter-spacing:0.05em; color:{SUB}; }}
[data-testid="stMetricDelta"] {{ font-size:0.72rem; }}

/* charts → bordered panels */
[data-testid="stPlotlyChart"] {{ border:1px solid {GRID}; border-radius:3px;
   background:{PANEL}; padding:2px; }}

/* dataframe panel */
[data-testid="stDataFrame"] {{ border:1px solid {GRID}; border-radius:3px; }}

/* tabs → terminal nav */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:0; border-bottom:1px solid {GRID}; }}
[data-testid="stTabs"] [data-baseweb="tab"] {{ font-size:0.72rem; text-transform:uppercase;
   letter-spacing:0.05em; color:{SUB}; padding:5px 11px; }}
[data-testid="stTabs"] [aria-selected="true"] {{ color:{GREEN};
   border-bottom:2px solid {GREEN}; background:transparent; }}

/* captions */
[data-testid="stCaptionContainer"] {{ color:#56606A; font-size:0.68rem; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PLOTLY THEME HELPER
# ---------------------------------------------------------------------------
def styled(fig, h=None, legend=True):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=PANEL,
        font=dict(family=MONO, size=10.5, color=TXT),
        colorway=SERIES, margin=dict(l=8, r=8, t=34, b=8),
        title=dict(font=dict(size=11, color=TXT)),
        legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)",
                    orientation="h", y=1.02, x=0) if legend else dict(),
        hoverlabel=dict(font=dict(family=MONO, size=10)),
        showlegend=legend,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(size=9.5))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(size=9.5))
    if h:
        fig.update_layout(height=h)
    return fig


# ---------------------------------------------------------------------------
# DATA LOADERS
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_history(tickers, ttl_bust):
    return yf.download(tickers, period="5y", interval="1d", progress=False)["Close"].copy()

@st.cache_data(show_spinner=False)
def load_live(tickers, period, interval, ttl_bust):
    return yf.download(tickers, period=period, interval=interval, progress=False)["Close"].copy()

@st.cache_data(show_spinner=False)
def fetch_eia(series_id, api_key, ttl_bust):
    url = f"https://api.eia.gov/v2/seriesid/{series_id}"
    r = requests.get(url, params={"api_key": api_key}, timeout=25)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["response"]["data"])
    df["period"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values("period")
    return pd.Series(df["value"].values, index=df["period"])

def rename_order(df, mapping):
    df = df.rename(columns={t: n for n, t in mapping.items()})
    return df[[n for n in mapping if n in df.columns]].ffill().dropna(how="all")


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def pct_change_n(s, n):
    s = s.dropna()
    return np.nan if len(s) <= n else (s.iloc[-1] - s.iloc[-1 - n]) / s.iloc[-1 - n] * 100

def ytd_change(s):
    s = s.dropna()
    if s.empty: return np.nan
    yr = s[s.index.year == s.index[-1].year]
    return np.nan if yr.empty else (s.iloc[-1] - yr.iloc[0]) / yr.iloc[0] * 100

def max_drawdown(price):
    price = price.dropna()
    return np.nan if price.empty else (price / price.cummax() - 1).min() * 100

def rsi(s, n=14):
    d = s.diff()
    ru = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    rd = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd.replace(0, np.nan))

def gr_style(df, cols, fmt="{:.2f}"):
    def gr(v):
        if pd.isna(v): return f"color:{SUB}"
        return f"color:{GREEN}" if v > 0 else f"color:{RED}" if v < 0 else f"color:{TXT}"
    return df.style.map(gr, subset=cols).format(fmt, subset=cols, na_rep="—")


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
st.sidebar.markdown(f"<div style='font-weight:700;letter-spacing:0.1em;color:#E6EDF3;"
                    f"font-size:0.8rem;margin-bottom:0.3rem'>▌ CONTROLS</div>",
                    unsafe_allow_html=True)

with st.sidebar.expander("ASSETS", expanded=True):
    picked_comm = st.multiselect("Commodities", list(COMMODITIES), default=list(COMMODITIES))
    picked_macro = st.multiselect("Macro inputs", list(MACRO), default=MACRO_DEFAULT)

with st.sidebar.expander("LIVE FEED", expanded=False):
    timeframe = st.selectbox("Intraday timeframe",
        ["1 Day (1-min)", "5 Days (5-min)", "1 Month (1-hour)",
         "6 Months (daily)", "1 Year (daily)"], index=1)

with st.sidebar.expander("ANALYSIS", expanded=False):
    lb = st.select_slider("History window", options=list(LOOKBACK_YEARS), value="3y")

with st.sidebar.expander("ALERTS", expanded=False):
    rsi_ob = st.slider("RSI overbought ≥", 60, 90, 70)
    rsi_os = st.slider("RSI oversold ≤", 10, 40, 30)
    z_thr = st.slider("|z-score| alert ≥", 1.0, 3.0, 2.0, step=0.5)
    move_thr = st.slider("Daily move alert ≥ %", 1.0, 10.0, 3.0, step=0.5)

with st.sidebar.expander("EIA KEY (Energy tab)", expanded=False):
    eia_key = st.text_input("EIA API key", type="password",
                            help="Free at eia.gov/opendata/register.php").strip()

with st.sidebar.expander("REFRESH", expanded=False):
    auto = st.toggle("Auto-refresh", value=True)
    every = st.slider("Every (seconds)", 15, 300, 60, step=15)
    if st.button("Refresh now", use_container_width=True):
        st.cache_data.clear(); st.rerun()

TF = {"1 Day (1-min)": ("1d", "1m"), "5 Days (5-min)": ("5d", "5m"),
      "1 Month (1-hour)": ("1mo", "1h"), "6 Months (daily)": ("6mo", "1d"),
      "1 Year (daily)": ("1y", "1d")}
period, interval = TF[timeframe]
tick = st_autorefresh(interval=every * 1000, key="datarefresh") if auto else 0
ttl_bucket_live = int(time.time() // every)
ttl_bucket_hist = int(time.time() // 3600)

if not picked_comm:
    st.warning("Pick at least one commodity in the sidebar."); st.stop()

# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------
all_map = {**{k: COMMODITIES[k] for k in picked_comm},
           **{k: MACRO[k] for k in picked_macro}}
with st.spinner("Fetching market data…"):
    hist_full = rename_order(load_history(tuple(all_map.values()), ttl_bucket_hist), all_map)
    live = rename_order(load_live(tuple(all_map.values()), period, interval, ttl_bucket_live), all_map)

hist = hist_full.tail(int(LOOKBACK_YEARS[lb] * TRADING_DAYS) + 5)
comm_cols = [c for c in picked_comm if c in hist.columns]
macro_cols = [c for c in picked_macro if c in hist.columns]
rets = hist.pct_change()
comm_rets = rets[comm_cols].dropna(how="all")

# ---- precompute snapshot / signals / alerts -------------------------------
snap = pd.DataFrame([{
    "Commodity": n, "Price": round(hist_full[n].dropna().iloc[-1], 2),
    "1D %": pct_change_n(hist_full[n], 1), "1W %": pct_change_n(hist_full[n], 5),
    "1M %": pct_change_n(hist_full[n], 21), "3M %": pct_change_n(hist_full[n], 63),
    "YTD %": ytd_change(hist_full[n]), "1Y %": pct_change_n(hist_full[n], TRADING_DAYS),
} for n in comm_cols])

sig_rows = []
for name in comm_cols:
    s = hist_full[name].dropna()
    if len(s) < 60: continue
    price = s.iloc[-1]
    ma50 = s.rolling(50).mean().iloc[-1]
    ma200 = s.rolling(200).mean().iloc[-1] if len(s) >= 200 else np.nan
    vs200 = (price / ma200 - 1) * 100 if ma200 == ma200 else np.nan
    trend = ("▲ Up" if (ma50 == ma50 and ma200 == ma200 and ma50 > ma200)
             else "▼ Down" if (ma50 == ma50 and ma200 == ma200) else "–")
    mom = (s.iloc[-21] / s.iloc[-TRADING_DAYS] - 1) * 100 if len(s) >= TRADING_DAYS else np.nan
    m60, sd60 = s.rolling(60).mean().iloc[-1], s.rolling(60).std().iloc[-1]
    z = (price - m60) / sd60 if sd60 else np.nan
    sig_rows.append({"Commodity": name, "Trend": trend,
                     "% vs 200d": round(vs200, 1) if vs200 == vs200 else np.nan,
                     "12-1 Mom %": round(mom, 1) if mom == mom else np.nan,
                     "Z (60d)": round(z, 2) if z == z else np.nan,
                     "RSI(14)": round(rsi(s).iloc[-1], 0)})
sig = pd.DataFrame(sig_rows)

alerts = []
for _, r in sig.iterrows():
    name = r["Commodity"]; rsiv, z = r["RSI(14)"], r["Z (60d)"]
    d1 = snap.loc[snap["Commodity"] == name, "1D %"].iloc[0]
    if pd.notna(rsiv) and rsiv >= rsi_ob: alerts.append((name, "RSI overbought", f"RSI {rsiv:.0f}", "high"))
    if pd.notna(rsiv) and rsiv <= rsi_os: alerts.append((name, "RSI oversold", f"RSI {rsiv:.0f}", "high"))
    if pd.notna(z) and abs(z) >= z_thr: alerts.append((name, "Stretched", f"z {z:+.2f}", "high"))
    if pd.notna(d1) and abs(d1) >= move_thr: alerts.append((name, "Big daily move", f"{d1:+.2f}% today", "med"))

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
last_ts = live.index[-1] if not live.empty else hist.index[-1]
live_dot = "● LIVE" if auto else "○ paused"
st.markdown(f"""
<div class="term-head">
  <div class="term-title"><span class="dot">◢</span> COMMODITIES QUANT TERMINAL</div>
  <div class="term-meta"><span class="term-live">{live_dot}</span> &nbsp;·&nbsp; {timeframe}
     &nbsp;·&nbsp; {lb} window &nbsp;·&nbsp; {last_ts:%Y-%m-%d %H:%M}
     &nbsp;·&nbsp; Yahoo (~15m delayed)</div>
</div>
""", unsafe_allow_html=True)
if alerts:
    st.markdown(
        f"<div style='border:1px solid {RED};background:rgba(220,38,38,0.10);border-radius:3px;"
        f"padding:5px 9px;font-size:0.74rem;color:#E6EDF3;margin-bottom:0.3rem'>"
        f"<b style='color:{RED}'>⚠ {len(alerts)} ALERT(S)</b> &nbsp; "
        + " &nbsp;|&nbsp; ".join(f"{n}: {t} ({d})" for n, t, d, _ in alerts)
        + "</div>", unsafe_allow_html=True)

(t_overview, t_perf, t_signals, t_alerts, t_corr,
 t_macro, t_energy, t_season) = st.tabs(
    ["Overview", "Performance & Risk", "Signals", "Alerts", "Correlations",
     "Macro", "Energy (EIA)", "Seasonality"])

# ---- OVERVIEW -------------------------------------------------------------
with t_overview:
    st.subheader("Live prices")
    ncol = min(6, len(comm_cols)); cols = st.columns(ncol)
    for i, name in enumerate(comm_cols):
        s = live[name].dropna() if name in live.columns else pd.Series(dtype=float)
        if s.empty: continue
        delta = (s.iloc[-1] - s.iloc[0]) / s.iloc[0] * 100 if len(s) > 1 else 0
        cols[i % ncol].metric(name, f"{s.iloc[-1]:,.2f}", f"{delta:+.2f}%")

    st.subheader("Snapshot — returns")
    st.dataframe(gr_style(snap, ["1D %", "1W %", "1M %", "3M %", "YTD %", "1Y %"]),
                 use_container_width=True, hide_index=True)

    st.subheader("Live chart")
    c0, c1 = st.columns([4, 1])
    pick = c0.selectbox("Commodity", comm_cols, key="livechart", label_visibility="collapsed")
    show_ma = c1.checkbox("MA20", value=True)
    s = live[pick].dropna()
    up = s.iloc[-1] >= s.iloc[0] if len(s) > 1 else True
    fig = go.Figure(go.Scatter(x=s.index, y=s, name=pick,
                               line=dict(color=GREEN if up else RED, width=1.4)))
    if show_ma:
        fig.add_trace(go.Scatter(x=s.index, y=s.rolling(20).mean(), name="MA20",
                                 line=dict(color=SUB, width=1, dash="dot")))
    st.plotly_chart(styled(fig, h=400), use_container_width=True)

# ---- PERFORMANCE & RISK ---------------------------------------------------
with t_perf:
    st.subheader(f"Relative performance — rebased to 100 ({lb})")
    norm = hist[comm_cols] / hist[comm_cols].bfill().iloc[0] * 100
    pf = go.Figure()
    for name in comm_cols:
        pf.add_trace(go.Scatter(x=norm.index, y=norm[name], name=name))
    st.plotly_chart(styled(pf, h=420), use_container_width=True)

    st.subheader("Performance heatmap (% return by period)")
    periods = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": TRADING_DAYS}
    hm = pd.DataFrame({p: [pct_change_n(hist_full[n], d) for n in comm_cols]
                       for p, d in periods.items()}, index=comm_cols)
    phm = go.Figure(go.Heatmap(z=hm.values, x=list(periods), y=comm_cols, colorscale=RYG,
                               zmid=0, text=np.round(hm.values, 1), texttemplate="%{text}",
                               textfont=dict(size=11, color=TXT),
                               colorbar=dict(thickness=6, outlinewidth=0)))
    st.plotly_chart(styled(phm, h=340, legend=False), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Rolling 30d annualized vol %")
        rv = comm_rets.rolling(30).std() * np.sqrt(TRADING_DAYS) * 100
        vf = go.Figure()
        for name in comm_cols:
            vf.add_trace(go.Scatter(x=rv.index, y=rv[name], name=name, line=dict(width=1.0)))
        st.plotly_chart(styled(vf, h=340), use_container_width=True)
    with c2:
        st.subheader("Drawdowns %")
        ddf = go.Figure()
        for name in comm_cols:
            p = hist[name].dropna()
            ddf.add_trace(go.Scatter(x=p.index, y=(p / p.cummax() - 1) * 100, name=name, line=dict(width=1.0)))
        st.plotly_chart(styled(ddf, h=340), use_container_width=True)

    st.subheader(f"Risk / return metrics (annualized, {lb}, rf = 0)")
    mrows = []
    for name in comm_cols:
        r = comm_rets[name].dropna()
        if r.empty: continue
        ann_ret = r.mean() * TRADING_DAYS * 100
        ann_vol = r.std() * np.sqrt(TRADING_DAYS) * 100
        downside = r[r < 0].std() * np.sqrt(TRADING_DAYS) * 100
        mrows.append({"Commodity": name, "Ann Return %": round(ann_ret, 1),
                      "Ann Vol %": round(ann_vol, 1),
                      "Sharpe": round(ann_ret / ann_vol, 2) if ann_vol else np.nan,
                      "Sortino": round(ann_ret / downside, 2) if downside else np.nan,
                      "Max DD %": round(max_drawdown(hist[name]), 1),
                      "Skew": round(r.skew(), 2), "Kurtosis": round(r.kurtosis(), 2)})
    st.dataframe(gr_style(pd.DataFrame(mrows),
                 ["Ann Return %", "Sharpe", "Sortino", "Max DD %"]),
                 use_container_width=True, hide_index=True)

# ---- SIGNALS --------------------------------------------------------------
with t_signals:
    st.subheader("Quant signal screen")
    st.caption("Trend (golden/death cross, dist. from 200d) · 12-1 momentum · "
               "z-score (price vs 60d) · RSI(14). Educational only.")
    def color_signal(col):
        out = []
        for v in col:
            if pd.isna(v): out.append(f"color:{SUB}"); continue
            if col.name in ("% vs 200d", "12-1 Mom %"):
                out.append(f"color:{GREEN}" if v > 0 else f"color:{RED}")
            elif col.name == "Z (60d)":
                out.append("background-color:rgba(220,38,38,0.22)" if abs(v) >= 2
                           else "background-color:rgba(234,179,8,0.18)" if abs(v) >= 1 else "")
            elif col.name == "RSI(14)":
                out.append("background-color:rgba(220,38,38,0.22)" if (v >= 70 or v <= 30) else "")
            else: out.append("")
        return out
    st.dataframe(sig.style.apply(color_signal,
                 subset=["% vs 200d", "12-1 Mom %", "Z (60d)", "RSI(14)"])
                 .format({"% vs 200d": "{:.1f}", "12-1 Mom %": "{:.1f}",
                          "Z (60d)": "{:.2f}", "RSI(14)": "{:.0f}"}, na_rep="—"),
                 use_container_width=True, hide_index=True)
    st.caption("Z ≥ |2| stretched (red), |1–2| elevated (amber). RSI ≥70 / ≤30 (red).")

    st.subheader("12-1 momentum ranking")
    mser = sig.dropna(subset=["12-1 Mom %"]).sort_values("12-1 Mom %")
    bar = go.Figure(go.Bar(x=mser["12-1 Mom %"], y=mser["Commodity"], orientation="h",
                           marker_color=[RED if v < 0 else GREEN for v in mser["12-1 Mom %"]]))
    st.plotly_chart(styled(bar, h=max(280, 34 * len(mser)), legend=False),
                    use_container_width=True)

# ---- ALERTS ---------------------------------------------------------------
with t_alerts:
    st.subheader("Triggered alerts")
    st.caption("Adjust thresholds in sidebar → ALERTS. Re-evaluated on every refresh.")
    if not alerts:
        st.success("No alerts triggered with the current thresholds.")
    else:
        adf = pd.DataFrame(alerts, columns=["Commodity", "Signal", "Detail", "Severity"])
        def sev(col):
            return ["background-color:rgba(220,38,38,0.22)" if v == "high"
                    else "background-color:rgba(234,179,8,0.18)" for v in col]
        st.dataframe(adf.style.apply(sev, subset=["Severity"]),
                     use_container_width=True, hide_index=True)
    st.markdown(f"<span style='color:{SUB};font-size:0.72rem'>Thresholds: RSI ≥{rsi_ob} / ≤{rsi_os}"
                f" · |z| ≥{z_thr} · daily move ≥{move_thr}%</span>", unsafe_allow_html=True)

# ---- CORRELATIONS ---------------------------------------------------------
with t_corr:
    st.subheader("Correlation of daily returns (commodities + macro)")
    corr = rets[comm_cols + macro_cols].dropna().corr().round(2)
    hf = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1,
                              colorscale=RG_SCALE, zmid=0, text=corr.values, texttemplate="%{text}",
                              textfont=dict(size=10, color=TXT),
                              colorbar=dict(thickness=8, outlinewidth=0)))
    st.plotly_chart(styled(hf, h=600, legend=False), use_container_width=True)

    st.subheader("Rolling correlation (pick any pair)")
    allcols = comm_cols + macro_cols
    c1, c2, c3 = st.columns(3)
    a = c1.selectbox("Asset A", allcols, index=0)
    b = c2.selectbox("Asset B", allcols,
                     index=allcols.index("US Dollar") if "US Dollar" in allcols else min(1, len(allcols) - 1))
    win = c3.slider("Window (days)", 20, 180, 60, step=10)
    if a != b:
        rc = go.Figure(go.Scatter(x=rets.index, y=rets[a].rolling(win).corr(rets[b]),
                                  line=dict(color=SERIES[0])))
        rc.add_hline(y=0, line_dash="dot", line_color=SUB)
        rc.update_layout(title=f"{a} vs {b} — {win}d rolling correlation", yaxis_range=[-1, 1])
        st.plotly_chart(styled(rc, h=380, legend=False), use_container_width=True)
    else:
        st.info("Pick two different assets.")

# ---- MACRO ----------------------------------------------------------------
with t_macro:
    st.subheader("Macro factor betas (multivariate OLS of daily returns)")
    if macro_cols:
        joined = rets[comm_cols + macro_cols].dropna()
        X = np.column_stack([np.ones(len(joined)), joined[macro_cols].values])
        brows = []
        for name in comm_cols:
            y = joined[name].values
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            yhat = X @ coef
            ss_res = np.sum((y - yhat) ** 2); ss_tot = np.sum((y - y.mean()) ** 2)
            row = {"Commodity": name}
            for j, m in enumerate(macro_cols):
                row[f"β {m}"] = round(coef[j + 1], 2)
            row["R²"] = round(1 - ss_res / ss_tot, 2) if ss_tot else np.nan
            brows.append(row)
        betas = pd.DataFrame(brows)
        st.dataframe(gr_style(betas, [c for c in betas.columns if c.startswith("β")]),
                     use_container_width=True, hide_index=True)
        st.caption("β = sensitivity to a 1-unit move in the factor's daily return. "
                   "R² = variance explained by the macro set.")
        st.subheader("Beta profile — pick a commodity")
        who = st.selectbox("Commodity", comm_cols, key="betapick", label_visibility="collapsed")
        brow = betas[betas["Commodity"] == who].iloc[0]
        bcols = [c for c in betas.columns if c.startswith("β")]
        bvals = [brow[c] for c in bcols]
        bar = go.Figure(go.Bar(x=[c[2:] for c in bcols], y=bvals,
                               marker_color=[RED if v < 0 else GREEN for v in bvals]))
        bar.update_layout(title=f"{who} — sensitivity to macro factors")
        st.plotly_chart(styled(bar, h=340, legend=False), use_container_width=True)
    else:
        st.info("Select some macro inputs in the sidebar to see factor betas.")

# ---- ENERGY (EIA) ---------------------------------------------------------
with t_energy:
    st.subheader("Energy fundamentals — EIA weekly data")
    if not eia_key:
        st.info("**Add a free EIA API key to unlock this tab.**  "
                "1) Register (~1 min): https://www.eia.gov/opendata/register.php  "
                "2) Key arrives by email.  3) Paste it in the sidebar → **EIA KEY**.  "
                "Then: U.S. crude/gasoline/distillate inventories, crude production, "
                "refinery utilization, and nat-gas storage.")
    else:
        chosen = st.multiselect("Series", list(EIA_SERIES), default=EIA_DEFAULT)
        if not chosen:
            st.info("Pick at least one EIA series above.")
        else:
            cols = st.columns(min(4, len(chosen)))
            series_cache = {}
            for i, label in enumerate(chosen):
                sid, units = EIA_SERIES[label]
                try:
                    s = fetch_eia(sid, eia_key, ttl_bucket_hist)
                    series_cache[label] = s
                    wow = s.iloc[-1] - s.iloc[-2] if len(s) > 1 else 0
                    cols[i % len(cols)].metric(label, f"{s.iloc[-1]:,.0f}", f"{wow:+,.0f} WoW")
                except Exception as e:
                    cols[i % len(cols)].error(f"{label}: {e}")

            st.subheader("Chart")
            c0, c1 = st.columns([4, 1])
            chart_pick = c0.selectbox("Series", list(series_cache),
                                      label_visibility="collapsed") if series_cache else None
            overlay = c1.checkbox("Overlay WTI", value=True)
            if chart_pick:
                s = series_cache[chart_pick]
                ef = make_subplots(specs=[[{"secondary_y": True}]])
                ef.add_trace(go.Scatter(x=s.index, y=s, name=chart_pick,
                                        line=dict(color=SERIES[0])), secondary_y=False)
                if overlay and "WTI Crude" in hist_full.columns:
                    w = hist_full["WTI Crude"].reindex(s.index, method="nearest")
                    ef.add_trace(go.Scatter(x=w.index, y=w, name="WTI ($/bbl)",
                                            line=dict(color=RED, width=1)), secondary_y=True)
                ef.update_layout(title=chart_pick)
                ef.update_yaxes(title_text=EIA_SERIES[chart_pick][1], secondary_y=False,
                                gridcolor=GRID)
                ef.update_yaxes(title_text="WTI $/bbl", secondary_y=True, gridcolor=GRID)
                st.plotly_chart(styled(ef, h=420), use_container_width=True)
            st.caption("Source: EIA v2 API. Inventory builds vs price = bearish supply; draws = bullish.")

# ---- SEASONALITY ----------------------------------------------------------
with t_season:
    st.subheader("Seasonality — average monthly return % (full 5y history)")
    monthly = hist_full[comm_cols].resample("ME").last().pct_change() * 100
    mn = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    seas = monthly.groupby(monthly.index.month).mean().reindex(range(1, 13))
    seas.index = mn
    sf = go.Figure(go.Heatmap(z=seas.T.values, x=mn, y=comm_cols, colorscale=RG_SCALE,
                              zmid=0, text=np.round(seas.T.values, 1), texttemplate="%{text}",
                              textfont=dict(size=11, color=TXT),
                              colorbar=dict(thickness=8, outlinewidth=0)))
    st.plotly_chart(styled(sf, h=460, legend=False), use_container_width=True)
    st.caption("Average % change in each calendar month over the last 5 years.")