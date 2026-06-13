"""Page 4: About & Methodology."""
import streamlit as st
from utils import MEASURES, METHODOLOGY, last_updated

st.set_page_config(page_title="About · Observatory", layout="wide")
st.title("About & Methodology")

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
- **Alarms** are *standardized* (comparable across countries): **3- and 5-period exceedance** =
  SD of the recent average above the country's own EWMA baseline (yellow ≥ 2σ, red ≥ 3σ); **CUSUM** flags
  sustained drift (yellow > 3, red > 5). "More alarming" means a country is departing from *its own* norm,
  not that its raw level is highest.
- Map colours a **trailing-window average** (single recent days are too sparse) on a dynamic 5–95th-percentile range.
""")

st.subheader("Validation")
st.markdown("""
- **Convergent validity** vs the Tsinghua *China–great-power relations* score (Yan Xuetong; external
  benchmark): the implicit-threat indices correlate **negatively** with relations across all 12 powers
  (yearly, DeepSeek e.g. US −0.79, France −0.72; LSS mean −0.65) — worse relations ⇒ more threat signaling.
- **Inter-method reliability** across the four implicit-threat coders: Krippendorff's α ≈ 0.43 (moderate);
  LSS most consistent. The measures are **distinct from general tone** (e.g. China's force-signaling tracks
  relations tightly for the US but only spikes at the 1969 clash for the USSR).
- Implicit-threat lexicon: Wong, *Forecasting the Use of Force: A Word Embedding Analysis of China's
  Rhetoric and Military Escalations*, **Political Science Research and Methods**.
""")

st.subheader("Caveats")
st.markdown("""
- Implicit-threat idioms are **rare** (~2% of articles), so short windows and small-N periods are noisy —
  read levels with the article count in mind.
- The 2025-12 → 2026 backfill reconstructs the summary step (the original summary prompt was unavailable);
  classify, framing, and implicit-threat prompts are applied **verbatim** to the original pipeline.
- Source: *People's Daily* digital edition. **Article-level text is not published** (copyright); only
  derived aggregate scores are shown.
""")
