"""China Foreign Rhetoric Observatory — Page 1: Global map. Offline MVP."""
import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (load_scores, MEASURES, METHODOLOGY, ISO3, WINDOW,
                   cusum_series, alert_for, kperiod_alarm, z_alert, last_updated,
                   recent_titles, negative_titles, mobile_css)

st.set_page_config(page_title="China Foreign Rhetoric Observatory", layout="wide")
mobile_css()

st.title("China Foreign Rhetoric Observatory")
st.caption("Tracking China's official diplomatic signaling across bilateral relations · "
           "People's Daily corpus 1950–2026")
st.caption(f"Data coverage through **{last_updated()}** · 12 great powers · updated daily.")

with st.sidebar:
    st.header("Controls")
    resolution = st.radio("Aggregation", list(WINDOW.keys()), index=2)
    measure = st.selectbox("Index", list(MEASURES.keys()),
                           format_func=lambda k: MEASURES[k],
                           index=list(MEASURES).index("negativity"))

df = load_scores(resolution)
latest = df["period"].max()
cur = df[df["period"] == latest].copy()
cur["iso3"] = cur["country"].map(ISO3)

# --- metric cards ---
def global_avg(periods_back):
    ps = sorted(df["period"].unique())[-periods_back:]
    return df[df["period"].isin(ps)][measure].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Global index ({latest.date()})", f"{cur[measure].mean():.3f}")
c2.metric("3-period avg", f"{global_avg(3):.3f}")
c3.metric("5-period avg", f"{global_avg(5):.3f}")
c4.metric("Countries monitored", f"{cur['country'].nunique()}")

# --- bubble map: recent trailing-window average (single periods are too sparse to vary) ---
# colour = score, size = article volume; equal visual weight per country, no area distortion
MAPWIN = {"Daily": 90, "Weekly": 26, "Monthly": 12, "Yearly": 5}[resolution]
LATLON = {  # representative on-land centroids, for placing the bubbles
    "US": (39.5, -98.4), "Russia": (60.0, 95.0), "Japan": (36.5, 138.0), "UK": (53.0, -1.5),
    "France": (46.5, 2.5), "India": (22.5, 79.0), "Germany": (51.0, 10.0), "Vietnam": (16.0, 106.5),
    "South Korea": (36.5, 127.8), "Australia": (-25.0, 134.0), "Indonesia": (-2.0, 118.0),
    "Pakistan": (30.0, 69.5)}
recent_periods = sorted(df["period"].unique())[-MAPWIN:]
mp = (df[df["period"].isin(recent_periods)]
      .groupby("country", as_index=False).agg({measure: "mean", "n_art": "sum"}))
mp["lat"] = mp["country"].map(lambda c: LATLON.get(c, (None, None))[0])
mp["lon"] = mp["country"].map(lambda c: LATLON.get(c, (None, None))[1])
# dynamic gradient: spread color across the 5th–95th percentile of the displayed values
lo, hi = mp[measure].quantile(0.05), mp[measure].quantile(0.95)
if not (hi > lo):
    hi = max(mp[measure].max(), 1e-9); lo = min(mp[measure].min(), 0.0)
st.subheader(f"{MEASURES[measure]} — last {MAPWIN} {resolution.lower()} periods (avg)")

# most-recent + the single most-negative headline per country (Chinese + English), for the map hover
_titles = recent_titles(2)
_neg = negative_titles(1)
def _clip(s, k):
    s = s or ""
    return s[:k] + "…" if len(s) > k else s
def _fmt(d, zh, en, tag=""):
    line = f"· {_clip(zh, 28)}{tag} <i>({d})</i>"
    if en:
        line += f"<br>&nbsp;&nbsp;<i>{_clip(en, 60)}</i>"
    return line
def _headlines(ctry):
    rec = _titles.get(ctry, [])
    neg = _neg.get(ctry, [])
    parts = []
    parts.append("<i>Most recent</i><br>" +
                 ("<br>".join(_fmt(d, zh, en) for d, zh, en, _u in rec) if rec else "—"))
    if neg:
        d, zh, en, s, summ, _u = neg[0]
        block = "<i>Most negative (last 7 days)</i><br>" + _fmt(d, zh, en, f" <b>[{s:.2f}]</b>")
        if summ:
            block += f"<br>&nbsp;&nbsp;{_clip(summ, 110)}"
        parts.append(block)
    return "<br><br>".join(parts)
mp["headlines"] = mp["country"].map(_headlines)

fig = px.scatter_geo(mp, lat="lat", lon="lon", color=measure, size="n_art",
                     hover_name="country", custom_data=["country", measure, "headlines", "n_art"],
                     color_continuous_scale="YlOrRd", range_color=(lo, hi), size_max=34)
fig.update_traces(marker=dict(line=dict(width=0.8, color="rgba(40,40,40,0.55)"), sizemin=5),
                  hovertemplate=(
    "<b>%{customdata[0]}</b><br>"
    f"{MEASURES[measure]}: " + "%{customdata[1]:.2f}"
    "   ·   %{customdata[3]} articles<br>"
    "<br>%{customdata[2]}<extra></extra>"))
fig.update_geos(projection_type="natural earth", showframe=False,
                showland=True, landcolor="#eceef0", showcountries=True, countrycolor="white",
                showcoastlines=False, showocean=False, lataxis_range=[-56, 84],
                bgcolor="rgba(0,0,0,0)")
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), hoverlabel=dict(align="left"))
st.caption("Bubble **size** = number of monitored articles in the window; **colour** = score "
           "(5th–95th-percentile range). **Hover** to preview · **click a bubble** to open its articles.")
