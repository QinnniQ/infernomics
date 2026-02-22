# streamlit_app.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

REPORTS_DIR = Path("outputs/reports")
ASSETS_DIR = Path("assets")


# -----------------------------
# Page config + minimal polish
# -----------------------------
st.set_page_config(page_title="Infernomics — Dashboard", layout="wide")

st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; }
hr { border: none; border-top: 1px solid rgba(255,255,255,0.10); margin: 14px 0 22px 0; }
.small-muted { opacity: 0.75; font-size: 13px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Helpers
# -----------------------------
def latest_file(pattern: str) -> Optional[Path]:
    files = sorted(REPORTS_DIR.glob(pattern))
    return files[-1] if files else None


def load_csv(path: Optional[Path]) -> Optional[pd.DataFrame]:
    if not path or not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.error(f"Failed to read {path}: {e}")
        return None


def to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def micro(series: pd.Series) -> pd.Series:
    return series.astype(float) * 1_000_000.0


def safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def safe_int(x, default=0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def fmt_micro(x: float) -> str:
    return f"{x:.1f} µ€"


def fmt_ms(x: float) -> str:
    return f"{x:.1f} ms"


def file_link(label: str, path: Optional[Path], hint: str = "") -> None:
    if path and path.exists():
        st.markdown(f"**{label}:** [{path.name}]({path.as_posix()})", unsafe_allow_html=True)
        if hint:
            st.caption(hint)
    else:
        st.markdown(f"**{label}:** —")
        if hint:
            st.caption(hint)


def metric_grid(items: list[tuple[str, str, str]], cols: int = 2) -> None:
    # items: (label, value, help)
    for i in range(0, len(items), cols):
        row = items[i : i + cols]
        c = st.columns(cols)
        for j, (label, value, help_text) in enumerate(row):
            c[j].metric(label, value, help=help_text)


def argmax_row(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    if df is None or df.empty or col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce")
    if s.isna().all():
        return None
    return df.loc[s.idxmax()]


def argmin_row(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    if df is None or df.empty or col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce")
    if s.isna().all():
        return None
    return df.loc[s.idxmin()]


def pareto_min_xy(df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    """
    Pareto frontier for minimizing x and y.
    Returns rows that are not dominated.
    """
    if df is None or df.empty:
        return df
    d = df.copy()
    d[x] = pd.to_numeric(d[x], errors="coerce")
    d[y] = pd.to_numeric(d[y], errors="coerce")
    d = d.dropna(subset=[x, y]).sort_values([x, y])
    best_y = float("inf")
    keep = []
    for _, r in d.iterrows():
        if r[y] <= best_y:
            best_y = r[y]
            keep.append(True)
        else:
            keep.append(False)
    return d.loc[d.index[keep]]


# -----------------------------
# Validate dirs
# -----------------------------
if not REPORTS_DIR.exists():
    st.error("outputs/reports not found. Run your scripts first to generate reports.")
    st.stop()

# -----------------------------
# Discover latest artifacts
# -----------------------------
chat_sweep = latest_file("sweep_chat_*.csv")
rag_sweep = latest_file("rag_sweep_*.csv")
cache_experiment = latest_file("cache_experiment_*.csv")
cache_hit_sweep = latest_file("cache_hit_rate_sweep_*.csv")
rag_topk = latest_file("rag_topk_sweep_*.csv")
rag_topk_judge = latest_file("rag_topk_judge_*.csv")

img_chat_vs_rag = REPORTS_DIR / "pareto_chat_vs_rag.png"
img_cache_cost = REPORTS_DIR / "cache_cost_curve.png"
img_cache_lat = REPORTS_DIR / "cache_latency_curve.png"
img_rag_topk_cost = REPORTS_DIR / "rag_topk_cost_curve.png"
img_rag_topk_lat = REPORTS_DIR / "rag_topk_latency_curve.png"

# Load
df_chat = load_csv(chat_sweep)
df_rag = load_csv(rag_sweep)
df_cache_exp = load_csv(cache_experiment)
df_cache_hit = load_csv(cache_hit_sweep)
df_topk = load_csv(rag_topk)
df_topk_j = load_csv(rag_topk_judge)

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("## Latest report files")
    st.markdown('<div class="small-muted">Click a filename to download.</div>', unsafe_allow_html=True)

    file_link("Chat sweep", chat_sweep, "Generated by scripts/run_sweep.py")
    file_link("RAG sweep", rag_sweep, "Generated by scripts/run_rag_sweep.py")
    file_link("Cache exp", cache_experiment, "Generated by scripts/run_cache_experiment.py")
    file_link("Cache hit sweep", cache_hit_sweep, "Generated by scripts/cache_hit_rate_sweep.py")
    file_link("RAG top_k", rag_topk, "Generated by scripts/run_rag_topk_sweep.py")
    file_link("RAG top_k + judge", rag_topk_judge, "Generated by judge-enabled top_k sweep")

    st.divider()
    st.markdown("### Display options")
    show_raw = st.toggle("Show raw tables", value=False)
    show_saved_images = st.toggle("Show saved plot images", value=True)
    use_micro_units = st.toggle("Use µ€ units", value=True)

    st.divider()
    st.markdown("### Quick commands")
    st.code(
        "\n".join(
            [
                "python scripts/run_sweep.py",
                "python scripts/run_cache_experiment.py",
                "python scripts/cache_hit_rate_sweep.py",
                "python scripts/build_rag_index.py",
                "python scripts/run_rag_sweep.py",
                "python scripts/run_rag_topk_sweep.py",
                "streamlit run streamlit_app.py",
            ]
        ),
        language="bash",
    )

# -----------------------------
# Branded Header (FORCED LOGO)
# -----------------------------

logo_path = Path("assets/infernomics_logo.png")

header_left, header_right = st.columns([3, 1])

with header_left:
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
    else:
        st.error("Logo not found at assets/infernomics_logo.png")

with header_right:
    st.markdown(
        """
<div style="text-align:right; padding-top:20px;">
  <div style="font-weight:700; font-size:14px; opacity:0.8;">
    Cost • Latency • Cache • RAG • Judge
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("<hr/>", unsafe_allow_html=True)

# -----------------------------
# Hero + KPI panel
# -----------------------------
hero_left, hero_right = st.columns([2.1, 1])

with hero_left:
    st.subheader("Chat vs RAG frontier")
    st.markdown('<div class="small-muted">Cost–latency tradeoffs for GPT-4o-mini across Chat and RAG.</div>', unsafe_allow_html=True)
    if show_saved_images and img_chat_vs_rag.exists():
        st.image(str(img_chat_vs_rag), use_container_width=True)
    else:
        st.info("No saved overlay image found (outputs/reports/pareto_chat_vs_rag.png).")

with hero_right:
    st.subheader("Project KPIs (latest)")
    st.markdown('<div class="small-muted">Fastest/cheapest configs + best quality-per-euro.</div>', unsafe_allow_html=True)

    kpis: list[tuple[str, str, str]] = []

    # ---- Chat KPIs ----
    if df_chat is not None and not df_chat.empty:
        dfc = to_num(df_chat, ["avg_ms", "p95_ms", "cost_per_req", "max_output_tokens"])
        cheapest = argmin_row(dfc, "cost_per_req")
        fastest = argmin_row(dfc, "avg_ms")

        if cheapest is not None:
            kpis.append(("Cheapest max_out", str(safe_int(cheapest.get("max_output_tokens"))), "Lowest inference cost per request"))
            c_micro = safe_float(cheapest.get("cost_per_req")) * 1_000_000
            kpis.append(("Cheapest µ€/req", fmt_micro(c_micro), "Inference-only cost per request"))

        if fastest is not None:
            kpis.append(("Fastest max_out", str(safe_int(fastest.get("max_output_tokens"))), "Lowest average latency"))
            kpis.append(("Fastest avg ms", fmt_ms(safe_float(fastest.get("avg_ms"))), "Average latency"))

    # ---- Judge KPIs ----
    if df_topk_j is not None and not df_topk_j.empty:
        dft = to_num(
            df_topk_j,
            [
                "top_k",
                "cost_per_req",
                "judge_quality_avg_0_5",
                "judge_grounded_avg_0_5",
                "judge_cost_per_req",
            ],
        )
        # Best quality per euro (inference-only)
        if "judge_quality_avg_0_5" in dft.columns and "cost_per_req" in dft.columns:
            dft = dft.dropna(subset=["judge_quality_avg_0_5", "cost_per_req"]).copy()
            if not dft.empty:
                dft["q_per_eur"] = dft["judge_quality_avg_0_5"] / dft["cost_per_req"]
                best = argmax_row(dft, "q_per_eur")
                if best is not None:
                    kpis.append(("Best top_k", str(safe_int(best.get("top_k"))), "Max quality per euro (inference-only)"))
                    kpis.append(("Q avg (0–5)", f"{safe_float(best.get('judge_quality_avg_0_5')):.2f}", "LLM-as-judge quality"))
                    kpis.append(("G avg (0–5)", f"{safe_float(best.get('judge_grounded_avg_0_5')):.2f}", "LLM-as-judge groundedness"))
                    eval_micro = safe_float(best.get("judge_cost_per_req")) * 1_000_000
                    kpis.append(("Eval µ€/req", fmt_micro(eval_micro), "Evaluation overhead per request"))

    if not kpis:
        st.info("Run sweeps to populate KPIs.")
    else:
        # 2-column grid prevents truncation
        metric_grid(kpis, cols=2)

st.markdown("<hr/>", unsafe_allow_html=True)

# -----------------------------
# Tabs
# -----------------------------
tab_chat, tab_cache, tab_rag, tab_judge = st.tabs(["Chat Sweep", "Caching", "RAG Sweep", "RAG top_k + Judge"])


# -----------------------------
# Chat tab
# -----------------------------
with tab_chat:
    st.subheader("Chat Sweep")
    st.markdown('<div class="small-muted">max_output_tokens sweep. Cost–latency frontier.</div>', unsafe_allow_html=True)

    if df_chat is None or df_chat.empty:
        st.warning("Chat sweep CSV not found. Run: python scripts/run_sweep.py")
    else:
        df = to_num(df_chat, ["max_output_tokens", "avg_ms", "p95_ms", "cost_per_req"])
        df = df.dropna(subset=["avg_ms", "cost_per_req"])

        df["cost_micro"] = micro(df["cost_per_req"])
        y_col = "cost_micro" if use_micro_units else "cost_per_req"
        y_title = "Cost per request (µ€)" if use_micro_units else "Cost per request (€)"

        if show_raw:
            st.dataframe(df, use_container_width=True)

        # Pareto overlay (minimize latency and cost)
        pareto = pareto_min_xy(df, "avg_ms", y_col)

        base = alt.Chart(df).mark_circle(size=140, opacity=0.85).encode(
            x=alt.X("avg_ms:Q", title="Average latency (ms)"),
            y=alt.Y(f"{y_col}:Q", title=y_title),
            tooltip=["max_output_tokens", "avg_ms", "p95_ms", "cost_per_req"],
        )
        frontier = alt.Chart(pareto).mark_line().encode(
            x="avg_ms:Q",
            y=f"{y_col}:Q",
        )

        st.altair_chart(base + frontier, use_container_width=True)


# -----------------------------
# Cache tab
# -----------------------------
with tab_cache:
    st.subheader("Caching")
    st.markdown('<div class="small-muted">Cold vs warm prompt cache + controlled cache hit-rate sweep.</div>', unsafe_allow_html=True)

    left, right = st.columns([1.05, 1.6])

    with left:
        st.markdown("### Cold vs Warm (prompt cache)")
        if df_cache_exp is None or df_cache_exp.empty:
            st.info("Cache experiment CSV not found. Run: python scripts/run_cache_experiment.py")
        else:
            if show_raw:
                st.dataframe(df_cache_exp, use_container_width=True)

    with right:
        st.markdown("### Hit rate sweep")
        if df_cache_hit is None or df_cache_hit.empty:
            st.info("Cache hit-rate sweep CSV not found. Run: python scripts/cache_hit_rate_sweep.py")
        else:
            df = to_num(df_cache_hit, ["hit_rate_real", "avg_ms", "billed_cost_per_req"])
            df = df.dropna(subset=["hit_rate_real", "billed_cost_per_req"]).copy()
            df["hit_rate_pct"] = df["hit_rate_real"] * 100.0
            df["billed_cost_micro"] = micro(df["billed_cost_per_req"])

            y_col = "billed_cost_micro" if use_micro_units else "billed_cost_per_req"
            y_title = "Billed cost per request (µ€)" if use_micro_units else "Billed cost per request (€)"

            if show_raw:
                st.dataframe(df, use_container_width=True)

            chart = alt.Chart(df.sort_values("hit_rate_pct")).mark_line(point=True).encode(
                x=alt.X("hit_rate_pct:Q", title="Cache hit rate (%)"),
                y=alt.Y(f"{y_col}:Q", title=y_title),
                tooltip=["hit_rate_pct", "avg_ms", "billed_cost_per_req"],
            )
            st.altair_chart(chart, use_container_width=True)

    if show_saved_images:
        st.markdown("### Saved plots")
        c1, c2 = st.columns(2)
        with c1:
            if img_cache_cost.exists():
                st.image(str(img_cache_cost), use_container_width=True)
            else:
                st.caption("cache_cost_curve.png not found.")
        with c2:
            if img_cache_lat.exists():
                st.image(str(img_cache_lat), use_container_width=True)
            else:
                st.caption("cache_latency_curve.png not found.")


# -----------------------------
# RAG sweep tab
# -----------------------------
with tab_rag:
    st.subheader("RAG Sweep")
    st.markdown('<div class="small-muted">RAG max_output_tokens sweep (inference + embedding overhead).</div>', unsafe_allow_html=True)

    if df_rag is None or df_rag.empty:
        st.warning("RAG sweep CSV not found. Run: python scripts/run_rag_sweep.py")
    else:
        df = to_num(df_rag, ["max_output_tokens", "top_k", "avg_ms", "p95_ms", "cost_per_req", "embed_cost_total"])
        df = df.dropna(subset=["avg_ms", "cost_per_req"]).copy()
        df["cost_micro"] = micro(df["cost_per_req"])

        y_col = "cost_micro" if use_micro_units else "cost_per_req"
        y_title = "Cost per request (µ€)" if use_micro_units else "Cost per request (€)"

        if show_raw:
            st.dataframe(df, use_container_width=True)

        chart = alt.Chart(df).mark_circle(size=140, opacity=0.9).encode(
            x=alt.X("avg_ms:Q", title="Average latency (ms)"),
            y=alt.Y(f"{y_col}:Q", title=y_title),
            color=alt.Color("max_output_tokens:N", title="max_out"),
            tooltip=["max_output_tokens", "top_k", "avg_ms", "p95_ms", "cost_per_req", "embed_cost_total"],
        )
        st.altair_chart(chart, use_container_width=True)


# -----------------------------
# Judge tab
# -----------------------------
with tab_judge:
    st.subheader("RAG top_k + Judge")
    st.markdown('<div class="small-muted">Cost vs Quality/Groundedness with evaluation overhead.</div>', unsafe_allow_html=True)

    if df_topk_j is None or df_topk_j.empty:
        st.warning("Judge CSV not found. Expected: outputs/reports/rag_topk_judge_*.csv")
    else:
        df = to_num(
            df_topk_j,
            [
                "top_k",
                "avg_ms",
                "cost_per_req",
                "judge_cost_per_req",
                "cost_per_req_including_eval",
                "judge_quality_avg_0_5",
                "judge_grounded_avg_0_5",
                "judge_follows_rate",
            ],
        )
        df = df.dropna(subset=["top_k", "cost_per_req", "judge_quality_avg_0_5"]).copy()

        df["cost_micro"] = micro(df["cost_per_req"])
        df["eval_micro"] = micro(df["judge_cost_per_req"])
        df["all_micro"] = micro(df["cost_per_req_including_eval"])

        if show_raw:
            st.dataframe(df, use_container_width=True)

        x_col = "cost_micro" if use_micro_units else "cost_per_req"
        x_title = "Inference cost per request (µ€)" if use_micro_units else "Inference cost per request (€)"

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Cost vs Quality")
            cq = alt.Chart(df).mark_circle(size=220).encode(
                x=alt.X(f"{x_col}:Q", title=x_title),
                y=alt.Y("judge_quality_avg_0_5:Q", title="Quality (0–5)"),
                color=alt.Color("top_k:N", title="top_k"),
                tooltip=[
                    "top_k",
                    "judge_quality_avg_0_5",
                    "judge_grounded_avg_0_5",
                    "judge_follows_rate",
                    "cost_per_req",
                    "judge_cost_per_req",
                    "cost_per_req_including_eval",
                    "avg_ms",
                ],
            )
            st.altair_chart(cq, use_container_width=True)

        with c2:
            st.markdown("### Cost vs Groundedness")
            cg = alt.Chart(df).mark_circle(size=220).encode(
                x=alt.X(f"{x_col}:Q", title=x_title),
                y=alt.Y("judge_grounded_avg_0_5:Q", title="Groundedness (0–5)"),
                color=alt.Color("top_k:N", title="top_k"),
                tooltip=[
                    "top_k",
                    "judge_quality_avg_0_5",
                    "judge_grounded_avg_0_5",
                    "judge_follows_rate",
                    "cost_per_req",
                    "judge_cost_per_req",
                    "cost_per_req_including_eval",
                    "avg_ms",
                ],
            )
            st.altair_chart(cg, use_container_width=True)

        st.markdown("### Cost components (µ€ / request)")
        melt = df[["top_k", "cost_micro", "eval_micro"]].melt(
            id_vars=["top_k"], var_name="component", value_name="micro_eur"
        )
        melt["component"] = melt["component"].map({"cost_micro": "Inference", "eval_micro": "Evaluation (judge)"})

        bars = alt.Chart(melt).mark_bar().encode(
            x=alt.X("top_k:N", title="top_k"),
            y=alt.Y("micro_eur:Q", title="µ€ per request"),
            color=alt.Color("component:N", title="Component"),
            tooltip=["top_k", "component", "micro_eur"],
        )
        st.altair_chart(bars, use_container_width=True)

        if show_saved_images:
            st.markdown("### Saved plots")
            i1, i2 = st.columns(2)
            with i1:
                if img_rag_topk_cost.exists():
                    st.image(str(img_rag_topk_cost), use_container_width=True)
                else:
                    st.caption("rag_topk_cost_curve.png not found.")
            with i2:
                if img_rag_topk_lat.exists():
                    st.image(str(img_rag_topk_lat), use_container_width=True)
                else:
                    st.caption("rag_topk_latency_curve.png not found.")
