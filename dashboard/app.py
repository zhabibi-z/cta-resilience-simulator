"""CTA Multi-Modal Resilience — interactive decision-support dashboard.

Run:  streamlit run dashboard/app.py

A planner picks a disruption (flood a region, attack the busiest hubs, random failure), sees the
cascade on a real CTA map, the resilience triangle, and a ranked list of stations to harden.
All computation is the real engine (core/) over the real bilayer (ingest/network).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable no matter how this file is launched. Streamlit (locally and on
# Community Cloud) runs `dashboard/app.py` directly, which puts only `dashboard/` on sys.path —
# not the project root where `core/` and `ingest/` live. Insert it before those imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pydeck as pdk
import streamlit as st

from core.hardening import greedy_hardening
from dashboard import logic
from ingest.network import load_or_build_network

st.set_page_config(page_title="CTA Resilience", layout="wide", page_icon="🚆")


@st.cache_resource(show_spinner="Loading the real CTA bilayer…")
def get_network():
    return load_or_build_network()


G = get_network()
n_nodes = G.number_of_nodes()

st.title("🚆 CTA Multi-Modal Resilience — Decision Support")
st.caption(
    f"Real CTA bus + rail bilayer ({n_nodes} nodes) from GTFS + Chicago Data Portal ridership. "
    "Pick a disruption; see the cascade, the resilience triangle, and where to invest."
)

# ── Controls ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("① Disruption")
    hazard_type = st.selectbox("Hazard", logic.HAZARD_TYPES)
    landmark, radius, k = "loop", 2000.0, 3
    if hazard_type == "Flood / storm (area)":
        landmark = st.selectbox("Location", logic.landmark_options(),
                                index=logic.landmark_options().index("loop"))
        radius = st.slider("Radius (m)", 500, 4000, 2000, 250)
    else:
        k = st.slider("How many stations", 1, 10, 3)

    st.header("② Model")
    load_label = st.selectbox("Load model", logic.LOAD_MODELS)
    alpha = st.slider("Capacity tolerance α", 0.05, 1.0, 0.15, 0.05)
    recovery = st.selectbox("Recovery order", ["ridership", "centrality", "random"])

hazard = logic.build_hazard(G, hazard_type, landmark=landmark, radius_m=radius, k=k)
result = logic.run_scenario(G, hazard, alpha, load_label, recovery)

# ── KPIs ────────────────────────────────────────────────────────────────────
for col, (label, val) in zip(st.columns(4), logic.kpis(result, n_nodes).items(), strict=False):
    col.metric(label, val)

# ── Map + resilience triangle ────────────────────────────────────────────────
left, right = st.columns([3, 2])
with left:
    st.subheader("Network status")
    df = logic.map_dataframe(G, result)
    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=41.88, longitude=-87.65, zoom=9.5),
        layers=[pdk.Layer(
            "ScatterplotLayer", data=df, get_position="[lon, lat]", get_fill_color="color",
            get_radius="ridership", radius_scale=0.04, radius_min_pixels=2, radius_max_pixels=16,
            pickable=True, opacity=0.75,
        )],
        tooltip={"text": "{name}\n{status} · {ridership} riders"},
    ))
    st.caption("🟢 active  🔴 failed  🔵 hardened  ⚪ bus")

with right:
    st.subheader("Resilience triangle")
    st.line_chart(logic.triangle_dataframe(result), x="step", y="served_fraction", height=280)
    st.caption(
        f"Service degrades then recovers. Hazard: `{hazard.label}` · "
        f"{result.total_failed} of {n_nodes} nodes down at the trough."
    )

# ── Hardening recommendations ────────────────────────────────────────────────
st.divider()
st.subheader("③ Where to invest — hardening recommendations")
c1, c2 = st.columns([1, 3])
budget = c1.slider("Protection budget", 1, 8, 4)
if c1.button("Compute recommendations", type="primary"):
    with st.spinner("Optimizing — running many trial cascades…"):
        hr = greedy_hardening(G, hazard, alpha=alpha, budget=budget,
                              max_candidates=12, max_cascade_ticks=6)
    delta = hr.final_objective - hr.baseline_objective
    c2.success(f"Integrated resilience **R {hr.baseline_objective:.3f} → {hr.final_objective:.3f}** "
               f"(+{delta:.3f}) by hardening {len(hr.hardened)} station(s).")
    for i, name in enumerate(hr.hardened_names, 1):
        c2.write(f"**{i}. {name}**")
    if not hr.hardened_names:
        c2.info("No single-station hardening improves this scenario under the current settings.")
else:
    c2.caption("Pick a budget and click to compute the priority-ordered stations to protect.")