_evt = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="worldmap")

# clicking a bubble opens a panel with CLICKABLE article links (hover tooltips can't hold links)
def _clicked_country(evt):
    pts = (evt or {}).get("selection", {}).get("points", []) if isinstance(evt, dict) else \
          getattr(getattr(evt, "selection", None), "points", []) or []
    if not pts:
        return None
    p = pts[0]
    cd = p.get("customdata")
    if cd:
        return cd[0]
    idx = p.get("point_index", p.get("point_number"))
    return mp.iloc[idx]["country"] if (idx is not None and idx < len(mp)) else None

_clicked = _clicked_country(_evt)
_countries = sorted(mp["country"])
_default = (_countries.index(_clicked) + 1) if _clicked in _countries else 0
_sel = st.selectbox("Open a country's articles (or click a bubble above)", ["—"] + _countries,
                    index=_default)
_sel = _clicked or (_sel if _sel != "—" else None)
if _sel:
    with st.container(border=True):
        st.markdown(f"**{_sel} — open on People's Daily**  ·  *click a title*")
        for d, zh, en, url in _titles.get(_sel, []):
            lab = en or zh
            st.markdown(f"- [{lab}]({url}) · *{d}* · <span style='color:grey'>{zh}</span>"
                        if url else f"- {lab} · *{d}*", unsafe_allow_html=True)
        for d, zh, en, s, summ, url in _neg.get(_sel, []):
            lab = en or zh
            head = f"- 🔴 **[{s:.2f}]** [{lab}]({url}) · *{d}*" if url else f"- 🔴 **[{s:.2f}]** {lab} · *{d}*"
            st.markdown(head + (f" — {summ}" if summ else ""))

left, right = st.columns(2)
# --- top 5 ---
with left:
    st.subheader(f"Top 5 — recent {MAPWIN}-period average")
    st.caption("Mean over the same trailing window as the map (not a single latest period, which is noisy).")
    top = mp.sort_values(measure, ascending=False).head(5)
    bar = px.bar(top, x=measure, y="country", orientation="h", color=measure,
                 color_continuous_scale="RdBu_r")
    bar.update_layout(margin=dict(l=0, r=0, t=0, b=0), yaxis=dict(autorange="reversed"),
                      coloraxis_showscale=False)
    st.plotly_chart(bar, use_container_width=True)

# --- alarm board: 3-period + 5-period (standardized exceedance) + CUSUM ---
with right:
    st.subheader("Alarm status")
    st.caption("How far each country sits above **its own** baseline (standardized, so countries are comparable). "
               "**Short-run** & **Sustained** = jump over the last 3 / 5 periods, in SD "
               "(<span style='color:#e08214'>amber ≥2σ</span>, <span style='color:#b2182b'>red ≥3σ</span>); "
               "**Drift** = accumulating deviation (amber >3, red >5). Full method on the **About** page.",
               unsafe_allow_html=True)
    rows = []
    for ctry, g in df.groupby("country"):
        s = g[measure].reset_index(drop=True)
        a3, a5 = kperiod_alarm(s, 3, WINDOW[resolution]), kperiod_alarm(s, 5, WINDOW[resolution])
        cu = cusum_series(s, WINDOW[resolution])[-1] if len(s) else 0.0
        rows.append((ctry, a3, a5, cu))
    rows.sort(key=lambda r: -max(r[2], r[3] / 5))   # rank by 5-period alarm (CUSUM scaled in)

    def badge(label, color, tip=""):
        t = f" title=\"{tip}\"" if tip else ""
        return (f"<span{t} style='background:{color};color:white;padding:1px 7px;border-radius:9px;"
                f"font-size:0.72em;cursor:default'>{label}</span>")
    TIP3 = ("Short-run signal: average of the last 3 periods, expressed in standard deviations "
            "above the country's own EWMA baseline. Amber at 2σ, red at 3σ.")
    TIP5 = ("Sustained signal: same measure over the last 5 periods, so a single spike counts less. "
            "Amber at 2σ, red at 3σ.")
    TIPC = ("Drift (CUSUM): running total of period-by-period deviations above baseline — flags a slow, "
            "persistent climb even when no single period is extreme. Amber above 3, red above 5.")
    for ctry, a3, a5, cu in rows:
        s3, c3 = z_alert(a3); s5, c5 = z_alert(a5); sc, cc = alert_for(cu)
        st.markdown(
            f"<span style='display:inline-block;width:96px'>{ctry}</span>"
            f"{badge(f'Short-run {a3:.1f}σ', c3, TIP3)} "
            f"{badge(f'Sustained {a5:.1f}σ', c5, TIP5)} "
            f"{badge(f'Drift {cu:.1f}', cc, TIPC)}",
            unsafe_allow_html=True)

st.divider()
st.caption(f"**Methodology — {MEASURES[measure]}.** {METHODOLOGY[measure]}  "
           "Empty period (0 articles) is scored 0. Alerts: CUSUM>3 yellow, >5 red, "
           f"baseline window = {WINDOW[resolution]} {resolution.lower()} periods.")
st.caption("Implicit Threat Index from Wong JSH. Forecasting the use of force: a word embedding analysis "
           "of China's rhetoric and military escalations. *Political Science Research and Methods*. "
           "Published online 2026:1-10. doi:10.1017/psrm.2025.10085")
