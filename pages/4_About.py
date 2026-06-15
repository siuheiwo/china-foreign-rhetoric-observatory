"""Page 4: About & Methodology."""
import streamlit as st
from utils import MEASURES, METHODOLOGY, last_updated, mobile_css

st.set_page_config(page_title="About and Methodology · Observatory", layout="wide")
mobile_css()
st.title("About and Methodology")

st.markdown(f"""
The **China Foreign Rhetoric Observatory** tracks how China's official media (*People's Daily*) signals
coercion toward 12 major powers, **1950–{last_updated()[:4]}**. It is built for researchers and policy
analysts. All figures are **aggregate** (country × period); no article text is reproduced.
""")

st.subheader("Indices")
for k in MEASURES:
    st.markdown(f"- **{MEASURES[k]}** — {METHODOLOGY[k]}")

st.subheader("Aggregation & alerts")
st.markdown("""
- **Daily / weekly / monthly** views; a period with **0 articles for a country is scored 0**.
- Map colours a **trailing-window average** (single recent days are too sparse) on a dynamic 5–95th-percentile range.

The **Alarm status** board carries three badges per country. All three are *standardized* — measured
against **each country's own history**, so a quiet country and a noisy one are directly comparable.
"More alarming" therefore means a country is **departing from its own norm**, not that its raw level is
highest. The badges read **green = normal, amber = watch, red = alert**.

| Badge | What it measures | Amber | Red |
|---|---|---|---|
| **Short-run** *(was "3p")* | Average of the **last 3 periods**, in standard deviations (σ) above the country's EWMA baseline. Reacts fast — catches a fresh spike. | ≥ 2σ | ≥ 3σ |
| **Sustained** *(was "5p")* | Same exceedance over the **last 5 periods**. A one-off spike is diluted, so this fires only when elevation **persists**. | ≥ 2σ | ≥ 3σ |
| **Drift** *(was "CUSUM")* | A **cumulative-sum** statistic: it keeps a running total of period-by-period deviations above baseline. Flags a slow, steady climb that no single period would trigger. | > 3 | > 5 |

- **EWMA baseline** = exponentially-weighted moving average over the resolution's window, so recent
  behaviour defines "normal" and old history fades out.
- The board is **ranked** by the Sustained signal (with Drift scaled in), so the country most clearly
  breaking from its own pattern sits at the top.

#### How the alarm bar is set
The thresholds are deliberately **conservative and rule-based**, not tuned to hit a target number of alerts:

- **Why standard deviations, not raw scores.** Each country is scored against **its own** baseline and
  spread (z-score), so a number means the same thing everywhere. A "2σ" jump is, under a roughly normal
  baseline, an event in the **top ~2.5%** of that country's history; "3σ" is the **top ~0.1%**. That is the
  bar: *amber* = unusual, *red* = rare.
- **Baseline window.** "Normal" is an EWMA over the last **365 daily / 52 weekly / 24 monthly** periods, so
  the bar **moves with the country** — a country that has been loud for months resets its own normal and
  stops tripping the alarm. A minimum number of periods is required before any baseline (and thus any
  alarm) is computed, so brand-new or ultra-sparse series do not fire on noise.
- **Drift (CUSUM).** Each period contributes its z-score **minus a slack of 0.5σ** (small wiggles are
  ignored) to a running total that is floored at zero. The total only grows when a country sits *above*
  baseline period after period; **> 3** is amber, **> 5** is red. This is what catches a slow, sustained
  climb that never produces a single dramatic period.
- **Empty periods** (0 articles for a country) are scored 0, so silence pulls a country back toward — never
  above — its baseline; it cannot manufacture an alarm.

These cut-offs (2σ / 3σ; 0.5σ slack; 3 / 5 on the CUSUM) are standard statistical-process-control
defaults. They are a **screening tool to rank attention, not a forecast** — a red badge says "this country
is departing sharply from its own norm right now," which is the cue to open the country page and read why.
""")

st.subheader("Validation")
st.markdown("""
- **Convergent validity** vs the Tsinghua *China–great-power relations* score (Yan Xuetong; external
  benchmark): the implicit-threat indices correlate **negatively** with relations across all 12 powers
  (yearly, DeepSeek e.g. US −0.79, France −0.72; LSS mean −0.65) — worse relations ⇒ more threat signaling.
- **Inter-method reliability** across the four implicit-threat coders: Krippendorff's α ≈ 0.43 (moderate);
  LSS most consistent. The measures are **distinct from general tone** (e.g. China's force-signaling tracks
  relations tightly for the US but only spikes at the 1969 clash for the USSR).
- Implicit-threat lexicon: Wong JSH. Forecasting the use of force: a word embedding analysis of China's
  rhetoric and military escalations. *Political Science Research and Methods*. Published online 2026:1-10.
  doi:10.1017/psrm.2025.10085
""")

st.subheader("Caveats")
st.markdown("""
- Implicit-threat idioms are **rare** (~2% of articles), so short windows and small-N periods are noisy —
  read levels with the article count in mind.
- The 2025-12 → 2026 backfill reconstructs the summary step (the original summary prompt was unavailable);
  classify, framing, and implicit-threat prompts are applied **verbatim** to the original pipeline.
- Source: *People's Daily* digital edition. **Article body text is not republished** (copyright); the site
  shows only derived aggregate scores, plus — on the map hover — the **headline and a link** to the two most
  recent items per country on the publisher's own site.
""")
