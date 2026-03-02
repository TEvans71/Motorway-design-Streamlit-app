# -*- coding: utf-8 -*-
"""
Motorway Design Coursework — Single-File Streamlit App
======================================================
EN3309 Week 1 + Week 2 (Ted's Spyder logic merged). All maths unchanged.
"""

import os
import math
import shutil
from datetime import datetime

import streamlit as st
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import pandas as pd
import numpy as np

from geotech_core_settlement import (
    StressInputs,
    build_settlement_integration_table,
    build_settlement_integration_table_mv,
    consolidation_times_table,
    settlement_primary_1d,
    sigma_v0_prime_kpa,
)

APP_BUILD = "1f51962"  # update this when you deploy

# =============================================================================
# 1) DEFAULT INPUTS — WEEK 1 (overwritten by sidebar on Run)
# =============================================================================

OUTPUT_FOLDER = "out_motorway"
OUTPUT_EXCEL_NAME = "Motorway_Week1.xlsx"

# Group defaults for Reset button
GROUP_DEFAULTS = {
    "L": 1000.0, "dx": 50.0,
    "ga": 49.6, "gb": 50.5, "xc": 500.0, "bc": 30.05, "bdown": True,
    "btop": 43.3, "m": 2.0,
    "flood": 54.0, "fb": 1.0, "z0": 55.0, "grade": 1.0 / 200.0,
    "gf": 20.0, "gc": 18.0, "gw": 10.0, "wt": True, "zw": 0.0,
    "cm": "mv", "mv": 0.0005, "Cc": 0.35, "e0": 0.335,
    "cu": 15.0, "Is": 1.0, "Ecu": 300.0,
    "imethod": "Lecture (Barnes/Craig): ρ_i = q B I_s / E_u",
    "qmethod": "Use q_equiv (trapezoid)",
    "ifmode": "Input I_s directly (from chart)",
    "Is_chart": 1.0,
    "mu1_chart": 1.0,
    "staged": False,
    "lift_h": 1.0,
    "xw": 500.0, "xs": 500.0,
    "cdm": "Layered (sum over N layers)", "Nlayers": 20, "csp": "Centre (x = 0)",
    "dsmode": "Lecture (Craig strip): Δσ(z)=q·Iσ(z)",
    "quick_stage1": True,
    "Cv": 1e-7, "vd": "double", "Uvt": "0.20, 0.50, 0.90",
}

L = 1000.0
dx = 50.0
ground_A = 49.6
ground_B = 50.5
x_c = 500.0
bedrock_c = 30.05
bedrock_goes_down_towards_B = True
B_top = 43.3
m = 2.0
flood_level = 54.0
freeboard = 1.0
Zmin_finish = flood_level + freeboard
Z_peak_finish = 55.0  # Crown level at x_peak
grade = 1.0 / 200.0
gamma_fill = 20.0
gamma_clay = 18.0
gamma_w = 10.0
water_table_at_ground = True
z_wt_m = 0.0
m_v = 0.0005
Cc = 0.35
e0 = 0.335
consol_method = "mv"
cu = 15.0
Is = 1.0
Eu_over_cu = 300.0
x_worked = 500.0
REPORT_CHAINAGES = [0.0, 500.0, 1000.0]
immediate_settlement_method = "Lecture (Barnes/Craig): ρ_i = q B I_s / E_u"
q_immediate_method = "Use q_equiv (trapezoid)"
influence_factor_input_mode = "Input I_s directly (from chart)"
I_s_input = 1.0
mu1_input = 1.0
staged_construction_lifts = False
lift_height_m = 1.0

IMMEDIATE_METHOD_LECTURE = "Lecture (Barnes/Craig): ρ_i = q B I_s / E_u"
IMMEDIATE_METHOD_LEGACY = "Current/simple (legacy)"
Q_METHOD_LECTURE = "Lecture: q = γ_fill * H_fill"
Q_METHOD_TRAPEZOID = "Use q_equiv (trapezoid)"
INFLUENCE_MODE_IS = "Input I_s directly (from chart)"
INFLUENCE_MODE_MU1 = "Input μ1 (μ0 assumed 1) (from chart)"
DELTA_SIGMA_MODE_LECTURE = "Lecture (Craig strip): Δσ(z)=q·Iσ(z)"
DELTA_SIGMA_MODE_QUICK = "Quick (constant): Δσ(z)=q (upper bound)"

# Layered consolidation options
consolidation_depth_method = "Layered (sum over N layers)"
N_layers = 20
consol_stress_point = "Centre (x = 0)"
delta_sigma_mode = DELTA_SIGMA_MODE_LECTURE
run_preliminary_quick_stage = True
run_detailed_stage2_profile = True
N_CHAINAGE_SURF = 21
N_LATERAL_SURF = 41
Z_EXAG = 15.0

# =============================================================================
# 1B) DEFAULT INPUTS — WEEK 2 (vertical consolidation only)
# =============================================================================

Uv_targets = [0.20, 0.50, 0.90]
Cv_m2_per_s = 1e-7
vertical_drainage = "double"
SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0
EVIDENCE_NOTES = [
    "Finish level constraint: Z_minfinish = 54 + 1 = 55 m AOD",
    "Vertical shift: ΔZ = max(0, 55 − min(Z_design_raw))",
    "Z_finish(x) = Z_design_raw(x) + ΔZ",
    "H_fill(x) = max(0, Z_finish(x) − Z_ground(x))",
    "z_wt(x) = max(0, Z_ground(x) − 54)",
    "σ′v0(z) = σv(z) − u(z)",
    "ds=(Cc/(1+e0)) dz log10((σ′0+Δσ)/σ′0)",
    "Tv=Cv t/Hd²; Hd=H0 or H0/2",
]
FLOOD_10YR_AOD_M = 54.0
FREEBOARD_M = 1.0
Z_MIN_FINISH_AOD_M = FLOOD_10YR_AOD_M + FREEBOARD_M  # 55.0 m AOD

# Coursework lock mode (default ON): fixed values, read-only sidebar display.
COURSEWORK_LOCKED = True
COURSEWORK_INPUTS = {
    "Chainage & geometry": [
        {"key": "L_m", "label": "L", "value": 1000.0, "unit": "m", "fmt": ".2f"},
        {"key": "dx_m", "label": "dx", "value": 50.0, "unit": "m", "fmt": ".2f"},
        {"key": "ground_A_mAOD", "label": "ground_A", "value": 49.6, "unit": "mAOD", "fmt": ".2f"},
        {"key": "ground_B_mAOD", "label": "ground_B", "value": 50.5, "unit": "mAOD", "fmt": ".2f"},
        {"key": "x_c_m", "label": "x_c", "value": 500.0, "unit": "m", "fmt": ".2f"},
        {"key": "bedrock_c_mAOD", "label": "bedrock_c", "value": 30.05, "unit": "mAOD", "fmt": ".2f"},
        {"key": "bedrock_goes_down_towards_B", "label": "bedrock_goes_down_towards_B", "value": True, "unit": ""},
        {"key": "B_top_m", "label": "B_top", "value": 43.30, "unit": "m", "fmt": ".2f"},
        {"key": "m_side_slope", "label": "m (side slope 2H:1V)", "value": 2.00, "unit": "", "fmt": ".2f"},
    ],
    "Finished road": [
        {"key": "flood_level_mAOD", "label": "flood_level", "value": 54.00, "unit": "mAOD", "fmt": ".2f"},
        {"key": "freeboard_m", "label": "freeboard", "value": 1.00, "unit": "m", "fmt": ".2f"},
        {"key": "Z_peak_finish_mAOD", "label": "Z_peak_finish", "value": 55.00, "unit": "mAOD", "fmt": ".2f"},
        {"key": "grade_m_per_m", "label": "grade", "value": 0.005000, "unit": "m/m", "fmt": ".6f"},
    ],
    "Soils & consolidation": [
        {"key": "gamma_fill", "label": "γ_fill", "value": 20.00, "unit": "kN/m³", "fmt": ".2f"},
        {"key": "gamma_clay", "label": "γ_clay", "value": 18.00, "unit": "kN/m³", "fmt": ".2f"},
        {"key": "gamma_w", "label": "γ_w", "value": 10.00, "unit": "kN/m³", "fmt": ".2f"},
        {"key": "water_table_at_ground", "label": "water_table_at_ground", "value": True, "unit": ""},
        {"key": "use_flood_wt", "label": "Use 10-year flood level as water level (54 m AOD)", "value": True, "unit": ""},
        {"key": "z_wt_m", "label": "z_wt_m (below ground)", "value": 0.00, "unit": "m", "fmt": ".2f"},
        {"key": "consol_method_display", "label": "Primary consolidation settlement model", "value": "mv (given)", "unit": ""},
        {"key": "m_v", "label": "m_v", "value": 0.000500, "unit": "m²/kN", "fmt": ".6f"},
        {"key": "Cc", "label": "Cc", "value": 0.35, "unit": "", "fmt": ".2f"},
        {"key": "e0", "label": "e0", "value": 0.34, "unit": "", "fmt": ".2f"},
        {"key": "cu_kpa", "label": "c_u", "value": 15.00, "unit": "kPa", "fmt": ".2f"},
        {"key": "Is", "label": "I_s (legacy/default)", "value": 1.00, "unit": "", "fmt": ".2f"},
        {"key": "Eu_over_cu", "label": "E_u/c_u", "value": 300.00, "unit": "", "fmt": ".2f"},
        {"key": "x_worked_m", "label": "x_worked", "value": 500.00, "unit": "m", "fmt": ".2f"},
        {"key": "consolidation_depth_method", "label": "Consolidation depth method", "value": "Layered (sum over N layers)", "unit": ""},
        {"key": "N_layers", "label": "N layers for consolidation", "value": 20, "unit": "", "fmt": "d"},
        {"key": "consol_stress_point", "label": "Stress point for consolidation Δσ", "value": "Centre (x = 0)", "unit": ""},
        {"key": "delta_sigma_mode", "label": "Δσ(z) method", "value": "Lecture (Craig strip): Δσ(z)=q·Iσ(z)", "unit": ""},
        {"key": "run_preliminary_quick_stage", "label": "Run preliminary quick settlement stage (lecture Stage 1)", "value": True, "unit": ""},
        {"key": "run_detailed_stage2_profile", "label": "Run detailed Stage-2 profile (ρ_total = ρ_i + ρ_c)", "value": True, "unit": ""},
        {"key": "immediate_settlement_method", "label": "Immediate settlement method", "value": "Lecture (Barnes/Craig): ρ_i = q B I_s / E_u", "unit": ""},
        {"key": "q_immediate_method", "label": "Applied pressure q at base", "value": "Lecture: q = γ_fill * H_fill", "unit": ""},
        {"key": "influence_factor_input_mode", "label": "Influence factor input", "value": "Input I_s directly (from chart)", "unit": ""},
        {"key": "I_s_input", "label": "I_s_input", "value": 1.00, "unit": "", "fmt": ".2f"},
        {"key": "mu1_input", "label": "mu1_input (inactive when I_s mode)", "value": 1.00, "unit": "", "fmt": ".2f"},
        {"key": "staged_construction_lifts", "label": "Staged construction (lifts)", "value": False, "unit": ""},
        {"key": "lift_height_m", "label": "lift_height_m", "value": 1.00, "unit": "m", "fmt": ".2f"},
    ],
    "Vertical consolidation": [
        {"key": "Cv_m2_per_s", "label": "Cv", "value": 1e-7, "unit": "m²/s", "fmt": ".0e"},
        {"key": "vertical_drainage", "label": "vertical_drainage", "value": "double", "unit": ""},
        {"key": "Uv_targets_str", "label": "Uv_targets (comma-sep)", "value": "0.20, 0.50, 0.90", "unit": ""},
        {"key": "x_section_m", "label": "Cross-section chainage x_section", "value": 500.00, "unit": "m", "fmt": ".2f"},
    ],
    "Slope stability (short-term)": [
        {"key": "run_slope_stability", "label": "Run slope stability analysis", "value": True, "unit": ""},
        {"key": "stability_analysis_domain", "label": "Stability analysis domain", "value": "Half embankment (crest → toe) [coursework]", "unit": ""},
        {"key": "stability_side", "label": "Side", "value": "Right", "unit": ""},
        {"key": "intersection_tolerance_m", "label": "Intersection tolerance", "value": 2.00, "unit": "m", "fmt": ".2f"},
        {"key": "mirror_for_display", "label": "Mirror for display", "value": False, "unit": ""},
        {"key": "require_pass_through_embankment", "label": "Require pass through embankment", "value": True, "unit": ""},
        {"key": "max_cover_height_m", "label": "Max cover height", "value": 2.00, "unit": "m", "fmt": ".2f"},
        {"key": "x_stability_m", "label": "x_stability", "value": 500.00, "unit": "m", "fmt": ".2f"},
        {"key": "n_slices", "label": "n_slices", "value": 30, "unit": "", "fmt": "d"},
        {"key": "grid_x_min_m", "label": "grid_x_min", "value": -120.00, "unit": "m", "fmt": ".2f"},
        {"key": "grid_x_max_m", "label": "grid_x_max", "value": 120.00, "unit": "m", "fmt": ".2f"},
        {"key": "grid_z_min_mAOD", "label": "grid_z_min", "value": 45.05, "unit": "mAOD", "fmt": ".2f"},
        {"key": "grid_z_max_mAOD", "label": "grid_z_max", "value": 130.05, "unit": "mAOD", "fmt": ".2f"},
        {"key": "grid_nx", "label": "grid_nx", "value": 15, "unit": "", "fmt": "d"},
        {"key": "grid_nz", "label": "grid_nz", "value": 10, "unit": "", "fmt": "d"},
        {"key": "circle_radius_min_m", "label": "circle_radius_min", "value": 10.00, "unit": "m", "fmt": ".2f"},
        {"key": "circle_radius_max_m", "label": "circle_radius_max", "value": 400.00, "unit": "m", "fmt": ".2f"},
        {"key": "radius_steps", "label": "radius_steps", "value": 120, "unit": "", "fmt": "d"},
        {"key": "span_requirement", "label": "Span requirement", "value": "Base toes (strict)", "unit": ""},
        {"key": "min_FOS_required", "label": "min_FOS_required", "value": 1.30, "unit": "", "fmt": ".2f"},
        {"key": "max_depth_below_ground_m", "label": "Max slip depth below ground", "value": 40.00, "unit": "m", "fmt": ".2f"},
        {"key": "depth_constraint_mode", "label": "Depth constraint mode", "value": "Limit below bedrock (recommended)", "unit": ""},
        {"key": "bedrock_margin_m", "label": "Allow slip below bedrock", "value": 0.00, "unit": "m", "fmt": ".2f"},
        {"key": "unit_weight_for_W", "label": "Unit weight for slice weight W", "value": "gamma_fill_above_ground + gamma_clay_below", "unit": ""},
    ],
}
COURSEWORK_INPUTS_BY_KEY = {
    item["key"]: item["value"]
    for section in COURSEWORK_INPUTS.values()
    for item in section
}


def _format_locked_value(item: dict) -> str:
    value = item.get("value")
    unit = item.get("unit", "")
    fmt = item.get("fmt")
    if isinstance(value, bool):
        text = "True" if value else "False"
    elif isinstance(value, (int, np.integer)) and fmt == "d":
        text = f"{int(value)}"
    elif isinstance(value, (float, np.floating)):
        if fmt:
            text = format(float(value), fmt)
        elif abs(float(value)) > 0.0 and (abs(float(value)) < 1e-4 or abs(float(value)) >= 1e5):
            text = f"{float(value):.2e}"
        else:
            text = f"{float(value):.2f}"
    else:
        text = str(value)
    return f"{text} {unit}".strip()


def render_project_inputs_locked(coursework_inputs: dict):
    st.sidebar.header("Project Inputs")
    st.sidebar.caption(f"Build: {APP_BUILD}")
    for section_name, items in coursework_inputs.items():
        st.sidebar.subheader(section_name)
        rows = [
            {"Parameter": item["label"], "Value": _format_locked_value(item)}
            for item in items
        ]
        df = pd.DataFrame(rows, columns=["Parameter", "Value"])
        st.sidebar.dataframe(df, use_container_width=True, hide_index=True)

# =============================================================================
# 2) HELPERS — WEEK 1 (Ted's logic, unchanged)
# =============================================================================

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def lin(x, x0, y0, x1, y1) -> float:
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)

def bedrock_slope() -> float:
    return 2.0 / 500.0

def bedrock_level(x: float) -> float:
    s = -bedrock_slope() if bedrock_goes_down_towards_B else +bedrock_slope()
    return bedrock_c + s * (x - x_c)

def finished_profile(chainages):
    """Crowned profile: peak at x_peak = x_c, slope g = grade each side."""
    x_peak = x_c
    Z_design_raw = [Z_peak_finish - grade * abs(x - x_peak) for x in chainages]
    Z_shift = max(0.0, Z_MIN_FINISH_AOD_M - float(np.min(Z_design_raw)))
    Z_design = [z + Z_shift for z in Z_design_raw]
    Z_finish = [max(z, Z_MIN_FINISH_AOD_M) for z in Z_design]
    return Z_finish

def B_base_from_H(H_fill: float) -> float:
    H = max(0.0, float(H_fill))
    return float(B_top) + 2.0 * float(m) * H

def A_trapezoid(H_fill: float, B_base: float) -> float:
    H = max(0.0, float(H_fill))
    return 0.5 * (float(B_top) + float(B_base)) * H

def W_line_kN_per_m(H_fill: float, B_base: float) -> float:
    return float(gamma_fill) * A_trapezoid(H_fill, B_base)

def q_equiv_kPa(H_fill: float, B_base: float) -> float:
    B = max(1e-9, float(B_base))
    return W_line_kN_per_m(H_fill, B_base) / B

def strip_angles_alpha_beta(B: float, z: float, x: float = 0.0):
    if z <= 0.0:
        return 0.0, 0.0
    x_left = -B / 2.0
    x_right = +B / 2.0
    theta_left = math.atan((x_left - x) / z)
    theta_right = math.atan((x_right - x) / z)
    alpha = theta_right - theta_left
    beta = theta_left
    return alpha, beta

def delta_sigma_strip(q: float, B: float, z: float, x: float = 0.0) -> float:
    if z <= 0.0 or q <= 0.0 or B <= 0.0:
        return 0.0
    alpha, beta = strip_angles_alpha_beta(B, z, x=x)
    return (q / math.pi) * (alpha + math.sin(alpha) * math.cos(alpha + 2.0 * beta))


def compute_rho_c_for_offset(
    H0_m: float,
    stress_inputs,
    q_kpa: float,
    B_base_m: float,
    offset_m: float,
    consol_method_value: str,
    m_v: float,
    Cc: float,
    e0: float,
    n_slices_settlement: int,
    log_base_settlement: float,
):
    """Compute primary consolidation settlement for a single lateral offset using Craig strip Δσ."""
    delta_sigma_func = (
        lambda z, q=q_kpa, B=B_base_m, xoff=offset_m:
        float(delta_sigma_strip(q=float(q), B=float(B), z=float(z), x=float(xoff)))
    )

    if str(consol_method_value).strip().lower() == "mv":
        mv_res = build_settlement_integration_table_mv(
            H0=float(H0_m),
            m_v=float(m_v),
            delta_sigma_func=delta_sigma_func,
            stress=stress_inputs,
            n_slices=int(n_slices_settlement),
        )
        if isinstance(mv_res, tuple):
            return float(mv_res[1]) if len(mv_res) > 1 else 0.0
        if isinstance(mv_res, dict):
            if "S_total_m" in mv_res:
                return float(mv_res["S_total_m"])
            mv_rows = mv_res.get("rows")
            return float(mv_rows["s_cum_m"].iloc[-1]) if mv_rows is not None and len(mv_rows) > 0 else 0.0
        return float(mv_res["s_cum_m"][-1])

    S_cc, _ = settlement_primary_1d(
        H0=float(H0_m),
        Cc=float(Cc),
        e0=float(e0),
        delta_sigma_func=delta_sigma_func,
        stress=stress_inputs,
        n_slices=int(n_slices_settlement),
        log_base=float(log_base_settlement),
    )
    return float(S_cc)


def consolidation_layers(
    consol_method: str,
    H0: float,
    q: float,
    B: float,
    x_offset: float,
    N_layers: int,
    m_v: float,
    Cc: float,
    e0: float,
    gamma_clay: float,
    gamma_w: float,
    water_table_at_ground: bool
) -> tuple:
    """
    Layered consolidation using exact Craig strip and mv/Cc formulas.
    Returns (rho_c_total, layers_df).
    """
    if H0 <= 0 or q <= 0 or B <= 0:
        empty_df = pd.DataFrame(columns=[
            "layer", "z_mid (m)", "dz (m)", "Delta_sigma (kPa)",
            "sigma_v0_prime (kPa)", "d_rho_c (m)", "rho_c_cum (m)"
        ])
        return (0.0, empty_df)

    dz = H0 / N_layers
    rows = []
    cum_rho = 0.0
    for i in range(N_layers):
        z_mid = (i + 0.5) * dz
        d_sigma = delta_sigma_strip(q, B, z_mid, x=x_offset)

        if consol_method.lower() == "mv":
            d_rho = m_v * d_sigma * dz
            sigma_prime = float("nan")
        elif consol_method.lower() == "cc":
            sigma_v0 = gamma_clay * z_mid
            u = gamma_w * z_mid if water_table_at_ground else 0.0
            sigma_prime = max(1e-6, sigma_v0 - u)
            ratio = (sigma_prime + d_sigma) / sigma_prime
            d_rho = (dz / (1.0 + e0)) * Cc * math.log10(ratio)
        else:
            raise ValueError("consol_method must be 'mv' or 'Cc'")

        cum_rho += d_rho
        rows.append({
            "layer": i + 1,
            "z_mid (m)": z_mid,
            "dz (m)": dz,
            "Delta_sigma (kPa)": d_sigma,
            "sigma_v0_prime (kPa)": sigma_prime if consol_method.lower() == "cc" else float("nan"),
            "d_rho_c (m)": d_rho,
            "rho_c_cum (m)": cum_rho,
        })
    layers_df = pd.DataFrame(rows)
    return (cum_rho, layers_df)


def plot_3d_motorway(df, B_top):
    """Static 3D view: ground, bedrock, road top, widening base, side embankment planes."""
    x_line = df["x"].values
    zg_line = df["ground level"].values
    zt_line = df["Z_finish"].values
    Bb_line = df["B_base"].values

    y_top = B_top / 2.0
    y_base = Bb_line / 2.0

    u = np.linspace(0.0, 1.0, 12)
    Xs, U = np.meshgrid(x_line, u)

    Y_right = y_top + U * (y_base[None, :] - y_top)
    Z_right = zt_line[None, :] + U * (zg_line[None, :] - zt_line[None, :])
    Y_left = -y_top - U * (y_base[None, :] - y_top)
    Z_left = zt_line[None, :] + U * (zg_line[None, :] - zt_line[None, :])

    H_fill_line = np.maximum(0.0, zt_line - zg_line)
    fill_mask = H_fill_line[None, :] > 1e-9
    Z_right = np.where(fill_mask, Z_right, np.nan)
    Z_left = np.where(fill_mask, Z_left, np.nan)

    Bmax = df["B_base"].max()
    y = np.linspace(-Bmax / 2, Bmax / 2, 40)
    X, Y = np.meshgrid(x_line, y)
    Zg = np.tile(zg_line, (len(y), 1))
    Zb = np.tile(df["bedrock level"].values, (len(y), 1))
    Zf = np.tile(zt_line, (len(y), 1))
    mask_top = np.abs(Y) <= (B_top / 2)
    Zf = np.where(mask_top, Zf, np.nan)
    y_left_edge = -Bb_line / 2
    y_right_edge = +Bb_line / 2

    fig = plt.figure(figsize=(9, 6))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot_surface(X, Y, Zg, alpha=0.35, linewidth=0)
    ax.plot_surface(X, Y, Zb, alpha=0.25, linewidth=0)
    ax.plot_surface(X, Y, Zf, alpha=0.6, linewidth=0)
    ax.plot_surface(Xs, Y_right, Z_right, alpha=0.45, linewidth=0)
    ax.plot_surface(Xs, Y_left, Z_left, alpha=0.45, linewidth=0)

    k0, k1 = 0, len(x_line) - 1
    for k in [k0, k1]:
        if H_fill_line[k] <= 1e-9:
            continue
        xk = x_line[k]
        zg = zg_line[k]
        zt = zt_line[k]
        ytop = B_top / 2.0
        ybase = Bb_line[k] / 2.0
        Yp = np.array([-ybase, -ytop, ytop, ybase])
        Zp = np.array([zg, zt, zt, zg])
        Xp = np.full_like(Yp, xk)
        verts_x = np.concatenate([Xp[[0, 1, 2]], Xp[[0, 2, 3]]])
        verts_y = np.concatenate([Yp[[0, 1, 2]], Yp[[0, 2, 3]]])
        verts_z = np.concatenate([Zp[[0, 1, 2]], Zp[[0, 2, 3]]])
        triangles = np.array([[0, 1, 2], [3, 4, 5]])
        ax.plot_trisurf(verts_x, verts_y, verts_z, triangles=triangles, alpha=0.45, linewidth=0)

    ax.plot(x_line, y_left_edge, zg_line, linewidth=2)
    ax.plot(x_line, y_right_edge, zg_line, linewidth=2)

    ax.set_xlabel("Chainage x (m)")
    ax.set_ylabel("Horizontal y (m)")
    ax.set_zlabel("Level (mAOD)")
    ax.set_title("3D view (static): ground + bedrock + road top + side embankment + widening base")
    ax.view_init(elev=20, azim=-60)
    return fig


# =============================================================================
# 3) WEEK 1 CALCULATION
# =============================================================================

def week1_calculate():
    depth_method = consolidation_depth_method
    use_craig_delta_sigma = str(delta_sigma_mode) == DELTA_SIGMA_MODE_LECTURE

    n = int(round(L / dx))
    chainages = [i * dx for i in range(n + 1)]
    ground = [lin(x, 0.0, ground_A, L, ground_B) for x in chainages]
    bedrock = [bedrock_level(x) for x in chainages]
    H0_list = [max(0.0, g - b) for g, b in zip(ground, bedrock)]
    Z_finish = finished_profile(chainages)
    H_fill = [max(0.0, zf - g) for zf, g in zip(Z_finish, ground)]
    B_base = [B_base_from_H(h) for h in H_fill]
    Atrap = [A_trapezoid(h, Bb) for h, Bb in zip(H_fill, B_base)]
    Wline = [W_line_kN_per_m(h, Bb) for h, Bb in zip(H_fill, B_base)]
    qeq = [q_equiv_kPa(h, Bb) for h, Bb in zip(H_fill, B_base)]
    rho_i = []
    q_immediate = []
    Is_immediate = []
    Eu_immediate = []
    immediate_stage_rows_x_section = []
    idx_x_section_target = min(range(len(chainages)), key=lambda i: abs(chainages[i] - float(x_section)))
    is_lecture_method = str(immediate_settlement_method) == IMMEDIATE_METHOD_LECTURE
    use_lecture_q = str(q_immediate_method) == Q_METHOD_LECTURE
    use_input_is = str(influence_factor_input_mode) == INFLUENCE_MODE_IS

    Delta_sigma_mid = []
    rho_c = []
    rho_c_center_list = []
    rho_c_edge_list = []
    rho_total_center_list = []
    rho_total_edge_list = []
    rho_c_method_list = []
    layer_tables_by_chainage = {}
    sigma_v0_prime_mins = []

    stress_inputs_by_chainage = {}
    n_slices_settlement = 60
    log_base_settlement = 10.0
    consol_method_value = str(consol_method).strip().lower()
    S_cc_slices_by_chainage = {}
    S_mv_slices_by_chainage = {}

    for chainage_idx, (h_fill, q, B, h0, x_val, g_level) in enumerate(zip(H_fill, qeq, B_base, H0_list, chainages, ground)):
        Eu_kpa = float(Eu_over_cu) * float(cu)
        mu0 = 1.0
        if is_lecture_method:
            if use_input_is:
                Is_x = float(I_s_input)
            else:
                Is_x = mu0 * float(mu1_input)
        else:
            Is_x = float(Is)

        if float(h_fill) <= 0.0:
            q_kpa = 0.0
        elif use_lecture_q:
            q_kpa = float(gamma_fill) * float(h_fill)
        else:
            q_kpa = float(q)

        rho_i_x = 0.0
        if Eu_kpa > 0.0 and q_kpa > 0.0:
            rho_i_x = (float(q_kpa) * float(B) * float(Is_x)) / float(Eu_kpa)

        if staged_construction_lifts:
            total_height = float(h_fill)
            lift_h = max(0.25, min(2.0, float(lift_height_m)))
            if total_height > 0.0 and Eu_kpa > 0.0:
                n_lifts = int(math.ceil(total_height / lift_h))
                rho_prev = 0.0
                stage_rows_local = []
                for k in range(1, n_lifts + 1):
                    Hk = min(k * lift_h, total_height)
                    if use_lecture_q:
                        qk = float(gamma_fill) * Hk
                    else:
                        qk = float(q) * (Hk / total_height)
                    rho_i_k = (qk * float(B) * float(Is_x)) / float(Eu_kpa)
                    delta_rho_i_k = rho_i_k - rho_prev
                    stage_rows_local.append({
                        "stage": k,
                        "Hk_m": Hk,
                        "qk_kpa": qk,
                        "rho_i_k_m": rho_i_k,
                        "delta_rho_i_k_m": delta_rho_i_k,
                    })
                    rho_prev = rho_i_k
                rho_i_x = rho_prev
                if chainage_idx == idx_x_section_target:
                    immediate_stage_rows_x_section = stage_rows_local
            else:
                rho_i_x = 0.0

        rho_i.append(float(rho_i_x))
        q_immediate.append(float(q_kpa))
        Is_immediate.append(float(Is_x))
        Eu_immediate.append(float(Eu_kpa))

        if use_flood_wt:
            z_wt_chain = max(0.0, float(g_level) - FLOOD_10YR_AOD_M)
        else:
            z_wt_chain = 0.0 if water_table_at_ground else float(z_wt_m)
        stress_inputs = StressInputs(
            gamma_unsat_kN_m3=float(gamma_clay),
            gamma_sat_kN_m3=float(gamma_clay),
            gamma_w_kN_m3=float(gamma_w),
            z_wt_m=z_wt_chain,
        )
        stress_inputs_by_chainage[x_val] = stress_inputs
        q_for_consol = float(q)
        Bsec = float(B)
        if use_craig_delta_sigma:
            delta_sigma_func_center = (
                lambda z, q=q_for_consol, B=Bsec:
                float(delta_sigma_strip(q=float(q), B=float(B), z=float(z), x=0.0))
            )
            delta_sigma_func_edge = (
                lambda z, q=q_for_consol, B=Bsec:
                float(delta_sigma_strip(q=float(q), B=float(B), z=float(z), x=0.5 * float(B)))
            )
        else:
            delta_sigma_func_center = (lambda z, q=q_for_consol: float(q))
            delta_sigma_func_edge = (lambda z, q=q_for_consol: float(q))

        if h0 <= 0.0 or q <= 0.0:
            Delta_sigma_mid.append(0.0)
            rho_c.append(0.0)
            rho_c_center_list.append(0.0)
            rho_c_edge_list.append(0.0)
            rho_total_center_list.append(float(rho_i_x))
            rho_total_edge_list.append(float(rho_i_x))
            if use_craig_delta_sigma:
                rho_c_method_list.append("mv slices (Craig Δσ center+edge)" if consol_method_value == "mv" else "Cc slices (Craig Δσ center+edge)")
            else:
                rho_c_method_list.append("mv slices (Δσ=q center+edge)" if consol_method_value == "mv" else "Cc slices (Δσ=q center+edge)")
            S_cc_slices_by_chainage[x_val] = 0.0
            S_mv_slices_by_chainage[x_val] = 0.0
            layer_tables_by_chainage[x_val] = pd.DataFrame(columns=[
                "z_mid_m", "dz_m", "sigma_v0_prime_kpa", "delta_sigma_kpa",
                "sigma_vf_prime_kpa", "ds_m", "s_cum_m",
            ])
            continue

        Delta_sigma_mid.append(delta_sigma_func_center(0.5 * h0))

        # ---- CENTRE ----
        S_cc_center_m, _ = settlement_primary_1d(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=delta_sigma_func_center,
            stress=stress_inputs,
            n_slices=n_slices_settlement,
            log_base=log_base_settlement,
        )
        layer_table = build_settlement_integration_table(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=delta_sigma_func_center,
            stress=stress_inputs,
            n_slices=n_slices_settlement,
            log_base=log_base_settlement,
        )
        mv_center = build_settlement_integration_table_mv(
            H0=h0,
            m_v=float(m_v),
            delta_sigma_func=delta_sigma_func_center,
            stress=stress_inputs,
            n_slices=int(n_slices_settlement),
        )
        if isinstance(mv_center, dict):
            if "S_total_m" in mv_center:
                S_mv_center_m = float(mv_center["S_total_m"])
            else:
                mv_rows_center = mv_center.get("rows")
                S_mv_center_m = float(mv_rows_center["s_cum_m"].iloc[-1]) if mv_rows_center is not None and len(mv_rows_center) > 0 else 0.0
        else:
            S_mv_center_m = float(mv_center[1]) if len(mv_center) > 1 else 0.0

        rho_c_center = float(S_mv_center_m) if consol_method_value == "mv" else float(S_cc_center_m)

        # ---- EDGE ----
        S_cc_edge_m, _ = settlement_primary_1d(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=delta_sigma_func_edge,
            stress=stress_inputs,
            n_slices=n_slices_settlement,
            log_base=log_base_settlement,
        )
        mv_edge = build_settlement_integration_table_mv(
            H0=h0,
            m_v=float(m_v),
            delta_sigma_func=delta_sigma_func_edge,
            stress=stress_inputs,
            n_slices=int(n_slices_settlement),
        )
        if isinstance(mv_edge, dict):
            if "S_total_m" in mv_edge:
                S_mv_edge_m = float(mv_edge["S_total_m"])
            else:
                mv_rows_edge = mv_edge.get("rows")
                S_mv_edge_m = float(mv_rows_edge["s_cum_m"].iloc[-1]) if mv_rows_edge is not None and len(mv_rows_edge) > 0 else 0.0
        else:
            S_mv_edge_m = float(mv_edge[1]) if len(mv_edge) > 1 else 0.0

        rho_c_edge = float(S_mv_edge_m) if consol_method_value == "mv" else float(S_cc_edge_m)
        rho_c_x = float(rho_c_center)
        rho_total_center = float(rho_i_x) + float(rho_c_center)
        rho_total_edge = float(rho_i_x) + float(rho_c_edge)

        S_cc_slices_by_chainage[x_val] = float(S_cc_center_m)
        S_mv_slices_by_chainage[x_val] = float(S_mv_center_m)

        layer_tables_by_chainage[x_val] = layer_table.copy()
        if len(layer_table) > 0:
            sigma_v0_prime_mins.append(layer_table["sigma_v0_prime_kpa"].min())

        # --- Local monotonicity check (evidence-based, same chainage) ---
        # Settlement should increase if the applied load increases at the SAME x (same σ'0 + same H0).
        # This is the only valid monotonicity sanity check.
        eps = 0.05  # 5% load bump (small enough to be "local")
        q_base = float(q)  # q_equiv_kpa at this chainage
        S_base = float(S_cc_center_m)
        if use_craig_delta_sigma:
            S_plus_func = (
                lambda z, qval=q_base * (1.0 + eps), Bval=float(B):
                float(delta_sigma_strip(q=float(qval), B=float(Bval), z=float(z), x=0.0))
            )
        else:
            S_plus_func = (lambda z, qval=q_base * (1.0 + eps): float(qval))
        S_plus_m, _ = settlement_primary_1d(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=S_plus_func,
            stress=stress_inputs,
            n_slices=60,
            log_base=10,
        )
        tol = 1e-9
        if S_plus_m + tol < S_base:
            monotonic_warnings.append({
                "x": float(x_val),
                "q_equiv_kpa": q_base,
                "S_base_m": S_base,
                "q_plus_kpa": q_base * (1.0 + eps),
                "S_plus_m": float(S_plus_m),
                "message": "Local monotonicity failed: load increased at same chainage but settlement decreased. Check σ′0/Δσ/log handling.",
            })

        rho_c.append(rho_c_x)
        rho_c_center_list.append(float(rho_c_center))
        rho_c_edge_list.append(float(rho_c_edge))
        rho_total_center_list.append(float(rho_total_center))
        rho_total_edge_list.append(float(rho_total_edge))
        if use_craig_delta_sigma:
            rho_c_method_list.append("mv slices (Craig Δσ center+edge)" if consol_method_value == "mv" else "Cc slices (Craig Δσ center+edge)")
        else:
            rho_c_method_list.append("mv slices (Δσ=q center+edge)" if consol_method_value == "mv" else "Cc slices (Δσ=q center+edge)")

    rho = [float(v) for v in rho_total_center_list]
    rho_total_center = [float(v) for v in rho_total_center_list]
    rho_total_edge = [float(v) for v in rho_total_edge_list]
    delta_rho_total_edge_minus_center = [
        float(re - rc) for re, rc in zip(rho_total_edge_list, rho_total_center_list)
    ]
    Z_rev = [zf + r for zf, r in zip(Z_finish, rho)]
    df = pd.DataFrame({
        "x": chainages, "ground level": ground, "bedrock level": bedrock, "H0": H0_list,
        "Z_finish": Z_finish, "H_fill": H_fill, "B_base": B_base, "A_trap": Atrap,
        "W_line": Wline, "q_equiv": qeq, "q_immediate": q_immediate, "Is_immediate": Is_immediate,
        "Eu_kpa": Eu_immediate, "rho_i": rho_i, "Delta_sigma_mid": Delta_sigma_mid,
        "rho_c": rho_c, "rho": rho, "Z_rev": Z_rev,
        "rho_c_center_m": rho_c_center_list, "rho_c_edge_m": rho_c_edge_list,
        "rho_total_center_m": rho_total_center, "rho_total_edge_m": rho_total_edge,
        "delta_rho_total_edge_minus_center_m": delta_rho_total_edge_minus_center,
        "rho_total_center_mm": [1000.0 * float(v) for v in rho_total_center],
        "rho_total_edge_mm": [1000.0 * float(v) for v in rho_total_edge],
        # Backward-compatible aliases used in existing UI checks.
        "rho_c_centre (m)": rho_c_center_list,
        "rho_c_edge (m)": rho_c_edge_list,
        "rho_total_centre (m)": rho_total_center,
        "rho_total_edge (m)": rho_total_edge,
        "delta_rho_c_edge_minus_centre (m)": [
            float(re - rc) for re, rc in zip(rho_c_edge_list, rho_c_center_list)
        ],
        "rho_c_method": rho_c_method_list,
    })

    layers_df_for_x_section = None
    layer_table_x0 = None
    if len(layer_tables_by_chainage) > 0:
        idx_sec = (df["x"] - x_section).abs().idxmin()
        x_sec_val = float(df.loc[idx_sec, "x"])
        layers_df_for_x_section = layer_tables_by_chainage.get(x_sec_val, None)
        idx_x0 = (df["x"] - 0.0).abs().idxmin()
        x0_val = float(df.loc[idx_x0, "x"])
        layer_table_x0 = layer_tables_by_chainage.get(x0_val, None)
        if (layer_table_x0 is None or len(layer_table_x0) == 0) and any(len(t) > 0 for t in layer_tables_by_chainage.values()):
            # Fallback: use first available slice table if x=0 has no clay
            for t in layer_tables_by_chainage.values():
                if t is not None and len(t) > 0:
                    layer_table_x0 = t
                    break

    settlement_summary = []
    for x_check in [x_worked, 0.0, 500.0, 1000.0]:
        idx = (df["x"] - x_check).abs().idxmin()
        r = df.loc[idx]
        x_val = float(r["x"])
        lt = layer_tables_by_chainage.get(x_val)
        sigma_min = float(lt["sigma_v0_prime_kpa"].min()) if lt is not None and len(lt) > 0 else float("nan")
        settlement_summary.append({
            "x": x_val,
            "H0": float(r["H0"]),
            "q_equiv": float(r["q_equiv"]),
            "S_primary_m": float(rho_c[df.index.get_loc(idx)]),
            "consol_method_used": consol_method_value,
            "S_cc_slices_m": float(S_cc_slices_by_chainage.get(x_val, 0.0)),
            "S_mv_slices_m": float(S_mv_slices_by_chainage.get(x_val, 0.0)),
            "sigma_v0_prime_min_kpa": sigma_min,
            "z_wt_m_used": float(stress_inputs_by_chainage.get(x_val).z_wt_m) if x_val in stress_inputs_by_chainage else float("nan"),
        })
    key_rows = []
    def add_row(label, idx):
        r = df.loc[idx]
        key_rows.append({"label": label, "x": float(r["x"]), "H0": float(r["H0"]),
            "H_fill": float(r["H_fill"]), "B_base": float(r["B_base"]), "q_equiv": float(r["q_equiv"]),
            "rho_i": float(r["rho_i"]), "rho_c": float(r["rho_c"]), "rho": float(r["rho"]),
            "Z_finish": float(r["Z_finish"]), "Z_rev": float(r["Z_rev"])})
    add_row("A (start)", df.index[0])
    add_row("Mid", (df["x"] - 500.0).abs().idxmin())
    add_row("B (end)", df.index[-1])
    add_row("Max fill height", df["H_fill"].idxmax())
    add_row("Max total settlement", df["rho"].idxmax())
    add_row("Min clay thickness (H0)", df["H0"].idxmin())
    key_df = pd.DataFrame(key_rows)
    idx_w = (df["x"] - float(x_worked)).abs().idxmin()
    rw = df.loc[idx_w]
    z_mid = 0.5 * float(rw["H0"])
    sigma_total_mid = stress_inputs.gamma_unsat_kN_m3 * min(z_mid, stress_inputs.z_wt_m)
    if z_mid > stress_inputs.z_wt_m:
        sigma_total_mid += stress_inputs.gamma_sat_kN_m3 * (z_mid - stress_inputs.z_wt_m)
    u_mid = 0.0 if z_mid <= stress_inputs.z_wt_m else stress_inputs.gamma_w_kN_m3 * (z_mid - stress_inputs.z_wt_m)
    sigma_eff_mid = sigma_total_mid - u_mid
    sigma_eff_mid_clipped = sigma_v0_prime_kpa(z_mid, stress_inputs)
    delta_sigma_mid = Delta_sigma_mid[df.index.get_loc(idx_w)]
    immediate_q_formula_text = "q = γ_fill * H_fill" if use_lecture_q else "q = q_equiv (trapezoid)"
    report = []
    report.append(f"WEEK 1 WORKED EXAMPLE @ x = {float(rw['x']):.1f} m")
    report.append("")
    report.append("Clay thickness")
    report.append("  H0 = ground level - bedrock level")
    report.append(f"  = {float(rw['ground level']):.3f} - {float(rw['bedrock level']):.3f} = {float(rw['H0']):.3f} m")
    report.append("")
    report.append("Trapezoid → equivalent uniform base pressure")
    report.append("  B_base = B_top + 2 m H_fill")
    report.append(f"  = {B_top:.3f} + 2*{m:.3f}*{float(rw['H_fill']):.3f} = {float(rw['B_base']):.3f} m")
    report.append("  A = (B_top + B_base)/2 * H_fill")
    report.append(f"  = ({B_top:.3f} + {float(rw['B_base']):.3f})/2 * {float(rw['H_fill']):.3f} = {float(rw['A_trap']):.3f} m^2")
    report.append("  W = γ_fill * A")
    report.append(f"  = {gamma_fill:.3f} * {float(rw['A_trap']):.3f} = {float(rw['W_line']):.3f} kN/m")
    report.append("  q = W / B_base")
    report.append(f"  = {float(rw['W_line']):.3f} / {float(rw['B_base']):.3f} = {float(rw['q_equiv']):.3f} kPa")
    report.append("")
    report.append("Immediate settlement (lecture)")
    report.append("  ρ_i = q B I_s / E_u  (use B = B_base)")
    report.append(f"  q method: {immediate_q_formula_text}")
    report.append(f"  E_u = (E/c_u)c_u = {Eu_over_cu:.1f}*{cu:.3f} = {float(rw['Eu_kpa']):.3f} kPa")
    report.append(f"  I_s = {float(rw['Is_immediate']):.3f}")
    report.append(f"  ρ_i = ({float(rw['q_immediate']):.3f}*{float(rw['B_base']):.3f}*{float(rw['Is_immediate']):.3f})/{float(rw['Eu_kpa']):.3f} = {float(rw['rho_i']):.3f} m")
    report.append("")
    report.append("Pre-fill effective stress σ′v0 (natural ground only)")
    report.append("  σv(z) = γ_unsat z (z ≤ z_wt); else γ_unsat z_wt + γ_sat (z - z_wt)")
    report.append(f"  σv(z_mid={z_mid:.3f}) = {sigma_total_mid:.3f} kPa")
    report.append(f"  u(z_mid) = γ_w (z - z_wt) = {u_mid:.3f} kPa")
    report.append(f"  σ′v0 = σv - u = {sigma_eff_mid:.3f} kPa (clipped to {sigma_eff_mid_clipped:.3f} kPa)")
    report.append("")
    if use_craig_delta_sigma:
        report.append("Δσ(z) computed using Craig strip method (Barnes equivalent): Δσ = q * Iσ(a/z, b/z)")
        report.append("Stress points computed for both centre (x=0) and edge (x=B/2).")
        report.append(f"  Δσ(z_mid, centre) = {delta_sigma_mid:.3f} kPa")
    else:
        report.append("Quick approximation: Δσ(z)=q constant with depth (upper bound)")
        report.append(f"  Δσ = {delta_sigma_mid:.3f} kPa")
    report.append("")
    report.append("Primary consolidation (Terzaghi 1D, log10)")
    report.append("  ds = (Cc/(1+e0)) dz log10((σ′0+Δσ)/σ′0)")
    report.append(f"  ρ_c (sum over slices) = {float(rw['rho_c']):.3f} m")
    report.append("")
    report.append("Total settlement and revised level")
    report.append("  ρ = ρ_i + ρ_c")
    report.append(f"  = {float(rw['rho_i']):.3f} + {float(rw['rho_c']):.3f} = {float(rw['rho']):.3f} m")
    report.append("  Z_rev = Z_finish + ρ")
    report.append(f"  = {float(rw['Z_finish']):.3f} + {float(rw['rho']):.3f} = {float(rw['Z_rev']):.3f} mAOD")
    report_df = pd.DataFrame({"text": report})
    summary = []
    summary.append("WEEK 1 SUMMARY")
    summary.extend(EVIDENCE_NOTES)
    summary.append("Finished level constraint: Z_finish(x)=max(Z_design(x), 55.0 m AOD) using 10-year flood level 54.0 m AOD + 1 m freeboard.")
    summary.append("WT depth for σ′v0 computed from AOD: z_wt(x)=max(0, Z_ground(x)−54.0).")
    summary.append(f"Max H_fill = {df['H_fill'].max():.3f} m")
    summary.append(f"Max ρ total = {df['rho'].max():.3f} m")
    summary.append(f"Max ρ_i = {df['rho_i'].max():.3f} m")
    summary.append(f"Max ρ_c = {df['rho_c'].max():.3f} m")
    summary_df = pd.DataFrame({"text": summary})

    if run_preliminary_quick_stage:
        delta_sigma_quick = [float(gamma_fill) * float(h) for h in H_fill]
        rho_c_quick = [float(m_v) * dsq * float(h0) for dsq, h0 in zip(delta_sigma_quick, H0_list)]
        rho_total_quick = [float(ri) + float(rcq) for ri, rcq in zip(rho_i, rho_c_quick)]
        Z_post_no_allow = [float(zf) - float(rtq) for zf, rtq in zip(Z_finish, rho_total_quick)]
        Z_req_construct = [float(zf) + float(rtq) for zf, rtq in zip(Z_finish, rho_total_quick)]
        Z_peak_construct = max(
            float(zreq) + float(grade) * abs(float(x) - float(x_c))
            for x, zreq in zip(chainages, Z_req_construct)
        )
        Z_construct_stage1 = [
            float(Z_peak_construct) - float(grade) * abs(float(x) - float(x_c))
            for x in chainages
        ]
        Z_post_stage1 = [float(zc) - float(rtq) for zc, rtq in zip(Z_construct_stage1, rho_total_quick)]
        quick_stage_df = pd.DataFrame({
            "x": chainages,
            "Z_finish": Z_finish,
            "rho_total_quick": rho_total_quick,
            "Z_req_construct": Z_req_construct,
            "Z_construct_stage1": Z_construct_stage1,
            "Z_post_stage1": Z_post_stage1,
            "Z_post_no_allow": Z_post_no_allow,
        })
        no_allow_violations_quick = [
            float(x)
            for x, zpost in zip(chainages, Z_post_no_allow)
            if float(zpost) < float(Z_MIN_FINISH_AOD_M)
        ]
        flood_violations_quick = [
            float(x)
            for x, zpost in zip(chainages, Z_post_stage1)
            if float(zpost) < float(Z_MIN_FINISH_AOD_M)
        ]
    else:
        quick_stage_df = pd.DataFrame(columns=[
            "x", "Z_finish", "rho_total_quick", "Z_req_construct", "Z_construct_stage1", "Z_post_stage1", "Z_post_no_allow",
        ])
        no_allow_violations_quick = []
        flood_violations_quick = []

    grade_slopes = [
        abs(
            (float(quick_stage_df["Z_construct_stage1"].iloc[i + 1]) - float(quick_stage_df["Z_construct_stage1"].iloc[i]))
            / float(dx)
        )
        for i in range(len(quick_stage_df) - 1)
    ] if len(quick_stage_df) > 1 and "Z_construct_stage1" in quick_stage_df.columns else []
    grade_target = float(grade)
    grade_tol = 1e-6
    grade_check_ok = [abs(s - grade_target) <= grade_tol for s in grade_slopes]
    grade_violations = [float(chainages[i]) for i, ok in enumerate(grade_check_ok) if not ok]

    rho_total_detailed = [float(v) for v in rho_total_center]
    if run_detailed_stage2_profile:
        rho_total_stage2_worst = [
            max(float(rc), float(re))
            for rc, re in zip(rho_total_center_list, rho_total_edge_list)
        ]
        Z_req_construct_stage2 = [float(zf) + float(rt) for zf, rt in zip(Z_finish, rho_total_stage2_worst)]
        Z_peak_construct_stage2 = max(
            float(zreq) + float(grade) * abs(float(x) - float(x_c))
            for x, zreq in zip(chainages, Z_req_construct_stage2)
        )
        Z_construct_stage2 = [
            float(Z_peak_construct_stage2) - float(grade) * abs(float(x) - float(x_c))
            for x in chainages
        ]
        Z_post_stage2_center = [float(zc) - float(rt) for zc, rt in zip(Z_construct_stage2, rho_total_center_list)]
        Z_post_stage2_edge = [float(zc) - float(rt) for zc, rt in zip(Z_construct_stage2, rho_total_edge_list)]
        Z_post_stage2 = [
            min(float(zc), float(ze))
            for zc, ze in zip(Z_post_stage2_center, Z_post_stage2_edge)
        ]
        rho_total_detailed = [float(v) for v in rho_total_stage2_worst]
        detailed_stage2_df = pd.DataFrame({
            "x": chainages,
            "Z_finish": Z_finish,
            "rho_total_detailed": rho_total_detailed,
            "rho_total_stage2_worst": rho_total_stage2_worst,
            "rho_total_center": rho_total_center_list,
            "rho_total_edge": rho_total_edge_list,
            "Z_req_construct_stage2": Z_req_construct_stage2,
            "Z_construct_stage2": Z_construct_stage2,
            "Z_post_stage2": Z_post_stage2,
            "Z_post_stage2_center": Z_post_stage2_center,
            "Z_post_stage2_edge": Z_post_stage2_edge,
        })
        flood_violations_stage2 = [
            float(x)
            for x, zc, ze in zip(chainages, Z_post_stage2_center, Z_post_stage2_edge)
            if float(zc) < float(Z_MIN_FINISH_AOD_M) or float(ze) < float(Z_MIN_FINISH_AOD_M)
        ]
        grade_slopes_stage2 = [
            abs((float(Z_construct_stage2[i + 1]) - float(Z_construct_stage2[i])) / float(dx))
            for i in range(len(Z_construct_stage2) - 1)
        ] if len(Z_construct_stage2) > 1 else []
        grade_violations_stage2 = [
            float(chainages[i])
            for i, s in enumerate(grade_slopes_stage2)
            if abs(float(s) - float(grade)) > grade_tol
        ]
    else:
        detailed_stage2_df = pd.DataFrame(columns=[
            "x", "Z_finish", "rho_total_detailed", "rho_total_stage2_worst",
            "rho_total_center", "rho_total_edge",
            "Z_req_construct_stage2", "Z_construct_stage2", "Z_post_stage2",
            "Z_post_stage2_center", "Z_post_stage2_edge",
        ])
        flood_violations_stage2 = []
        grade_violations_stage2 = []
        grade_slopes_stage2 = []

    if any(not np.isfinite(val) for val in rho_c):
        raise ValueError("Non-finite consolidation settlement encountered.")
    if len(rho_c) > 0 and min(rho_c) < 0:
        raise ValueError("Negative consolidation settlement encountered.")
    if sigma_v0_prime_mins and min(sigma_v0_prime_mins) <= 0:
        raise ValueError("σ′v0 <= 0 detected; check stress model inputs.")

    neg_dsigma_chainages = []
    for i, ds in enumerate(Delta_sigma_mid):
        if ds < 0 and H0_list[i] > 0:
            neg_dsigma_chainages.append((chainages[i], ds))
    if neg_dsigma_chainages:
        pass  # UI will show st.warning

    immediate_stage_df_x_section = pd.DataFrame(
        immediate_stage_rows_x_section,
        columns=["stage", "Hk_m", "qk_kpa", "rho_i_k_m", "delta_rho_i_k_m"],
    )

    return (
        df,
        key_df,
        report_df,
        summary_df,
        layers_df_for_x_section,
        settlement_summary,
        neg_dsigma_chainages,
        layer_table_x0,
        immediate_stage_df_x_section,
        monotonic_warnings,
        quick_stage_df,
        no_allow_violations_quick,
        flood_violations_quick,
        grade_violations,
        grade_slopes,
        detailed_stage2_df,
        flood_violations_stage2,
        grade_violations_stage2,
        grade_slopes_stage2,
    )


# =============================================================================
# 4) EXPORT WEEK 1
# =============================================================================

def export_week1_excel(df, key_df, report_df, summary_df, layers_df_for_x_section=None, immediate_stage_df_x_section=None):
    ensure_dir(OUTPUT_FOLDER)
    base_path = os.path.join(OUTPUT_FOLDER, OUTPUT_EXCEL_NAME)
    out_path = base_path
    if os.path.exists(base_path):
        try:
            with open(base_path, "a"):
                pass
        except PermissionError:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(OUTPUT_EXCEL_NAME)
            out_path = os.path.join(OUTPUT_FOLDER, f"{name}_{stamp}{ext}")
    inputs = {
        "L": L, "dx": dx, "ground_A": ground_A, "ground_B": ground_B,
        "bedrock_c": bedrock_c, "x_c": x_c, "bedrock_goes_down_towards_B": bedrock_goes_down_towards_B,
        "B_top": B_top, "m": m, "flood_level": flood_level, "freeboard": freeboard,
        "Zmin_finish": Zmin_finish, "Z_peak_finish": Z_peak_finish, "grade": grade,
        "gamma_fill": gamma_fill, "gamma_clay": gamma_clay, "gamma_w": gamma_w,
        "water_table_at_ground": water_table_at_ground, "cu": cu, "Is": Is, "Eu_over_cu": Eu_over_cu,
        "immediate_settlement_method": immediate_settlement_method,
        "q_immediate_method": q_immediate_method,
        "influence_factor_input_mode": influence_factor_input_mode,
        "I_s_input": I_s_input,
        "mu1_input": mu1_input,
        "staged_construction_lifts": staged_construction_lifts,
        "lift_height_m": lift_height_m,
        "consol_method": consol_method, "m_v": m_v, "Cc": Cc, "e0": e0, "x_worked": x_worked,
        "consolidation_depth_method": consolidation_depth_method,
        "N_layers": N_layers,
        "consol_stress_point": consol_stress_point,
        "delta_sigma_mode": delta_sigma_mode,
        "run_preliminary_quick_stage": run_preliminary_quick_stage,
        "run_detailed_stage2_profile": run_detailed_stage2_profile,
        "Uv_targets": str(Uv_targets), "Cv_m2_per_s": Cv_m2_per_s,
        "vertical_drainage": vertical_drainage,
    }
    inputs_df = pd.DataFrame([inputs]).T.reset_index()
    inputs_df.columns = ["input", "value"]
    report_all = pd.concat([report_df, pd.DataFrame({"text": ["", "----------------", ""]}), summary_df], ignore_index=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        inputs_df.to_excel(writer, sheet_name="Inputs", index=False)
        df.to_excel(writer, sheet_name="Week1_Chainage", index=False)
        key_df.to_excel(writer, sheet_name="Week1_KeySections", index=False)
        report_all.to_excel(writer, sheet_name="Week1_Report", index=False)
        if layers_df_for_x_section is not None and len(layers_df_for_x_section) > 0:
            layers_df_for_x_section.to_excel(writer, sheet_name="Week1_ConsolLayers_xSection", index=False)
        else:
            note_df = pd.DataFrame([{"note": "Layered mode not used. Consolidation layers sheet applies only to Layered depth method."}])
            note_df.to_excel(writer, sheet_name="Week1_ConsolLayers_xSection", index=False)
        if immediate_stage_df_x_section is not None and len(immediate_stage_df_x_section) > 0:
            immediate_stage_df_x_section.to_excel(writer, sheet_name="Week1_ImmediateStages_xSection", index=False)
        else:
            note_df_stage = pd.DataFrame([{"note": "Staged immediate settlement not enabled or no fill at x_section."}])
            note_df_stage.to_excel(writer, sheet_name="Week1_ImmediateStages_xSection", index=False)
        for name in ["Inputs", "Week1_Chainage", "Week1_KeySections", "Week1_Report", "Week1_ConsolLayers_xSection", "Week1_ImmediateStages_xSection"]:
            ws = writer.sheets[name]
            ws.freeze_panes = "B2"
    return out_path


# =============================================================================
# 5) WEEK 2 FUNCTIONS
# =============================================================================

def week2_run(df_week1_chainage: pd.DataFrame):
    """Compute vertical consolidation time along chainage (Week 2A only)."""
    if "H0" not in df_week1_chainage.columns:
        raise KeyError("Week 1 dataframe must contain 'H0' column.")
    rows = []
    for _, r in df_week1_chainage.iterrows():
        x, H = float(r["x"]), float(r["H0"])
        if H <= 0.0:
            rows.append({
                "x": x,
                "H0": H,
                "vertical_drainage": vertical_drainage,
                "Hd_m": 0.0,
                "Cv_m2_per_s": Cv_m2_per_s,
            })
            continue
        times_df = consolidation_times_table(
            Cv_m2_per_s=Cv_m2_per_s,
            H0_m=H,
            drainage=vertical_drainage,
            U_targets=Uv_targets,
        )
        row = {
            "x": x,
            "H0": H,
            "vertical_drainage": vertical_drainage,
        }
        if len(times_df) > 0:
            row["Hd_m"] = float(times_df.iloc[0]["Hd_m"])
            row["Cv_m2_per_s"] = float(times_df.iloc[0]["Cv_m2_per_s"])
            for col in times_df.columns:
                if col.startswith("U") and ("Tv" in col or "t_years" in col):
                    row[col] = float(times_df.iloc[0][col])
            # Sanity gate: t20 < t50 < t90
            try:
                t20 = row.get("U20_t_years", None)
                t50 = row.get("U50_t_years", None)
                t90 = row.get("U90_t_years", None)
                if all(v is not None for v in [t20, t50, t90]):
                    if not (t20 < t50 < t90):
                        raise ValueError(f"Consolidation time monotonicity failed at x={x:.1f} m.")
            except KeyError:
                pass
        rows.append(row)
    return pd.DataFrame(rows)

import numpy as np
import pandas as pd

def summarize_x0_settlement_and_consolidation(layer_table_x0: pd.DataFrame, cons_times_df: pd.DataFrame) -> dict:
    """
    Summarise min/max slice quantities at x=0.
    Assumes layer_table_x0 has columns:
      z_mid_m, sigma_v0_prime_kpa, delta_sigma_kpa, ds_m, s_cum_m
    Assumes cons_times_df contains row for x=0 with:
      Hd_m, U20_Tv, U20_t_years, U50_Tv, U50_t_years, U90_Tv, U90_t_years
    """
    out = {}

    if layer_table_x0 is None or layer_table_x0.empty:
        out["ok"] = False
        out["reason"] = "layer_table_x0 is empty"
        return out

    df = layer_table_x0.copy()

    # --- ranges over depth (slices) ---
    out["ok"] = True
    out["sigma_v0_prime_min_kpa"] = float(df["sigma_v0_prime_kpa"].min())
    out["sigma_v0_prime_max_kpa"] = float(df["sigma_v0_prime_kpa"].max())

    out["delta_sigma_min_kpa"] = float(df["delta_sigma_kpa"].min())
    out["delta_sigma_max_kpa"] = float(df["delta_sigma_kpa"].max())

    out["ds_min_m"] = float(df["ds_m"].min())
    out["ds_max_m"] = float(df["ds_m"].max())

    # where ds is largest (dominant slice)
    idx = int(df["ds_m"].idxmax())
    out["ds_max_z_mid_m"] = float(df.loc[idx, "z_mid_m"])
    out["ds_max_sigma_v0_prime_kpa"] = float(df.loc[idx, "sigma_v0_prime_kpa"])
    out["ds_max_delta_sigma_kpa"] = float(df.loc[idx, "delta_sigma_kpa"])

    # total primary consolidation settlement at x=0
    out["S_primary_m"] = float(df["s_cum_m"].iloc[-1])
    out["S_primary_mm"] = out["S_primary_m"] * 1000.0

    # --- consolidation time row (x=0) ---
    times_row = None
    if cons_times_df is not None and not cons_times_df.empty:
        if "x" in cons_times_df.columns:
            i0 = int((cons_times_df["x"].astype(float) - 0.0).abs().idxmin())
            times_row = cons_times_df.loc[i0]
        else:
            times_row = cons_times_df.iloc[0]

    if times_row is not None:
        for k in ["Hd_m", "U20_Tv", "U20_t_years", "U50_Tv", "U50_t_years", "U90_Tv", "U90_t_years"]:
            if k in times_row.index:
                try:
                    out[k] = float(times_row[k])
                except (TypeError, ValueError):
                    pass
        if not all(k in out for k in ["U20_t_years", "U50_t_years", "U90_t_years"]):
            out["consol_times_missing"] = True

    return out

def export_add_week2_sheets(out_path: str, week2_chainage_df: pd.DataFrame) -> str:
    """Add Week2_ConsolTime (vertical consolidation) sheet to workbook."""
    if not os.path.exists(out_path):
        raise FileNotFoundError(f"Cannot find Week 1 workbook: {out_path}")
    try:
        with pd.ExcelWriter(out_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            week2_chainage_df.to_excel(writer, sheet_name="Week2_ConsolTime", index=False)
        return out_path
    except PermissionError:
        folder = os.path.dirname(out_path) or "."
        base = os.path.basename(out_path)
        name, ext = os.path.splitext(base)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        copy_path = os.path.join(folder, f"{name}_week2_{stamp}{ext}")
        shutil.copyfile(out_path, copy_path)
        with pd.ExcelWriter(copy_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            week2_chainage_df.to_excel(writer, sheet_name="Week2_ConsolTime", index=False)
        return copy_path


def export_additional_csvs(
    df,
    week2_chainage_df,
    layer_table_x0=None,
    quick_stage_df=None,
    detailed_stage2_df=None,
    run_detailed_stage2_profile=False,
):
    """CSV exports for settlement and consolidation evidence."""
    ensure_dir(OUTPUT_FOLDER)
    paths = {}

    if df is not None and len(df) > 0:
        sett_df = pd.DataFrame({
            "x_m": df["x"],
            "S_primary_m": df["rho_c"],
            "S_primary_mm": df["rho_c"] * 1000.0,
            "rho_c_center_m": df["rho_c_center_m"],
            "rho_c_edge_m": df["rho_c_edge_m"],
            "rho_total_center_m": df["rho_total_center_m"],
            "rho_total_edge_m": df["rho_total_edge_m"],
            "delta_rho_total_edge_minus_center_m": df["delta_rho_total_edge_minus_center_m"],
            "rho_total_center_mm": df["rho_total_center_mm"],
            "rho_total_edge_mm": df["rho_total_edge_mm"],
        })
        p_sett = os.path.join(OUTPUT_FOLDER, "settlement_vs_chainage.csv")
        sett_df.to_csv(p_sett, index=False)
        paths["settlement_vs_chainage"] = p_sett

    if layer_table_x0 is not None and len(layer_table_x0) > 0:
        p_layer = os.path.join(OUTPUT_FOLDER, "settlement_layer_table_x0.csv")
        layer_table_x0.to_csv(p_layer, index=False)
        paths["settlement_layer_table_x0"] = p_layer

    if week2_chainage_df is not None and len(week2_chainage_df) > 0:
        p_consol = os.path.join(OUTPUT_FOLDER, "consolidation_times.csv")
        week2_chainage_df.to_csv(p_consol, index=False)
        paths["consolidation_times"] = p_consol

    if df is not None and len(df) > 0:
        z_build_vals = df["Z_rev"]
        z_post_vals = df["Z_finish"]
        settlement_vals = df["rho"]
        note_text = "Z_construct = Z_design + settlement (design as post-settlement target)."
        if (
            run_detailed_stage2_profile
            and detailed_stage2_df is not None
            and len(detailed_stage2_df) == len(df)
            and "Z_construct_stage2" in detailed_stage2_df.columns
            and "Z_post_stage2" in detailed_stage2_df.columns
            and "rho_total_detailed" in detailed_stage2_df.columns
        ):
            z_build_vals = detailed_stage2_df["Z_construct_stage2"]
            z_post_vals = detailed_stage2_df["Z_post_stage2"]
            settlement_vals = detailed_stage2_df["rho_total_detailed"]
            note_text = "Stage-2 detailed profile: crowned construction surface offsets detailed settlement (ρ_i + ρ_c) and preserves 1:200."
        elif (
            quick_stage_df is not None
            and len(quick_stage_df) == len(df)
            and "Z_construct_stage1" in quick_stage_df.columns
            and "Z_post_stage1" in quick_stage_df.columns
            and "rho_total_quick" in quick_stage_df.columns
        ):
            z_build_vals = quick_stage_df["Z_construct_stage1"]
            z_post_vals = quick_stage_df["Z_post_stage1"]
            settlement_vals = quick_stage_df["rho_total_quick"]
            note_text = "Stage-1 lecture profile: crowned construction surface offsets quick settlement and preserves 1:200."
        align_df = pd.DataFrame({
            "chainage_m": df["x"],
            "Z_design_mAOD": df["Z_finish"],
            "settlement_total_m": settlement_vals,
            "Z_construct_mAOD": z_build_vals,
            "Z_post_mAOD": z_post_vals,
            "note": note_text,
        })
        if (
            run_detailed_stage2_profile
            and detailed_stage2_df is not None
            and len(detailed_stage2_df) == len(df)
            and "rho_total_stage2_worst" in detailed_stage2_df.columns
            and "rho_total_center" in detailed_stage2_df.columns
            and "rho_total_edge" in detailed_stage2_df.columns
            and "Z_post_stage2_center" in detailed_stage2_df.columns
            and "Z_post_stage2_edge" in detailed_stage2_df.columns
        ):
            align_df["Z_construct_mAOD"] = detailed_stage2_df["Z_construct_stage2"]
            align_df["Z_post_center_mAOD"] = detailed_stage2_df["Z_post_stage2_center"]
            align_df["Z_post_edge_mAOD"] = detailed_stage2_df["Z_post_stage2_edge"]
            align_df["settlement_total_worst_m"] = detailed_stage2_df["rho_total_stage2_worst"]
            align_df["settlement_total_center_m"] = detailed_stage2_df["rho_total_center"]
            align_df["settlement_total_edge_m"] = detailed_stage2_df["rho_total_edge"]
        p_align = os.path.join(OUTPUT_FOLDER, "alignment_profiles.csv")
        align_df.to_csv(p_align, index=False)
        paths["alignment_profiles"] = p_align

    return paths


# =============================================================================
# 5B) SLOPE STABILITY (WEEK 5) — Short-term undrained circular slip
# =============================================================================

def z_surface(y: float, ground_level: float, Z_finish: float, B_top: float, B_base: float) -> float:
    """Surface elevation (mAOD) at horizontal position y. Embankment trapezoid cross-section."""
    a = B_top / 2.0
    b = B_base / 2.0
    ay = abs(y)
    if ay <= a:
        return Z_finish
    if ay <= b and b > a:
        t = (ay - a) / (b - a)
        return Z_finish + t * (ground_level - Z_finish)
    return ground_level


def z_surface_half(y: float, ground_level: float, Z_finish: float, side: str,
                   B_top: float, B_base: float) -> float:
    """
    Surface elevation for HALF domain (one side slope: crest → toe).
    Used only for slope stability when domain_mode == half.
    """
    y_crest = B_top / 2.0 if side == "Right" else -B_top / 2.0
    y_toe = B_base / 2.0 if side == "Right" else -B_base / 2.0
    if side == "Right":
        if y <= y_crest:
            return Z_finish
        if y <= y_toe:
            t = (y - y_crest) / (y_toe - y_crest)
            return Z_finish + t * (ground_level - Z_finish)
        return ground_level
    else:  # Left
        if y >= y_crest:
            return Z_finish
        if y >= y_toe:
            t = (y_crest - y) / (y_crest - y_toe)
            return Z_finish + t * (ground_level - Z_finish)
        return ground_level


def _z_surface_at_y(y: float, ground_level: float, Z_finish: float, B_top: float, B_base: float) -> float:
    """Surface elevation (mAOD) at horizontal position y (m, centreline=0)."""
    half_top = B_top / 2.0
    half_base = B_base / 2.0
    if abs(y) <= half_top:
        return Z_finish
    if y < -half_base or y > half_base:
        return ground_level
    if y < -half_top:
        t = (y + half_base) / (half_base - half_top)
    else:
        t = (half_base - y) / (half_base - half_top)
    return ground_level + (Z_finish - ground_level) * t


def _circle_ground_intersection(yc: float, zc: float, R: float, ground_level: float) -> tuple:
    """
    Intersect circle (yc,zc,R) with horizontal line z=ground_level.
    Returns (y1, y2) or None if no two intersections.
    """
    D = R**2 - (ground_level - zc)**2
    if D <= 0:
        return None
    s = math.sqrt(D)
    return (yc - s, yc + s)


def _circle_geometry_valid(yc: float, zc: float, R: float, ground_level: float,
                          B_base: float, B_top: float, max_depth_below_ground: float,
                          span_mode: str,
                          bedrock_level: float, depth_constraint_mode: str, bedrock_margin: float = 0.0,
                          domain_mode: str = "full", side: str = "Right", tol: float = 2.0,
                          require_pass_through_embankment: bool = False,
                          Z_finish: float = 0.0, max_cover_height: float = 2.0) -> tuple:
    """
    Geometry validity: circle must intersect ground, satisfy domain span condition,
    and not exceed depth limit. Returns (valid, y_entry, y_exit, fail_reason).

    domain_mode: "half" or "full"
    - FULL: uses span_mode (Base toes, Top width, None)
    - HALF: circle must intersect ground near toe AND have other intersection behind crest.
      (Crest is on embankment, not ground; intersections are at z=ground only.)

    Depth rule:
    - "Limit below ground (current)": z_min >= ground_level - max_depth_below_ground
    - "Limit below bedrock (recommended)": z_min >= bedrock_level - bedrock_margin
    """
    delta = R**2 - (ground_level - zc)**2
    if delta <= 0:
        return (False, None, None, "no_intersection")
    s = math.sqrt(delta)
    y_entry = yc - s
    y_exit = yc + s
    # ensure y_entry < y_exit for consistent ordering
    if y_entry > y_exit:
        y_entry, y_exit = y_exit, y_entry

    if domain_mode == "half":
        y_crest = B_top / 2.0 if side == "Right" else -B_top / 2.0
        y_toe = B_base / 2.0 if side == "Right" else -B_base / 2.0
        toe_near = (abs(y_entry - y_toe) <= tol) or (abs(y_exit - y_toe) <= tol)
        if not toe_near:
            return (False, None, None, "toe")
        if side == "Right":
            behind_crest = min(y_entry, y_exit) <= y_crest - tol
        else:  # Left: behind crest = more to the right, so max >= y_crest + tol
            behind_crest = max(y_entry, y_exit) >= y_crest + tol
        if not behind_crest:
            return (False, None, None, "behind_crest")
        if require_pass_through_embankment:
            if not _arc_passes_through_embankment_half(
                    yc, zc, R, ground_level, Z_finish, B_top, B_base, side, max_cover_height):
                return (False, None, None, "embankment")
    else:
        # FULL mode: existing span logic
        if span_mode == "Base toes (strict)":
            y_toeL = -B_base / 2.0
            y_toeR = +B_base / 2.0
            if not (y_entry <= y_toeL and y_exit >= y_toeR):
                return (False, None, None, "span")
        elif span_mode == "Top width only (lenient)":
            y_topL = -B_top / 2.0
            y_topR = +B_top / 2.0
            if not (y_entry <= y_topL and y_exit >= y_topR):
                return (False, None, None, "span")
        elif span_mode == "None (debug)":
            pass
        else:
            return (False, None, None, "span")

    z_min = zc - R
    if depth_constraint_mode == "Limit below ground (current)":
        if z_min < (ground_level - max_depth_below_ground):
            return (False, None, None, "depth")
    else:
        if z_min < (bedrock_level - bedrock_margin):
            return (False, None, None, "depth")
    return (True, y_entry, y_exit, None)


def _arc_length_lower(y1: float, y2: float, yc: float, zc: float, R: float, ground_level: float) -> float:
    """Arc length of the lower (soil-side) segment of circle from y1 to y2 at z=ground_level."""
    if R <= 0:
        return 0.0
    chord = abs(y2 - y1)
    if chord >= 2 * R:
        return math.pi * R
    theta = 2.0 * math.asin(min(1.0, chord / (2.0 * R)))
    return R * theta


def _circle_arc_z_at_y(y: float, yc: float, zc: float, R: float, lower: bool = True) -> float:
    """z (mAOD) on circle at given y. lower=True gives the lower arc (soil side)."""
    d = R**2 - (y - yc)**2
    if d < 0:
        return float("nan")
    z = zc - math.sqrt(d) if lower else zc + math.sqrt(d)
    return z


def _arc_passes_through_embankment_half(yc: float, zc: float, R: float, ground_level: float,
                                        Z_finish: float, B_top: float, B_base: float,
                                        side: str, max_cover_height: float, Ns: int = 40) -> bool:
    """
    Check that slip arc passes through the embankment on the slope face (crest→toe).
    Sample Ns y-points on the slope; valid if arc is below surface somewhere AND
    comes within max_cover_height of the surface.
    """
    y_crest = B_top / 2.0 if side == "Right" else -B_top / 2.0
    y_toe = B_base / 2.0 if side == "Right" else -B_base / 2.0
    y_min, y_max = min(y_crest, y_toe), max(y_crest, y_toe)
    y_pts = np.linspace(y_min, y_max, Ns)
    covers = []
    for y in y_pts:
        z_surf = z_surface_half(y, ground_level, Z_finish, side, B_top, B_base)
        rad = R**2 - (y - yc)**2
        if rad <= 0:
            continue
        z_arc = zc - math.sqrt(rad)
        cover = z_surf - z_arc
        if cover > 0:
            covers.append(cover)
    if not covers:
        return False  # (a) no point where arc is below surface
    return min(covers) <= max_cover_height  # (b) arc comes within max_cover_height of surface


def _slice_area_and_centroid(y_left: float, y_right: float, yc: float, zc: float, R: float,
                             ground_level: float, Z_finish: float, B_top: float, B_base: float,
                             n_integration: int = 20) -> tuple:
    """
    Area (m²) and (y_centroid, z_centroid) of failure mass in vertical slice.
    Failure mass = above slip arc, below ground/fill surface.
    """
    y_pts = np.linspace(y_left, y_right, n_integration + 1)
    dz_dy = []
    for y in y_pts:
        z_top = _z_surface_at_y(y, ground_level, Z_finish, B_top, B_base)
        z_arc = _circle_arc_z_at_y(y, yc, zc, R, lower=True)
        if np.isnan(z_arc) or z_top <= z_arc:
            dz_dy.append(0.0)
        else:
            dz_dy.append(z_top - z_arc)
    dz_arr = np.array(dz_dy)
    dy = (y_right - y_left) / n_integration
    try:
        area = np.trapezoid(dz_arr, y_pts)
    except AttributeError:
        area = float(((dz_arr[:-1] + dz_arr[1:]) * 0.5 * (y_pts[1:] - y_pts[:-1])).sum())
    if area <= 0:
        return (0.0, (y_left + y_right) / 2.0, ground_level)
    try:
        y_c = np.trapezoid(y_pts * dz_arr, y_pts)
    except AttributeError:
        y_c = float((((y_pts * dz_arr)[:-1] + (y_pts * dz_arr)[1:]) * 0.5 * (y_pts[1:] - y_pts[:-1])).sum())
    y_c = y_c / area
    z_top_vals = np.array([_z_surface_at_y(y, ground_level, Z_finish, B_top, B_base) for y in y_pts])
    z_arc_vals = np.array([_circle_arc_z_at_y(y, yc, zc, R, lower=True) for y in y_pts])
    z_mid = np.where(dz_arr > 0, (z_top_vals + np.where(np.isnan(z_arc_vals), z_top_vals, z_arc_vals)) / 2.0, ground_level)
    try:
        z_c = np.trapezoid(z_mid * dz_arr, y_pts)
    except AttributeError:
        z_c = float((((z_mid * dz_arr)[:-1] + (z_mid * dz_arr)[1:]) * 0.5 * (y_pts[1:] - y_pts[:-1])).sum())
    z_c = z_c / area if area > 0 else ground_level
    return (float(area), float(y_c), float(z_c))


def _gamma_for_slice(y_centroid: float, z_centroid: float, ground_level: float,
                     unit_weight_option: str, gamma_fill: float, gamma_clay: float) -> float:
    """Unit weight for slice based on position relative to ground."""
    if unit_weight_option == "gamma_fill":
        return gamma_fill
    if unit_weight_option == "gamma_clay":
        return gamma_clay
    if unit_weight_option == "gamma_fill_above_ground + gamma_clay_below":
        if z_centroid >= ground_level:
            return gamma_fill
        return gamma_clay
    return gamma_fill


def slope_stability_fos(yc: float, zc: float, R: float,
                        ground_level: float, Z_finish: float, B_top: float, B_base: float,
                        cu: float, gamma_fill: float, gamma_clay: float,
                        unit_weight_option: str, n_slices: int,
                        cu_scale: float = 1.0, gamma_scale: float = 1.0,
                        fill_area_scale: float = 1.0,
                        domain_mode: str = "full", side: str = "Right") -> dict:
    """
    Compute FOS for a given slip circle using short-term undrained moment method.
    Returns dict of metrics or None if invalid. Optional scale params for sanity checks.

    domain_mode: "half" or "full". For HALF, slice y-range is [y_crest, y_toe] (Right)
    or [y_toe, y_crest] (Left). For FULL, uses y_entry..y_exit from circle-ground intersection.
    """
    inter = _circle_ground_intersection(yc, zc, R, ground_level)
    if inter is None:
        return None
    y1_inter, y2_inter = inter
    if y2_inter - y1_inter < 1e-6:
        return None
    L_arc = _arc_length_lower(y1_inter, y2_inter, yc, zc, R, ground_level)
    if L_arc <= 0:
        return None

    # Slice y-range: HALF restricts to one side slope (crest→toe); FULL uses intersection span
    if domain_mode == "half":
        y_crest = B_top / 2.0 if side == "Right" else -B_top / 2.0
        y_toe = B_base / 2.0 if side == "Right" else -B_base / 2.0
        y_slice_min = min(y_crest, y_toe)
        y_slice_max = max(y_crest, y_toe)
    else:
        y_slice_min, y_slice_max = y1_inter, y2_inter

    M_drive = 0.0
    W_total = 0.0
    n_valid_slices = 0
    slice_width = (y_slice_max - y_slice_min) / n_slices
    dy = slice_width
    for i in range(n_slices):
        y_left = y_slice_min + i * slice_width
        y_right = y_slice_min + (i + 1) * slice_width
        y_mid = (y_left + y_right) / 2.0
        if domain_mode == "half":
            z_surf = z_surface_half(y_mid, ground_level, Z_finish, side, B_top, B_base)
        else:
            z_surf = z_surface(y_mid, ground_level, Z_finish, B_top, B_base)
        radicand = R**2 - (y_mid - yc)**2
        if radicand <= 0:
            continue
        z_slip = zc - math.sqrt(radicand)
        height = max(0.0, z_surf - z_slip)
        A_i = height * dy
        if A_i <= 0:
            continue
        n_valid_slices += 1
        z_centroid = (z_surf + z_slip) / 2.0
        gamma_used = _gamma_for_slice(y_mid, z_centroid, ground_level, unit_weight_option, gamma_fill, gamma_clay)
        gamma_eff = gamma_used * gamma_scale
        if fill_area_scale != 1.0 and z_surf > ground_level + 1e-9:
            A_i = A_i * fill_area_scale
        W_i = gamma_eff * A_i
        d_i = abs(y_mid - yc)
        M_drive += W_i * d_i
        W_total += W_i
    if M_drive <= 0:
        return None
    cu_eff = cu * cu_scale
    M_resist = cu_eff * L_arc * R
    FOS = M_resist / M_drive
    return {
        "fos": FOS,
        "M_drive": M_drive,
        "M_resist": M_resist,
        "W_total": W_total,
        "L_arc": L_arc,
        "R": R,
        "yc": yc,
        "zc": zc,
        "y_entry": y1_inter,
        "y_exit": y2_inter,
        "n_slices": n_slices,
        "n_valid_slices": n_valid_slices,
        "domain_mode": domain_mode,
        "side": side,
    }


def slope_stability_grid_search(df1: pd.DataFrame, x_stability: float,
                                grid_x_min: float, grid_x_max: float,
                                grid_z_min: float, grid_z_max: float,
                                grid_nx: int, grid_nz: int,
                                circle_radius_min: float, circle_radius_max: float,
                                n_slices: int, cu: float, gamma_fill: float, gamma_clay: float,
                                unit_weight_option: str, B_top: float,
                                n_radii: int = 120,
                                max_depth_below_ground: float = 40.0,
                                span_mode: str = "Base toes (strict)",
                                depth_constraint_mode: str = "Limit below bedrock (recommended)",
                                bedrock_margin: float = 0.0,
                                domain_mode: str = "half", side: str = "Right", tol: float = 2.0,
                                require_pass_through_embankment: bool = False,
                                max_cover_height: float = 2.0) -> tuple:
    """
    Grid search for critical slip circle. Returns:
    (min_FOS, best_yc, best_zc, best_R, best_L_arc, all_results_list, arc_geom_for_plot,
     best_result_dict, attempted_circles, invalid_no_intersection, invalid_span, invalid_depth,
     invalid_toe, invalid_behind_crest, invalid_embankment, valid_count, yc_list, zc_list,
     fos_min_at_center_list, R_list_best, fos_list_best)
    For HALF mode: invalid_toe/invalid_behind_crest/invalid_embankment used; invalid_span=0.
    """
    idx = (df1["x"] - x_stability).abs().idxmin()
    r = df1.loc[idx]
    ground_level = float(r["ground level"])
    bedrock_level = float(r["bedrock level"])
    Z_finish = float(r["Z_finish"])
    H_fill = float(r["H_fill"])
    B_base = float(r["B_base"])
    if H_fill <= 0:
        return (None, None, None, None, None, [], None, None, 0, 0, 0, 0, 0, 0, 0, 0, [], [], [], [], [])
    B_top_val = B_top
    yc_grid = np.linspace(grid_x_min, grid_x_max, int(grid_nx))
    zc_grid = np.linspace(grid_z_min, grid_z_max, int(grid_nz))
    R_grid = np.linspace(circle_radius_min, circle_radius_max, n_radii)
    results = []
    best_fos = float("inf")
    best_result = None
    arc_geom = None
    attempted_circles = 0
    invalid_no_intersection = 0
    invalid_span = 0
    invalid_depth = 0
    invalid_toe = 0
    invalid_behind_crest = 0
    invalid_embankment = 0
    valid_count = 0
    yc_list = []
    zc_list = []
    fos_min_at_center_list = []
    for yc in yc_grid:
        for zc in zc_grid:
            best_fos_center = float("inf")
            center_has_valid = False
            for R in R_grid:
                attempted_circles += 1
                geom_ok, y_entry, y_exit, fail_reason = _circle_geometry_valid(
                    yc, zc, R, ground_level, B_base, B_top_val, max_depth_below_ground, span_mode,
                    bedrock_level, depth_constraint_mode, bedrock_margin,
                    domain_mode=domain_mode, side=side, tol=tol,
                    require_pass_through_embankment=require_pass_through_embankment,
                    Z_finish=Z_finish, max_cover_height=max_cover_height)
                if not geom_ok:
                    if fail_reason == "no_intersection":
                        invalid_no_intersection += 1
                    elif fail_reason == "span":
                        invalid_span += 1
                    elif fail_reason == "toe":
                        invalid_toe += 1
                    elif fail_reason == "behind_crest":
                        invalid_behind_crest += 1
                    elif fail_reason == "embankment":
                        invalid_embankment += 1
                    else:
                        invalid_depth += 1
                    continue
                res = slope_stability_fos(
                    yc, zc, R, ground_level, Z_finish, B_top_val, B_base, cu, gamma_fill, gamma_clay,
                    unit_weight_option, int(n_slices),
                    domain_mode=domain_mode, side=side)
                if res is not None:
                    valid_count += 1
                    center_has_valid = True
                    fos = res["fos"]
                    best_fos_center = min(best_fos_center, fos)
                    if fos < best_fos:
                        best_fos = fos
                        best_result = res.copy()
                        y_ent, y_ext = res["y_entry"], res["y_exit"]
                        y_arc = np.linspace(y_ent, y_ext, 100)
                        rad_sq = np.maximum(0.0, R**2 - (y_arc - yc)**2)
                        z_arc = zc - np.sqrt(rad_sq)
                        arc_geom = (y_arc, z_arc, ground_level, bedrock_level, Z_finish, B_top_val, B_base, domain_mode, side)
                    results.append({
                        "yc": yc, "zc": zc, "R": R, "fos": fos,
                        "M_drive": res["M_drive"], "M_resist": res["M_resist"], "W_total": res["W_total"],
                        "L_arc": res["L_arc"], "y_entry": res["y_entry"], "y_exit": res["y_exit"],
                        "n_valid_slices": res["n_valid_slices"],
                    })
            if center_has_valid and np.isfinite(best_fos_center):
                yc_list.append(yc)
                zc_list.append(zc)
                fos_min_at_center_list.append(best_fos_center)
    R_list_best = []
    fos_list_best = []
    if best_result is not None:
        yc_best, zc_best = best_result["yc"], best_result["zc"]
        for R in R_grid:
            geom_ok, y_entry, y_exit, _ = _circle_geometry_valid(
                yc_best, zc_best, R, ground_level, B_base, B_top_val, max_depth_below_ground, span_mode,
                bedrock_level, depth_constraint_mode, bedrock_margin,
                domain_mode=domain_mode, side=side, tol=tol,
                require_pass_through_embankment=require_pass_through_embankment,
                Z_finish=Z_finish, max_cover_height=max_cover_height)
            if not geom_ok:
                continue
            res = slope_stability_fos(
                yc_best, zc_best, R, ground_level, Z_finish, B_top_val, B_base, cu, gamma_fill, gamma_clay,
                unit_weight_option, int(n_slices),
                domain_mode=domain_mode, side=side)
            if res is not None:
                R_list_best.append(R)
                fos_list_best.append(res["fos"])
    if best_result is None:
        return (None, None, None, None, None, results, None, None, attempted_circles,
                invalid_no_intersection, invalid_span, invalid_depth,
                invalid_toe, invalid_behind_crest, invalid_embankment, valid_count,
                yc_list, zc_list, fos_min_at_center_list, R_list_best, fos_list_best)
    return (best_fos, best_result["yc"], best_result["zc"], best_result["R"], best_result["L_arc"],
            results, arc_geom, best_result, attempted_circles,
            invalid_no_intersection, invalid_span, invalid_depth,
            invalid_toe, invalid_behind_crest, invalid_embankment, valid_count,
            yc_list, zc_list, fos_min_at_center_list, R_list_best, fos_list_best)


# =============================================================================
# 6) STREAMLIT UI
# =============================================================================

st.set_page_config(page_title="Motorway Design Coursework", layout="wide")
st.title("Motorway Design Coursework")

# Sidebar
if not COURSEWORK_LOCKED and st.sidebar.button("Reset to group defaults", type="secondary"):
    for k, v in GROUP_DEFAULTS.items():
        st.session_state[k] = v
    st.rerun()

if COURSEWORK_LOCKED:
    L = float(COURSEWORK_INPUTS_BY_KEY["L_m"])
    dx = float(COURSEWORK_INPUTS_BY_KEY["dx_m"])
    ground_A = float(COURSEWORK_INPUTS_BY_KEY["ground_A_mAOD"])
    ground_B = float(COURSEWORK_INPUTS_BY_KEY["ground_B_mAOD"])
    x_c = float(COURSEWORK_INPUTS_BY_KEY["x_c_m"])
    bedrock_c = float(COURSEWORK_INPUTS_BY_KEY["bedrock_c_mAOD"])
    bedrock_goes_down_towards_B = bool(COURSEWORK_INPUTS_BY_KEY["bedrock_goes_down_towards_B"])
    B_top = float(COURSEWORK_INPUTS_BY_KEY["B_top_m"])
    m = float(COURSEWORK_INPUTS_BY_KEY["m_side_slope"])

    flood_level = float(COURSEWORK_INPUTS_BY_KEY["flood_level_mAOD"])
    freeboard = float(COURSEWORK_INPUTS_BY_KEY["freeboard_m"])
    Z_peak_finish = float(COURSEWORK_INPUTS_BY_KEY["Z_peak_finish_mAOD"])
    grade = float(COURSEWORK_INPUTS_BY_KEY["grade_m_per_m"])

    gamma_fill = float(COURSEWORK_INPUTS_BY_KEY["gamma_fill"])
    gamma_clay = float(COURSEWORK_INPUTS_BY_KEY["gamma_clay"])
    gamma_w = float(COURSEWORK_INPUTS_BY_KEY["gamma_w"])
    water_table_at_ground = bool(COURSEWORK_INPUTS_BY_KEY["water_table_at_ground"])
    use_flood_wt = bool(COURSEWORK_INPUTS_BY_KEY["use_flood_wt"])
    z_wt_m = float(COURSEWORK_INPUTS_BY_KEY["z_wt_m"])
    consol_method = "mv" if str(COURSEWORK_INPUTS_BY_KEY["consol_method_display"]).startswith("mv") else "Cc"
    m_v = float(COURSEWORK_INPUTS_BY_KEY["m_v"])
    Cc = float(COURSEWORK_INPUTS_BY_KEY["Cc"])
    e0 = float(COURSEWORK_INPUTS_BY_KEY["e0"])
    cu = float(COURSEWORK_INPUTS_BY_KEY["cu_kpa"])
    Is = float(COURSEWORK_INPUTS_BY_KEY["Is"])
    Eu_over_cu = float(COURSEWORK_INPUTS_BY_KEY["Eu_over_cu"])
    x_worked = float(COURSEWORK_INPUTS_BY_KEY["x_worked_m"])
    consolidation_depth_method = str(COURSEWORK_INPUTS_BY_KEY["consolidation_depth_method"])
    N_layers = int(COURSEWORK_INPUTS_BY_KEY["N_layers"])
    consol_stress_point = str(COURSEWORK_INPUTS_BY_KEY["consol_stress_point"])
    delta_sigma_mode = str(COURSEWORK_INPUTS_BY_KEY["delta_sigma_mode"])
    run_preliminary_quick_stage = bool(COURSEWORK_INPUTS_BY_KEY["run_preliminary_quick_stage"])
    run_detailed_stage2_profile = bool(COURSEWORK_INPUTS_BY_KEY["run_detailed_stage2_profile"])

    immediate_settlement_method = str(COURSEWORK_INPUTS_BY_KEY["immediate_settlement_method"])
    q_immediate_method = str(COURSEWORK_INPUTS_BY_KEY["q_immediate_method"])
    influence_factor_input_mode = str(COURSEWORK_INPUTS_BY_KEY["influence_factor_input_mode"])
    I_s_input = float(COURSEWORK_INPUTS_BY_KEY["I_s_input"])
    mu1_input = float(COURSEWORK_INPUTS_BY_KEY["mu1_input"])
    staged_construction_lifts = bool(COURSEWORK_INPUTS_BY_KEY["staged_construction_lifts"])
    lift_height_m = float(COURSEWORK_INPUTS_BY_KEY["lift_height_m"])

    Cv_m2_per_s = float(COURSEWORK_INPUTS_BY_KEY["Cv_m2_per_s"])
    vertical_drainage = str(COURSEWORK_INPUTS_BY_KEY["vertical_drainage"])
    Uv_targets_str = str(COURSEWORK_INPUTS_BY_KEY["Uv_targets_str"])
    x_section = float(COURSEWORK_INPUTS_BY_KEY["x_section_m"])

    run_slope_stability = bool(COURSEWORK_INPUTS_BY_KEY["run_slope_stability"])
    stability_analysis_domain = str(COURSEWORK_INPUTS_BY_KEY["stability_analysis_domain"])
    is_half_domain = "Half" in stability_analysis_domain
    stability_side = str(COURSEWORK_INPUTS_BY_KEY["stability_side"])
    intersection_tolerance = float(COURSEWORK_INPUTS_BY_KEY["intersection_tolerance_m"])
    mirror_for_display = bool(COURSEWORK_INPUTS_BY_KEY["mirror_for_display"])
    require_pass_through_embankment = bool(COURSEWORK_INPUTS_BY_KEY["require_pass_through_embankment"])
    max_cover_height = float(COURSEWORK_INPUTS_BY_KEY["max_cover_height_m"])
    x_stability = float(COURSEWORK_INPUTS_BY_KEY["x_stability_m"])
    n_slices = int(COURSEWORK_INPUTS_BY_KEY["n_slices"])
    grid_x_min = float(COURSEWORK_INPUTS_BY_KEY["grid_x_min_m"])
    grid_x_max = float(COURSEWORK_INPUTS_BY_KEY["grid_x_max_m"])
    grid_z_min = float(COURSEWORK_INPUTS_BY_KEY["grid_z_min_mAOD"])
    grid_z_max = float(COURSEWORK_INPUTS_BY_KEY["grid_z_max_mAOD"])
    grid_nx = int(COURSEWORK_INPUTS_BY_KEY["grid_nx"])
    grid_nz = int(COURSEWORK_INPUTS_BY_KEY["grid_nz"])
    circle_radius_min = float(COURSEWORK_INPUTS_BY_KEY["circle_radius_min_m"])
    circle_radius_max = float(COURSEWORK_INPUTS_BY_KEY["circle_radius_max_m"])
    radius_steps = int(COURSEWORK_INPUTS_BY_KEY["radius_steps"])
    span_requirement = str(COURSEWORK_INPUTS_BY_KEY["span_requirement"])
    min_FOS_required = float(COURSEWORK_INPUTS_BY_KEY["min_FOS_required"])
    max_depth_below_ground = float(COURSEWORK_INPUTS_BY_KEY["max_depth_below_ground_m"])
    depth_constraint_mode = str(COURSEWORK_INPUTS_BY_KEY["depth_constraint_mode"])
    bedrock_margin = float(COURSEWORK_INPUTS_BY_KEY["bedrock_margin_m"])
    unit_weight_for_W = str(COURSEWORK_INPUTS_BY_KEY["unit_weight_for_W"])

    render_project_inputs_locked(COURSEWORK_INPUTS)

    x_ratio = float(x_section)
    g_ratio = lin(x_ratio, 0.0, ground_A, L, ground_B)
    b_ratio = bedrock_level(x_ratio)
    H0_ratio = max(0.0, g_ratio - b_ratio)
    zf_ratio = finished_profile([x_ratio])[0]
    H_fill_ratio = max(0.0, zf_ratio - g_ratio)
    B_base_ratio = B_base_from_H(H_fill_ratio)
    H_over_B = (H0_ratio / B_base_ratio) if B_base_ratio > 0.0 else 0.0
    st.sidebar.subheader("Chart ratios (read-only)")
    st.sidebar.text(f"H_over_B = H0 / B_base = {H_over_B:.3f}")
    st.sidebar.text("D_over_B = 0 / B_base = 0")
    st.sidebar.text("L_over_B assumed = ∞ (plane strain)")
    st.sidebar.text("alpha = 0")
else:
    st.error("Editable sidebar mode is disabled in this coursework build.")
    st.stop()

run_btn = st.sidebar.button("Run calculations", type="primary")

_uv_parse_ok = True
try:
    _uv_raw = [float(x.strip()) for x in Uv_targets_str.split(",") if x.strip()]
    Uv_targets = [u for u in _uv_raw if 0.0 < u < 1.0]
    if not Uv_targets:
        Uv_targets = [0.20, 0.50, 0.90]
        _uv_parse_ok = False
except ValueError:
    Uv_targets = [0.20, 0.50, 0.90]
    _uv_parse_ok = False

if not _uv_parse_ok:
    st.warning("Invalid U targets. Using defaults: 0.20, 0.50, 0.90")

Zmin_finish = flood_level + freeboard

df1 = key_df = report_df = summary_df = None
week2_chainage_df = None
out_path = None
layers_df_for_x_section = None
immediate_stage_df_x_section = None
layer_table_x0 = None
settlement_summary = []
neg_dsigma_chainages = []
monotonic_warnings = []
quick_stage_df = None
no_allow_violations_quick = []
flood_violations_quick = []
grade_violations = []
grade_slopes = []
detailed_stage2_df = None
flood_violations_stage2 = []
grade_violations_stage2 = []
grade_slopes_stage2 = []
slope_stab_result = None
csv_paths = {}
x0_summary = None

if run_btn:
    with st.spinner("Calculating..."):
        (
            df1,
            key_df,
            report_df,
            summary_df,
            layers_df_for_x_section,
            settlement_summary,
            neg_dsigma_chainages,
            layer_table_x0,
            immediate_stage_df_x_section,
            monotonic_warnings,
            quick_stage_df,
            no_allow_violations_quick,
            flood_violations_quick,
            grade_violations,
            grade_slopes,
            detailed_stage2_df,
            flood_violations_stage2,
            grade_violations_stage2,
            grade_slopes_stage2,
        ) = week1_calculate()
        out_path = export_week1_excel(
            df1,
            key_df,
            report_df,
            summary_df,
            layers_df_for_x_section,
            immediate_stage_df_x_section,
        )
        week2_chainage_df = week2_run(df1)
        out_path = export_add_week2_sheets(out_path, week2_chainage_df)
        csv_paths = export_additional_csvs(
            df1,
            week2_chainage_df,
            layer_table_x0,
            quick_stage_df,
            detailed_stage2_df,
            run_detailed_stage2_profile,
        )
        if run_slope_stability and df1 is not None:
            slope_stab_result = slope_stability_grid_search(
                df1, x_stability, grid_x_min, grid_x_max, grid_z_min, grid_z_max,
                grid_nx, grid_nz, circle_radius_min, circle_radius_max, n_slices,
                cu, gamma_fill, gamma_clay, unit_weight_for_W, B_top, n_radii=int(radius_steps),
                max_depth_below_ground=max_depth_below_ground, span_mode=span_requirement,
                depth_constraint_mode=depth_constraint_mode, bedrock_margin=bedrock_margin,
                domain_mode="half" if is_half_domain else "full", side=stability_side, tol=intersection_tolerance,
                require_pass_through_embankment=require_pass_through_embankment if is_half_domain else False,
                max_cover_height=max_cover_height if is_half_domain else 2.0)
        x0_summary = summarize_x0_settlement_and_consolidation(layer_table_x0, week2_chainage_df)
    csv_note = ""
    if csv_paths:
        csv_note = " | CSV: " + ", ".join([os.path.basename(p) for p in csv_paths.values()])
    st.success("Done. Excel saved to " + str(out_path) + csv_note)

if df1 is not None:
    # -------------------------------------------------------------------------
    # 1) Geometry & Profiles
    # -------------------------------------------------------------------------
    st.header("Geometry & Profiles")
    st.subheader("Longitudinal Profile")
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    x_vals = df1["x"].values
    ax1.plot(x_vals, df1["ground level"].values, "b-", label="ground", lw=2)
    ax1.plot(x_vals, df1["bedrock level"].values, "sienna", ls="--", label="bedrock", lw=1.5)
    ax1.plot(x_vals, df1["Z_finish"].values, "green", label="Z_finish", lw=2)
    ax1.plot(x_vals, df1["Z_rev"].values, "red", label="Z_construct", lw=2)
    ax1.set_xlabel("Chainage x (m)")
    ax1.set_ylabel("Level (mAOD)")
    y_lo = min(df1["bedrock level"].min(), df1["ground level"].min()) - 1
    y_hi = max(df1["Z_rev"].max(), df1["Z_finish"].max()) + 2
    ax1.axvline(x_c, color="gray", ls=":", alpha=0.7)
    ax1.annotate(f"L = {L:.0f} m", xy=(L * 0.7, y_hi - 0.5), fontsize=9)
    ax1.annotate(f"x_c = {x_c:.0f} m (crown)", xy=(x_c, y_lo + 0.5), fontsize=9, ha="center")
    ax1.annotate(f"grade g = 1/200 = {grade:.4f}", xy=(L * 0.5, y_lo + 1.0), fontsize=9, ha="center")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Ground, bedrock, Z_finish, Z_construct vs x")
    plt.tight_layout()
    st.pyplot(fig1)
    plt.close()

    st.subheader("3D Motorway View (static)")
    x_vol = df1["x"].values
    A_vol = df1["A_trap"].values
    try:
        V_fill = np.trapezoid(A_vol, x_vol)
    except AttributeError:
        # Fallback if trapezoid isn't available for any reason
        V_fill = float(((A_vol[:-1] + A_vol[1:]) * 0.5 * (x_vol[1:] - x_vol[:-1])).sum())
    st.metric("Estimated fill volume (m³)", f"{V_fill:,.0f}")
    st.caption("Computed from trapezoidal integration of embankment area along chainage.")
    st.latex(r"V_{fill}=\int_0^L A(x)\,dx \approx \sum \frac{A_i+A_{i+1}}{2}\Delta x")
    st.latex(r"A(x)=\frac{B_{top}+B_{base}(x)}{2}H_{fill}(x)")
    fig_3d = plot_3d_motorway(df1, B_top)
    st.pyplot(fig_3d)
    plt.close()

    st.subheader(f"Cross Section at x = {x_section} m")
    idx_s = (df1["x"] - x_section).abs().idxmin()
    r = df1.loc[idx_s]
    ground_lev = float(r["ground level"])
    bedrock_lev = float(r["bedrock level"])
    H_fill_sec = float(r["H_fill"])
    H0_sec = float(r["H0"])
    B_base_sec = float(r["B_base"])
    rho_total_sec = float(r["rho"])
    rho_total_center_sec = float(r["rho_total_center_m"]) if "rho_total_center_m" in r.index else float(rho_total_sec)
    rho_total_edge_sec = float(r["rho_total_edge_m"]) if "rho_total_edge_m" in r.index else float(rho_total_sec)
    half_w = max(100, B_base_sec / 2 + 25)
    fig2, ax2 = plt.subplots(figsize=(12, 7), dpi=200)
    ax2.set_xlabel("Horizontal (m)")
    ax2.set_ylabel("Level (mAOD)")
    ax2.set_title(f"Cross section at chainage x = {float(r['x']):.0f} m")
    ax2.axhline(ground_lev, color="brown", ls="-", lw=2, label="ground", zorder=7)
    ax2.axhline(bedrock_lev, color="sienna", ls="--", lw=1.5, label="bedrock", zorder=7)
    ax2.axhspan(bedrock_lev, ground_lev, color="sienna", alpha=0.06, zorder=0, label=None)
    ax2.set_ylim(bedrock_lev - 2, ground_lev + H_fill_sec + 4)
    ax2.set_xlim(-half_w, half_w)
    xmin_plot, xmax_plot = ax2.get_xlim()
    N_sec = int(len(layers_df_for_x_section)) if layers_df_for_x_section is not None and len(layers_df_for_x_section) > 0 else 60
    k_show = 5
    dz_sec = (float(H0_sec) / float(N_sec)) if H0_sec > 0 and N_sec > 0 else 0.0
    first_layer_line = True
    if dz_sec > 0:
        for j in range(k_show, N_sec, k_show):
            y_layer = float(bedrock_lev) + j * dz_sec
            if first_layer_line:
                ax2.hlines(
                    y_layer,
                    xmin_plot,
                    xmax_plot,
                    colors="0.35",
                    linewidth=1.6,
                    alpha=0.85,
                    zorder=3,
                    label=f"clay layers (N={N_sec}, every {k_show}th shown)",
                )
                first_layer_line = False
            else:
                ax2.hlines(y_layer, xmin_plot, xmax_plot, colors="0.35", linewidth=1.6, alpha=0.85, zorder=3)
    if H_fill_sec > 0:
        trap_x = [-B_base_sec/2, -B_top/2, B_top/2, B_base_sec/2, -B_base_sec/2]
        trap_z = [ground_lev, ground_lev + H_fill_sec, ground_lev + H_fill_sec, ground_lev, ground_lev]
        ax2.fill(trap_x, trap_z, color="green", alpha=0.45, label="embankment", zorder=6)
        y_ground = float(ground_lev)
        lift_h = 1.0
        half_top = 0.5 * float(B_top)
        half_base = half_top + float(m) * float(H_fill_sec)
        for h in np.arange(lift_h, H_fill_sec, lift_h):
            y = y_ground + h
            half_width_y = half_base - float(m) * h
            if half_width_y <= 0:
                continue
            x_left = -half_width_y
            x_right = half_width_y
            ax2.hlines(y, x_left, x_right, linewidth=1.2, alpha=0.9, zorder=9)
        ax2.plot(trap_x, trap_z, linewidth=2.4, zorder=10, color="black")

        n_lifts = int(math.ceil(H_fill_sec / lift_h)) if H_fill_sec > 0 else 0
        y_top = y_ground + H_fill_sec
        right_toe_x = 0.5 * float(B_base_sec)
        x_anno = right_toe_x + 18.0
        tick = 3.0
        ax2.text(
            x_anno, y_top,
            f"Construction lifts ({lift_h:.0f} m)",
            va="bottom", ha="left",
            fontsize=10,
            zorder=20,
        )
        ax2.plot([x_anno, x_anno + tick], [y_ground, y_ground], linewidth=1.6, zorder=20, color="black")
        ax2.plot([x_anno, x_anno], [y_ground, y_top], linewidth=1.6, zorder=20, color="black")
        ax2.plot([x_anno, x_anno + tick], [y_top, y_top], linewidth=1.6, zorder=20, color="black")
        y_mid = 0.5 * (y_ground + y_top)
        ax2.text(
            x_anno + tick + 2.0, y_mid,
            f"H_fill={H_fill_sec:.1f} m\n~{n_lifts} lifts",
            va="center", ha="left",
            fontsize=9,
            zorder=20,
        )
        xmin, xmax = ax2.get_xlim()
        if x_anno + tick + 15 > xmax:
            ax2.set_xlim(xmin, x_anno + tick + 15)
    ax2.annotate(f"B_top = {B_top:.1f} m", xy=(0, ground_lev + H_fill_sec + 0.5), fontsize=9, ha="center")
    ax2.annotate(f"B_base = {B_base_sec:.1f} m", xy=(0, ground_lev - 2.0), fontsize=9, ha="center")
    ax2.annotate(f"H_fill = {H_fill_sec:.1f} m", xy=(-B_base_sec/2 - 8, ground_lev + H_fill_sec/2), fontsize=9, ha="right", va="center")
    ax2.annotate(f"H0 = {H0_sec:.1f} m", xy=(-half_w + 12, bedrock_lev + H0_sec/2), fontsize=9, ha="left", va="center")
    ax2.annotate(f"m = 2H:1V", xy=(-B_base_sec/2 - 10, ground_lev + H_fill_sec*0.3), fontsize=9, ha="right")
    z_finish_sec = float(r["Z_finish"])
    # Settlement annotations at centre and edge for the selected chainage.
    ax2.annotate(
        f"ρ_total centre = {rho_total_center_sec:.3f} m",
        xy=(0.0, z_finish_sec - rho_total_center_sec),
        xytext=(0.0, z_finish_sec + 1.2),
        ha="center",
        va="bottom",
        fontsize=9,
        color="navy",
        arrowprops={"arrowstyle": "<->", "color": "navy", "lw": 1.6},
        zorder=25,
    )
    ax2.annotate(
        f"ρ_total edge = {rho_total_edge_sec:.3f} m",
        xy=(0.5 * B_base_sec, z_finish_sec - rho_total_edge_sec),
        xytext=(0.5 * B_base_sec, z_finish_sec + 2.0),
        ha="center",
        va="bottom",
        fontsize=9,
        color="darkred",
        arrowprops={"arrowstyle": "<->", "color": "darkred", "lw": 1.6},
        zorder=25,
    )
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    st.pyplot(fig2)
    plt.close()

    with st.expander("Formulas used", expanded=False):
        st.latex(r"H_0 = \text{ground} - \text{bedrock}")
        st.latex(r"Z_{\text{finish}}(x) = Z_{\text{peak}} - g|x - x_c|,\ \text{then shift if min} < Z_{\min,\text{finish}}")
        st.latex(r"H_{\text{fill}} = \max(0,\ Z_{\text{finish}} - \text{ground})")
    st.caption("**Values carried forward →** H₀, H_fill, Z_finish passed to Loading/Settlement")

    # -------------------------------------------------------------------------
    # 2) Loading & Stress Increment
    # -------------------------------------------------------------------------
    st.header("Loading & Stress Increment")
    st.subheader("Design vs Construction (same chainage)")
    H_fill_design = float(r["Z_finish"]) - ground_lev
    H_fill_construct = (float(r["Z_finish"]) + rho_total_sec) - ground_lev
    if run_detailed_stage2_profile and detailed_stage2_df is not None and len(detailed_stage2_df) > 0:
        i_d2 = (detailed_stage2_df["x"].astype(float) - float(r["x"])).abs().idxmin()
        r_d2 = detailed_stage2_df.loc[i_d2]
        H_fill_construct = float(r_d2["Z_construct_stage2"]) - ground_lev
    elif run_preliminary_quick_stage and quick_stage_df is not None and len(quick_stage_df) > 0:
        i_q = (quick_stage_df["x"].astype(float) - float(r["x"])).abs().idxmin()
        r_q = quick_stage_df.loc[i_q]
        H_fill_construct = float(r_q["Z_construct_stage1"]) - ground_lev
    fig3, ax3 = plt.subplots(figsize=(8, 5))
    ax3.set_xlabel("Horizontal (m)")
    ax3.set_ylabel("Level (mAOD)")
    ax3.set_title(f"Design vs Construction surface at x = {float(r['x']):.0f} m")
    ax3.axhline(ground_lev, color="brown", ls="-", lw=2, label="ground")
    ax3.axhline(bedrock_lev, color="sienna", ls="--", lw=1.5, alpha=0.7)
    ax3.fill_between([-half_w, half_w], bedrock_lev, ground_lev, color="sienna", alpha=0.15)
    if H_fill_design > 0:
        B_base_design = B_top + 2 * m * H_fill_design
        trap_d_x = [-B_base_design/2, -B_top/2, B_top/2, B_base_design/2, -B_base_design/2]
        trap_d_z = [ground_lev, ground_lev + H_fill_design, ground_lev + H_fill_design, ground_lev, ground_lev]
        ax3.fill(trap_d_x, trap_d_z, color="green", alpha=0.2, label="Design surface (target)")
        ax3.plot(trap_d_x, trap_d_z, color="green", lw=2)
    if H_fill_construct > 0:
        B_base_const = B_top + 2 * m * H_fill_construct
        trap_c_x = [-B_base_const/2, -B_top/2, B_top/2, B_base_const/2, -B_base_const/2]
        trap_c_z = [ground_lev, ground_lev + H_fill_construct, ground_lev + H_fill_construct, ground_lev, ground_lev]
        ax3.fill(trap_c_x, trap_c_z, color="red", alpha=0.2, label="Construction surface")
        ax3.plot(trap_c_x, trap_c_z, color="darkred", lw=2)
    ax3.set_ylim(bedrock_lev - 2, ground_lev + max(H_fill_design, H_fill_construct) + 4)
    ax3.set_xlim(-half_w, half_w)
    ax3.legend(loc="upper right")
    ax3.grid(True, alpha=0.3)
    ax3.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    st.pyplot(fig3)
    plt.close()

    with st.expander("Formulas used", expanded=False):
        st.latex(r"B_{\text{base}} = B_{\text{top}} + 2\,m\,H_{\text{fill}}")
        st.latex(r"A_{\text{trap}} = \frac{B_{\text{top}} + B_{\text{base}}}{2} \cdot H_{\text{fill}}")
        st.latex(r"W_{\text{line}} = \gamma_{\text{fill}} \cdot A_{\text{trap}}")
        st.latex(r"q_{\text{equiv}} = \frac{W_{\text{line}}}{B_{\text{base}}}")
        st.markdown(r"**Craig strip:** $\Delta\sigma = \frac{q}{\pi}\{\alpha + \sin\alpha \cos(\alpha+2\beta)\}$ with α, β from strip geometry (x_left, x_right, z)")
    st.caption("**Values carried forward →** q_equiv and B_base passed to Δσ and settlements")

    if neg_dsigma_chainages:
        st.warning(f"Negative Δσ at chainages: {[(x, f'{v:.3f} kPa') for x, v in neg_dsigma_chainages]}. Proceeding without crash.")

    with_clay = df1[df1["H0"] > 0]
    if len(with_clay) > 0:
        edge_diff_total = with_clay["delta_rho_total_edge_minus_center_m"]
        if np.allclose(edge_diff_total.values, 0.0, atol=1e-12):
            st.warning("Edge and centre total settlements are identical at all clay chainages. Check Craig-strip x offset wiring if this was not intended.")

    # -------------------------------------------------------------------------
    # 3) Settlement Results
    # -------------------------------------------------------------------------
    st.header("Settlement Results")
    if monotonic_warnings:
        st.warning("Settlement should increase with higher fill; monotonicity failed for some cases (see Detailed tables).")
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        st.metric("Max ρ_i (m)", f"{df1['rho_i'].max():.4f}")
        st.metric("Max ρ_c (m)", f"{df1['rho_c'].max():.4f}")
        st.metric("Max ρ_total (m)", f"{df1['rho'].max():.4f}")
        st.metric("Max Z_construct (mAOD)", f"{df1['Z_rev'].max():.3f}")
    with c_s2:
        st.caption("ρ_i is currently assumed the same at centre and edge; only ρ_c varies by Craig-strip x offset.")

    st.subheader("3D post-settlement road surface (Stage-2 detailed)")
    with st.spinner("Computing Stage-2 detailed post-settlement surface on toe-to-toe η grid..."):
        n_slices_settlement = 60
        log_base_settlement = 10.0
        consol_method_value = str(consol_method).strip().lower()

        x_full = df1["x"].astype(float).to_numpy()
        if len(x_full) > int(N_CHAINAGE_SURF):
            idx_sel = np.linspace(0, len(x_full) - 1, int(N_CHAINAGE_SURF)).round().astype(int)
        else:
            idx_sel = np.arange(len(x_full), dtype=int)
        x_vals = [float(x_full[k]) for k in idx_sel]
        df_surface = df1.iloc[idx_sel].reset_index(drop=True)

        if (
            run_detailed_stage2_profile
            and detailed_stage2_df is not None
            and len(detailed_stage2_df) == len(df1)
            and "Z_construct_stage2" in detailed_stage2_df.columns
        ):
            z_construct_surface = detailed_stage2_df.iloc[idx_sel]["Z_construct_stage2"].astype(float).to_numpy()
        else:
            z_construct_surface = df_surface["Z_rev"].astype(float).to_numpy()

        eta_vals = np.linspace(-1.0, 1.0, int(N_LATERAL_SURF))
        X_mesh = np.zeros((len(x_vals), len(eta_vals)), dtype=float)
        Y_mesh = np.zeros((len(x_vals), len(eta_vals)), dtype=float)
        rho_total_mesh = np.zeros((len(x_vals), len(eta_vals)), dtype=float)
        Z_post_mesh = np.zeros((len(x_vals), len(eta_vals)), dtype=float)
        for i, x in enumerate(x_vals):
            r_surf = df_surface.iloc[i]
            H0_i = float(r_surf["H0"])
            B_base_i = float(r_surf["B_base"])
            q_i = float(r_surf["q_equiv"])
            rho_i_i = float(r_surf["rho_i"])
            if use_flood_wt:
                g_i = float(r_surf["ground level"])
                z_wt_i = max(0.0, g_i - FLOOD_10YR_AOD_M)
            else:
                z_wt_i = 0.0 if water_table_at_ground else float(z_wt_m)
            stress_inputs = StressInputs(
                gamma_unsat_kN_m3=float(gamma_clay),
                gamma_sat_kN_m3=float(gamma_clay),
                gamma_w_kN_m3=float(gamma_w),
                z_wt_m=float(z_wt_i),
            )
            halfB_i = 0.5 * float(B_base_i)

            for j, eta in enumerate(eta_vals):
                y = float(eta) * halfB_i
                rho_c_y = compute_rho_c_for_offset(
                    H0_m=float(H0_i),
                    stress_inputs=stress_inputs,
                    q_kpa=float(q_i),
                    B_base_m=float(B_base_i),
                    offset_m=float(y),
                    consol_method_value=consol_method_value,
                    m_v=float(m_v),
                    Cc=float(Cc),
                    e0=float(e0),
                    n_slices_settlement=int(n_slices_settlement),
                    log_base_settlement=float(log_base_settlement),
                )
                rho_total_ij = float(rho_i_i) + float(rho_c_y)
                X_mesh[i, j] = float(x)
                Y_mesh[i, j] = float(y)
                rho_total_mesh[i, j] = rho_total_ij
                Z_post_mesh[i, j] = float(z_construct_surface[i]) - rho_total_ij

    Z_plot = np.ma.masked_invalid(Z_post_mesh)
    fig_sett_3d = plt.figure(figsize=(14, 4), dpi=200)
    ax_sett_3d = fig_sett_3d.add_subplot(111, projection="3d")
    ax_sett_3d.plot_surface(X_mesh, Y_mesh, Z_plot, cmap="viridis", linewidth=0, rstride=1, cstride=1, antialiased=True)
    ax_sett_3d.set_box_aspect((6, 3, 5))
    try:
        ax_sett_3d.set_proj_type("ortho")
    except Exception:
        pass
    ax_sett_3d.set_xlabel("Chainage x (m)")
    ax_sett_3d.set_ylabel("Lateral offset y (m)")
    ax_sett_3d.set_zlabel("Post-settlement level Z_post (mAOD)")
    ax_sett_3d.set_xticks([0.0, 250.0, 500.0, 750.0, 1000.0])
    halfB_tick = 0.5 * float(df_surface["B_base"].astype(float).max())
    ax_sett_3d.set_yticks([-float(halfB_tick), 0.0, float(halfB_tick)])
    ax_sett_3d.set_title("3D post-settlement road surface (Stage-2 detailed)")
    ax_sett_3d.view_init(elev=25, azim=-65)
    plt.tight_layout()
    st.pyplot(fig_sett_3d, use_container_width=True)
    plt.close(fig_sett_3d)
    st.caption("Assumption: immediate settlement ρ_i is laterally constant; across-width variation comes from Craig-strip consolidation Δσ(y).")

    i_sec = int(np.argmin(np.abs(np.array(x_vals, dtype=float) - float(x_section))))
    j_center = int(np.argmin(np.abs(eta_vals - 0.0)))
    j_edge_p = int(np.argmin(np.abs(eta_vals - 1.0)))
    j_edge_m = int(np.argmin(np.abs(eta_vals + 1.0)))
    sanity_df = pd.DataFrame([
        {"point": "centre", "eta": float(eta_vals[j_center]), "y_m": float(Y_mesh[i_sec, j_center]), "rho_total_m": float(rho_total_mesh[i_sec, j_center]), "Z_post_mAOD": float(Z_post_mesh[i_sec, j_center])},
        {"point": "edge +", "eta": float(eta_vals[j_edge_p]), "y_m": float(Y_mesh[i_sec, j_edge_p]), "rho_total_m": float(rho_total_mesh[i_sec, j_edge_p]), "Z_post_mAOD": float(Z_post_mesh[i_sec, j_edge_p])},
        {"point": "edge -", "eta": float(eta_vals[j_edge_m]), "y_m": float(Y_mesh[i_sec, j_edge_m]), "rho_total_m": float(rho_total_mesh[i_sec, j_edge_m]), "Z_post_mAOD": float(Z_post_mesh[i_sec, j_edge_m])},
    ])
    st.markdown("**x_section sanity check (centre vs edges: ρ_total and Z_post)**")
    st.dataframe(sanity_df, use_container_width=True, hide_index=True)
    st.caption("Expected: ρ_total centre > edges and Z_post centre < edges (centre sags lower).")

    finite_mask = np.isfinite(rho_total_mesh)
    if finite_mask.any():
        surf_export_df = pd.DataFrame({
            "x_m": X_mesh[finite_mask],
            "y_m": Y_mesh[finite_mask],
            "rho_total_m": rho_total_mesh[finite_mask],
        })
        ensure_dir(OUTPUT_FOLDER)
        surf_export_path = os.path.join(OUTPUT_FOLDER, "settlement_surface_xy.csv")
        surf_export_df.to_csv(surf_export_path, index=False)
    if run_preliminary_quick_stage:
        st.subheader("Preliminary quick settlement stage (lecture Stage 1)")
        if quick_stage_df is not None and len(quick_stage_df) > 0:
            st.dataframe(
                quick_stage_df[
                    ["x", "Z_finish", "rho_total_quick", "Z_req_construct", "Z_construct_stage1", "Z_post_stage1"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        if no_allow_violations_quick:
            st.info(
                "No allowance case: if built to Z_finish, post-settlement level drops below 55 m AOD at these chainages: "
                + ", ".join([f"{x:.1f} m" for x in no_allow_violations_quick])
            )
        else:
            st.success("No allowance case: post-settlement level stays above 55 m AOD (unexpected but OK).")
        if flood_violations_quick:
            st.error(
                "Stage-1 revised construction profile failed flood+1 check at chainages: "
                + ", ".join([f"{x:.1f} m" for x in flood_violations_quick])
            )
        else:
            st.success("Stage-1 revised profile check passed: post-settlement level stays at/above 55 m AOD.")
        if grade_violations:
            st.warning(
                "Stage-1 grade check deviates from 1:200 at chainages starting: "
                + ", ".join([f"{x:.1f} m" for x in grade_violations[:10]])
            )
        else:
            st.success("Stage-1 grade check passed: 1 in 200 crown enforced by construction profile.")
    if run_detailed_stage2_profile:
        st.subheader("Stage-2 Detailed Profile")
        if detailed_stage2_df is not None and len(detailed_stage2_df) > 0:
            st.dataframe(
                detailed_stage2_df[
                    [
                        "x", "Z_finish", "rho_total_stage2_worst", "rho_total_center", "rho_total_edge",
                        "Z_req_construct_stage2", "Z_construct_stage2",
                        "Z_post_stage2_center", "Z_post_stage2_edge",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        if flood_violations_stage2:
            st.error(
                "Stage-2 detailed profile failed flood+1 check at chainages: "
                + ", ".join([f"{x:.1f} m" for x in flood_violations_stage2])
            )
        else:
            st.success("Stage-2 detailed profile check passed: post-settlement level stays at/above 55 m AOD.")
        if grade_violations_stage2:
            st.warning(
                "Stage-2 grade check deviates from 1:200 at chainages starting: "
                + ", ".join([f"{x:.1f} m" for x in grade_violations_stage2[:10]])
            )
        else:
            st.success("Stage-2 grade check passed: 1 in 200 crown enforced by construction profile.")
    with st.expander("Settlement integration table at x_section (slices)", expanded=False):
        if layers_df_for_x_section is not None:
            st.dataframe(layers_df_for_x_section, use_container_width=True, hide_index=True)
        else:
            st.info("No settlement slices available (H0<=0 or settlement not computed at this chainage).")
    if staged_construction_lifts:
        st.subheader("Immediate settlement staging at x_section")
        if immediate_stage_df_x_section is not None and len(immediate_stage_df_x_section) > 0:
            st.dataframe(immediate_stage_df_x_section, use_container_width=True, hide_index=True)
        else:
            st.info("No staged immediate-settlement rows at x_section (H_fill<=0 or no computed lifts).")
        st.caption("Staged construction: incremental ρ_i computed per lift; final ρ_i equals last stage.")

    st.subheader("x_section settlement vs time (using U targets)")
    if week2_chainage_df is not None and len(week2_chainage_df) > 0 and "U20_t_years" in week2_chainage_df.columns:
        i_sec = (df1["x"].astype(float) - float(x_section)).abs().idxmin()
        r_sec = df1.loc[i_sec]
        rho_i_sec = float(r_sec["rho_i"])
        rho_c_sec = float(r_sec["rho_c"])
        j_sec = (week2_chainage_df["x"].astype(float) - float(x_section)).abs().idxmin()
        r_cons_sec = week2_chainage_df.loc[j_sec]
        t20 = float(r_cons_sec["U20_t_years"])
        t50 = float(r_cons_sec["U50_t_years"])
        t90 = float(r_cons_sec["U90_t_years"])
        x_section_time_df = pd.DataFrame(
            [
                {
                    "U": 0.20,
                    "t_years": t20,
                    "S_consol_m": 0.20 * rho_c_sec,
                    "S_consol_mm": 0.20 * rho_c_sec * 1000.0,
                    "rho_total_m": rho_i_sec + (0.20 * rho_c_sec),
                    "rho_total_mm": (rho_i_sec + (0.20 * rho_c_sec)) * 1000.0,
                },
                {
                    "U": 0.50,
                    "t_years": t50,
                    "S_consol_m": 0.50 * rho_c_sec,
                    "S_consol_mm": 0.50 * rho_c_sec * 1000.0,
                    "rho_total_m": rho_i_sec + (0.50 * rho_c_sec),
                    "rho_total_mm": (rho_i_sec + (0.50 * rho_c_sec)) * 1000.0,
                },
                {
                    "U": 0.90,
                    "t_years": t90,
                    "S_consol_m": 0.90 * rho_c_sec,
                    "S_consol_mm": 0.90 * rho_c_sec * 1000.0,
                    "rho_total_m": rho_i_sec + (0.90 * rho_c_sec),
                    "rho_total_mm": (rho_i_sec + (0.90 * rho_c_sec)) * 1000.0,
                },
            ]
        )
        st.dataframe(x_section_time_df, use_container_width=True, hide_index=True)
        st.caption(
            f"Nearest chainage used: x={float(r_sec['x']):.1f} m. "
            f"Uses selected-method outputs from Week 1: rho_i={rho_i_sec:.4f} m, rho_c={rho_c_sec:.4f} m."
        )
    else:
        st.info("Run calculations to populate x_section settlement vs time.")

    show_crosscheck = st.checkbox("Show method cross-check", value=False)
    if show_crosscheck:
        st.subheader("Method cross-check (x_section)")
        if H0_sec > 0.0 and float(r["q_equiv"]) > 0.0:
            q_sec = float(r["q_equiv"])
            x_sec_val = float(r["x"])
            n_slices_cross = int(len(layers_df_for_x_section)) if layers_df_for_x_section is not None and len(layers_df_for_x_section) > 0 else 60
            dz_cross = H0_sec / float(n_slices_cross)

            if use_flood_wt:
                z_wt_cross = max(0.0, ground_lev - FLOOD_10YR_AOD_M)
            else:
                z_wt_cross = 0.0 if water_table_at_ground else float(z_wt_m)
            stress_cross = StressInputs(
                gamma_unsat_kN_m3=float(gamma_clay),
                gamma_sat_kN_m3=float(gamma_clay),
                gamma_w_kN_m3=float(gamma_w),
                z_wt_m=float(z_wt_cross),
            )
            if consol_stress_point == "Centre (x = 0)":
                xoff_cross = 0.0
            else:
                xoff_cross = 0.5 * float(B_base_sec)
            if str(delta_sigma_mode) == DELTA_SIGMA_MODE_LECTURE:
                delta_sigma_func_cross = (
                    lambda z, qval=q_sec, Bval=float(B_base_sec), xoff=float(xoff_cross):
                    float(delta_sigma_strip(q=float(qval), B=float(Bval), z=float(z), x=float(xoff)))
                )
            else:
                delta_sigma_func_cross = (lambda z, qval=q_sec: float(qval))

            if layers_df_for_x_section is not None and len(layers_df_for_x_section) > 0 and "s_cum_m" in layers_df_for_x_section.columns:
                S_Cc_slices = float(layers_df_for_x_section["s_cum_m"].iloc[-1])
            else:
                S_Cc_slices = float(r["rho_c"])
            z_mid_cross = 0.5 * H0_sec
            sigma0_mid_cross = sigma_v0_prime_kpa(z_mid_cross, stress_cross)
            delta_sigma_mid_cross = float(delta_sigma_func_cross(z_mid_cross))
            ratio_mid_cross = (sigma0_mid_cross + delta_sigma_mid_cross) / max(1e-3, sigma0_mid_cross)
            S_Cc_mid = (float(Cc) / (1.0 + float(e0))) * H0_sec * math.log10(ratio_mid_cross)

            mv_table = build_settlement_integration_table_mv(
                H0=H0_sec,
                m_v=float(m_v),
                delta_sigma_func=delta_sigma_func_cross,
                stress=stress_cross,
                n_slices=n_slices_cross,
            )
            S_mv_slices = float(mv_table["S_total_m"])
            # Assumption: mv is constant with depth for this simplified coursework model.
            S_mv_mid = float(m_v) * delta_sigma_mid_cross * H0_sec

            def _pct_diff(slice_val: float, mid_val: float) -> float:
                denom = max(abs(slice_val), 1e-12)
                return 100.0 * abs(mid_val - slice_val) / denom

            pct_cc_slice_mid = _pct_diff(S_Cc_slices, S_Cc_mid)
            pct_mv_slice_mid = _pct_diff(S_mv_slices, S_mv_mid)
            pct_cc_vs_mv_slices = _pct_diff(S_Cc_slices, S_mv_slices)

            st.markdown(
                f"Nearest computed chainage: **x={x_sec_val:.1f} m**  \n"
                f"Slice size: **dz = H0/N = {H0_sec:.3f}/{n_slices_cross} = {dz_cross:.4f} m**  \n"
                f"Δσ(H0/2): **{delta_sigma_mid_cross:.3f} kPa** | σ′v0(H0/2): **{sigma0_mid_cross:.3f} kPa**"
            )
            cc1, cc2 = st.columns(2)
            with cc1:
                st.metric("S_Cc_slices", f"{S_Cc_slices:.4f} m ({S_Cc_slices * 1000.0:.1f} mm)")
                st.metric("S_Cc_mid", f"{S_Cc_mid:.4f} m ({S_Cc_mid * 1000.0:.1f} mm)")
                st.metric("Cc slice vs mid", f"{pct_cc_slice_mid:.2f}%")
            with cc2:
                st.metric("S_mv_slices", f"{S_mv_slices:.4f} m ({S_mv_slices * 1000.0:.1f} mm)")
                st.metric("S_mv_mid", f"{S_mv_mid:.4f} m ({S_mv_mid * 1000.0:.1f} mm)")
                st.metric("mv slice vs mid", f"{pct_mv_slice_mid:.2f}%")
            st.metric("Cc_slices vs mv_slices (method sensitivity)", f"{pct_cc_vs_mv_slices:.2f}%")
            st.caption("Cross-check shows both methods; they are different constitutive assumptions so results need not match.")
        else:
            st.info("Method cross-check unavailable at this x_section (requires H0>0 and q_equiv>0).")

    st.subheader("x=0 summary (depth slices → evidence)")
    if x0_summary and x0_summary.get("ok"):
        if x0_summary.get("consol_times_missing"):
            st.warning("No consolidation times at x=0 (H0<=0 or missing values).")
        hd_txt = f"{x0_summary.get('Hd_m', float('nan')):.3f} m" if x0_summary.get("Hd_m") is not None else "—"
        t20_txt = f"{x0_summary.get('U20_t_years', float('nan')):.3f} yrs" if x0_summary.get("U20_t_years") is not None else "—"
        t50_txt = f"{x0_summary.get('U50_t_years', float('nan')):.3f} yrs" if x0_summary.get("U50_t_years") is not None else "—"
        t90_txt = f"{x0_summary.get('U90_t_years', float('nan')):.3f} yrs" if x0_summary.get("U90_t_years") is not None else "—"
        c_x0_1, c_x0_2 = st.columns(2)
        with c_x0_1:
            st.markdown(
                f"σ′v0(z) min/max: **{x0_summary['sigma_v0_prime_min_kpa']:.3f} / {x0_summary['sigma_v0_prime_max_kpa']:.3f} kPa**  \n"
                f"Δσ(z) min/max: **{x0_summary['delta_sigma_min_kpa']:.3f} / {x0_summary['delta_sigma_max_kpa']:.3f} kPa**  \n"
                f"ds(z) min/max: **{x0_summary['ds_min_m']:.4f} / {x0_summary['ds_max_m']:.4f} m**  \n"
                f"Max ds at z_mid={x0_summary['ds_max_z_mid_m']:.3f} m "
                f"(σ′v0={x0_summary['ds_max_sigma_v0_prime_kpa']:.3f} kPa, Δσ={x0_summary['ds_max_delta_sigma_kpa']:.3f} kPa)"
            )
        with c_x0_2:
            st.markdown(
                f"S_primary(x=0): **{x0_summary['S_primary_m']:.4f} m ({x0_summary['S_primary_mm']:.1f} mm)**  \n"
                f"Hd (drainage path): **{hd_txt}**  \n"
                f"t20 / t50 / t90: **{t20_txt} / {t50_txt} / {t90_txt}**"
            )
    elif x0_summary and not x0_summary.get("ok"):
        st.info(f"x=0 summary unavailable: {x0_summary.get('reason', 'unknown issue')}")
    else:
        st.info("Run calculations to populate x=0 settlement/consolidation summary.")

    show_debug = st.checkbox("Show debug checks", value=False)
    if show_debug:
        with st.expander("Debug (optional): x=0 audit check", expanded=False):
            if df1 is not None and len(df1) > 0 and layer_table_x0 is not None and len(layer_table_x0) > 0:
                idx_x0 = (df1["x"] - 0.0).abs().idxmin()
                r0 = df1.loc[idx_x0]
                H0_x0 = float(r0["H0"])
                z_mid = 0.5 * H0_x0
                if use_flood_wt:
                    z_wt_val_ui = max(0.0, float(r0["ground level"]) - FLOOD_10YR_AOD_M)
                else:
                    z_wt_val_ui = 0.0 if water_table_at_ground else float(z_wt_m)
                if z_mid <= z_wt_val_ui:
                    sigma_v_mid = float(gamma_clay) * z_mid
                    u_mid = 0.0
                else:
                    sigma_v_mid = float(gamma_clay) * z_wt_val_ui + float(gamma_clay) * (z_mid - z_wt_val_ui)
                    u_mid = float(gamma_w) * (z_mid - z_wt_val_ui)
                sigma_v0_mid = max(sigma_v_mid - u_mid, 1e-3)
                st.markdown(
                    f"**x=0 mid-depth (z=H0/2):** H0={H0_x0:.3f} m, z_mid={z_mid:.3f} m  \n"
                    f"σv={sigma_v_mid:.3f} kPa, u={u_mid:.3f} kPa → σ′v0={sigma_v0_mid:.3f} kPa"
                )
                st.caption("Slice preview (first 5 rows) from settlement integration table at x≈0.")
                st.dataframe(layer_table_x0.head(5), use_container_width=True, hide_index=True)
            else:
                st.info("No settlement integration table available at x=0 (check H0 and inputs).")
    with st.expander("Formulas used", expanded=False):
        q_formula_text = "q = γ_fill * H_fill" if q_immediate_method == Q_METHOD_LECTURE else "q = q_equiv (trapezoid)"
        st.markdown("E_u = (E_u/c_u) * c_u")
        st.markdown("ρ_i = q * B_base * I_s / E_u")
        st.markdown("μ0 = 1 for D/B = 0; I_s may be input directly or via μ1 (I_s=μ0μ1)")
        st.markdown("Chart ratios shown: H/B = H0/B_base; α=0; L/B→∞")
        st.markdown(q_formula_text)
        st.latex(r"\sigma_v(z)=\gamma_{\text{unsat}}z\ (z\le z_{wt});\ \sigma_v=\gamma_{\text{unsat}}z_{wt}+\gamma_{\text{sat}}(z-z_{wt})\ (z>z_{wt})")
        st.latex(r"u(z)=0\ (z\le z_{wt});\ u=\gamma_w(z-z_{wt})\ (z>z_{wt});\ \sigma'_{v0}=\max(\sigma_v-u,10^{-3}\text{ kPa})")
        if str(delta_sigma_mode) == DELTA_SIGMA_MODE_LECTURE:
            st.markdown("Δσ(z) computed using Craig strip method (Barnes equivalent): Δσ = q * Iσ(a/z, b/z)")
            st.markdown("Stress point: centre (x=0) OR edge (x=B/2) applied to Δσ(z)")
        else:
            st.markdown("Quick approximation: Δσ(z)=q constant with depth (upper bound)")
        st.markdown(r"**Terzaghi 1D (log10):** $ds=\frac{C_c}{1+e_0}dz\log_{10}\frac{\sigma'_{v0}+\Delta\sigma}{\sigma'_{v0}},\ S=\sum ds$")
        st.latex(r"\rho_{\text{total}} = \rho_i + S")
        st.latex(r"Z_{\text{construct}} = Z_{\text{finish}} + \rho_{\text{total}}")
    st.caption("**Values carried forward →** rho_total used for Z_construct and construction cross-section")
    st.markdown("**Evidence notes:**")
    for note in EVIDENCE_NOTES:
        st.caption(note)

    # -------------------------------------------------------------------------
    # 4) Consolidation Time (Vertical)
    # -------------------------------------------------------------------------
    st.header("Consolidation Time (Vertical)")
    t90_col = "U90_t_years"
    if t90_col in week2_chainage_df.columns:
        i_max = week2_chainage_df[t90_col].astype(float).idxmax()
        rmax = week2_chainage_df.loc[i_max]
        st.metric("Worst-case t90 (years)", f"{float(rmax[t90_col]):.2f}")
        st.caption(f"Occurs at x = {float(rmax['x']):.1f} m")
        if float(rmax[t90_col]) > 5.0:
            st.warning("t90 > 5 years: long-term consolidation settlement likely (programme risk).")
    st.dataframe(week2_chainage_df, use_container_width=True, hide_index=True)
    with st.expander("Formulas used", expanded=False):
        st.latex(r"T_v = \frac{C_v \, t}{H_d^2} \implies t = \frac{T_v \, H_d^2}{C_v}")
        st.markdown(r"**U(T_v) series:** $U = 1 - \sum_{n=0}^{\infty}\frac{8}{\pi^2(2n+1)^2}e^{-(2n+1)^2\pi^2 T_v/4}$")
        st.caption("Tv(U) solved by bisection (80-term truncation).")
        st.latex(r"H_d = H_0 \text{ (single drainage)} \quad \text{or} \quad H_d = H_0/2 \text{ (double drainage)}")
    st.caption("**Values carried forward →** Tv and t_years for U20/U50/U90")

    # -------------------------------------------------------------------------
    # 5) Slope Stability (Short-term Undrained)
    # -------------------------------------------------------------------------
    st.header("Slope Stability (Short-term Undrained)")
    if not run_slope_stability:
        st.info("Slope stability is OFF. Tick 'Run slope stability analysis' in the sidebar and click Run to compute.")
    elif slope_stab_result is None:
        st.warning("Slope stability was not run in the last calculation. Ensure the checkbox is enabled and click Run.")
    else:
        min_FOS, best_yc, best_zc, best_R, best_L_arc, all_results, arc_geom, best_result, attempted_circles, invalid_no_intersection, invalid_span, invalid_depth, invalid_toe, invalid_behind_crest, invalid_embankment, valid_count, yc_list, zc_list, fos_min_at_center_list, R_list_best, fos_list_best = slope_stab_result
        debug_extra = f", invalid_toe={invalid_toe}, invalid_behind_crest={invalid_behind_crest}, invalid_embankment={invalid_embankment}" if is_half_domain else ""
        st.write(
            f"Debug: attempted={attempted_circles}, valid={valid_count}, "
            f"invalid_no_intersection={invalid_no_intersection}, invalid_span={invalid_span}, invalid_depth={invalid_depth}{debug_extra}, "
            f"valid_centres={len(yc_list)}"
        )
        if min_FOS is None:
            st.error(
                "No valid slip circles found. Try widening the grid/radius ranges: "
                "increase grid_x_min/max, extend grid_z_min (deeper), grid_z_max (shallower), or circle_radius_min/max."
            )
        elif len(yc_list) == 0:
            st.error("Slope stability ran but found ZERO valid centres. Widen grid bounds or radius range.")
        else:
            with st.expander("Formulas used", expanded=False):
                st.latex(r"M_{\text{drive}} = \sum (W_i \cdot d_i)")
                st.latex(r"W_i = \gamma \cdot A_i")
                st.latex(r"M_{\text{resist}} = c_u \cdot L_{\text{arc}} \cdot R")
                st.latex(r"\text{FOS} = \frac{M_{\text{resist}}}{M_{\text{drive}}}")
            with st.expander("Assumptions (slope stability)", expanded=True):
                st.info(
                    "**Short-term undrained analysis** during construction (per A6 lecture). "
                    "Circular slip surfaces searched via grid of centres. "
                    "Moments: overturning M_drive = Σ(Wᵢ·dᵢ), resisting M_resist = c_u·L_arc·R (as per A6 slide). "
                    "Slice weights from chosen unit weight option."
                )
            st.markdown(
                f"**Debug counts:** attempted={attempted_circles}, valid={valid_count}, "
                f"invalid_no_intersection={invalid_no_intersection}, invalid_span={invalid_span}, invalid_depth={invalid_depth}"
                + (f", invalid_toe={invalid_toe}, invalid_behind_crest={invalid_behind_crest}, invalid_embankment={invalid_embankment}" if is_half_domain else "")
                + f", best (min) FOS={min_FOS:.4f}"
            )
            eval_count = attempted_circles - (invalid_no_intersection + invalid_span + invalid_depth + invalid_toe + invalid_behind_crest + invalid_embankment)
            valid_rate = valid_count / max(1, eval_count)
            if valid_rate < 0.02:
                st.warning("Very few valid circles found (<2%). Consider widening grid bounds or radius range.")
            pass_fail = "✓ Pass" if min_FOS >= min_FOS_required else "✗ Fail"
            domain_label = f"Half embankment ({stability_side})" if is_half_domain else "Full embankment (toe → toe)"
            st.markdown(f"**Domain:** {domain_label}")
            st.metric("Minimum FOS", f"{min_FOS:.3f}", delta=pass_fail)
            c_ss1, c_ss2, c_ss3, c_ss4 = st.columns(4)
            with c_ss1:
                st.metric("Circle centre (yc, zc)", f"({best_yc:.1f}, {best_zc:.1f}) mAOD")
            with c_ss2:
                st.metric("Radius R (m)", f"{best_R:.1f}")
            with c_ss3:
                st.metric("Arc length L_arc (m)", f"{best_L_arc:.2f}")
            with c_ss4:
                y_ent, y_ext = best_result["y_entry"], best_result["y_exit"]
                st.metric("y_entry → y_exit (m)", f"{y_ent:.2f} → {y_ext:.2f}", help="Crest-to-toe span (HALF) or full span (FULL)")
            W_tot = best_result["W_total"]
            M_dr = best_result["M_drive"]
            M_res = best_result["M_resist"]
            st.markdown(
                f"**W_total (kN/m):** {W_tot:.1f} | "
                f"**M_drive (kN·m/m):** {M_dr:.1f} | "
                f"**M_resist (kN·m/m):** {M_res:.1f}"
            )
            st.markdown(f"**min_FOS >= min_FOS_required ({min_FOS_required})?** {pass_fail}")

            if min_FOS < 1.0:
                st.error("**Interpretation:** Predicted instability (failure likely)")
            elif min_FOS < 1.3:
                st.warning("**Interpretation:** Marginal / below requirement")
            else:
                st.success("**Interpretation:** Pass")

            cu_required = cu * min_FOS_required / min_FOS
            st.markdown(
                f"**Required c_u for target FOS ({min_FOS_required}):** "
                f"c_u,required = c_u,current × (FOS_target / FOS_current) = "
                f"{cu:.1f} × ({min_FOS_required} / {min_FOS:.3f}) = **{cu_required:.1f} kPa**"
            )

            if arc_geom is not None:
                y_arc, z_arc, gl, bl, Zf, Bt, Bb = arc_geom[:7]
                arc_domain_mode = arc_geom[7] if len(arc_geom) > 7 else "full"
                arc_side = arc_geom[8] if len(arc_geom) > 8 else "Right"
                fig_slope, ax_slope = plt.subplots(figsize=(10, 6))
                ax_slope.set_xlabel("Horizontal y (m)")
                ax_slope.set_ylabel("Level (mAOD)")
                ax_slope.set_title(f"Critical slip circle at x = {x_stability:.0f} m — FOS = {min_FOS:.3f}")
                ax_slope.axhline(gl, color="brown", ls="-", lw=2, label="ground")
                ax_slope.axhline(bl, color="sienna", ls="--", lw=1.5, label="bedrock")
                half_w = max(80, Bb / 2 + 30)
                ax_slope.fill_between([-half_w, half_w], bl, gl, color="sienna", alpha=0.2)
                # Embankment: HALF mode = one side wedge (crest→toe); FULL = full trapezoid
                if arc_domain_mode == "half":
                    y_crest = (Bt / 2.0) if arc_side == "Right" else (-Bt / 2.0)
                    y_toe = (Bb / 2.0) if arc_side == "Right" else (-Bb / 2.0)
                    y_pts = np.linspace(y_crest - 40, y_toe + 40, 80) if arc_side == "Right" else np.linspace(y_toe - 40, y_crest + 40, 80)
                    z_surf_pts = np.array([z_surface_half(y, gl, Zf, arc_side, Bt, Bb) for y in y_pts])
                    ax_slope.fill_between(y_pts, gl, z_surf_pts, where=(z_surf_pts >= gl), color="green", alpha=0.3, label="embankment")
                    ax_slope.plot(y_pts, z_surf_pts, color="darkgreen", lw=2)
                else:
                    trap_x = [-Bb/2, -Bt/2, Bt/2, Bb/2, -Bb/2]
                    trap_z = [gl, Zf, Zf, gl, gl]
                    ax_slope.fill(trap_x, trap_z, color="green", alpha=0.3, label="embankment")
                    ax_slope.plot(trap_x, trap_z, color="darkgreen", lw=2)
                ax_slope.plot(y_arc, z_arc, "r-", lw=3, label="critical slip arc")
                if arc_domain_mode == "half" and mirror_for_display:
                    y_arc_mirror = -y_arc
                    ax_slope.plot(y_arc_mirror, z_arc, "r--", lw=1.5, alpha=0.6, label="mirrored")
                ax_slope.plot(best_yc, best_zc, "ko", markersize=8, label="circle centre")
                ax_slope.set_xlim(-half_w, half_w)
                z_lo = min(bl - 5, float(np.min(z_arc)) - 2) if len(z_arc) > 0 else bl - 5
                ax_slope.set_ylim(z_lo, max(Zf + 3, gl + 5))
                ax_slope.legend(loc="upper right")
                ax_slope.grid(True, alpha=0.3)
                ax_slope.set_aspect("equal", adjustable="box")
                plt.tight_layout()
                st.pyplot(fig_slope)
                plt.close()

            st.subheader("Slope stability search graphics")
            if len(yc_list) < 5 and len(yc_list) >= 1:
                st.warning(f"Only {len(yc_list)} valid centre(s) found — landscape is sparse; widen search bounds.")
            fig_land, ax_land = plt.subplots(figsize=(8, 5))
            sc = ax_land.scatter(yc_list, zc_list, c=fos_min_at_center_list, s=40)
            fig_land.colorbar(sc, ax=ax_land, label="Min FOS at centre (across radii)")
            ax_land.scatter([best_yc], [best_zc], marker="X", s=120, color="red", edgecolors="black", linewidths=2)
            ax_land.set_xlabel("Circle centre yc (m)")
            ax_land.set_ylabel("Circle centre zc (mAOD)")
            ax_land.set_title("Grid search: minimum FOS at each circle centre")
            ax_land.invert_yaxis()
            ax_land.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig_land)
            plt.close()

            if R_list_best and fos_list_best:
                fig2_rad, ax2_rad = plt.subplots(figsize=(7, 4))
                ax2_rad.plot(R_list_best, fos_list_best, marker="o")
                ax2_rad.set_xlabel("Radius R (m)")
                ax2_rad.set_ylabel("FOS (-)")
                ax2_rad.set_title("Best centre: FOS vs radius")
                ax2_rad.grid(True, alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig2_rad)
                plt.close()

            if all_results:
                sorted_results = sorted(all_results, key=lambda x: x["fos"])[:10]
                top10_df = pd.DataFrame(sorted_results).rename(columns={"fos": "FOS"})
                st.markdown("**Top 10 lowest FOS circles**")
                st.caption("Moments are per metre run (kN·m per m).")
                st.dataframe(top10_df, use_container_width=True, hide_index=True)

            if best_result is not None and df1 is not None:
                with st.expander("Sanity checks (expected trends)", expanded=True):
                    idx_stab = (df1["x"] - x_stability).abs().idxmin()
                    r_stab = df1.loc[idx_stab]
                    gl = float(r_stab["ground level"])
                    Zf = float(r_stab["Z_finish"])
                    Bb = float(r_stab["B_base"])
                    Bt = B_top
                    yc_star, zc_star, R_star = best_result["yc"], best_result["zc"], best_result["R"]
                    dom_mode = "half" if is_half_domain else "full"
                    dom_side = stability_side if is_half_domain else "Right"
                    res_base = slope_stability_fos(
                        yc_star, zc_star, R_star, gl, Zf, Bt, Bb,
                        cu, gamma_fill, gamma_clay, unit_weight_for_W, int(n_slices),
                        domain_mode=dom_mode, side=dom_side)
                    res_cu2 = slope_stability_fos(
                        yc_star, zc_star, R_star, gl, Zf, Bt, Bb,
                        cu, gamma_fill, gamma_clay, unit_weight_for_W, int(n_slices), cu_scale=2.0,
                        domain_mode=dom_mode, side=dom_side)
                    res_g11 = slope_stability_fos(
                        yc_star, zc_star, R_star, gl, Zf, Bt, Bb,
                        cu, gamma_fill, gamma_clay, unit_weight_for_W, int(n_slices), gamma_scale=1.1,
                        domain_mode=dom_mode, side=dom_side)
                    res_fill11 = slope_stability_fos(
                        yc_star, zc_star, R_star, gl, Zf, Bt, Bb,
                        cu, gamma_fill, gamma_clay, unit_weight_for_W, int(n_slices), fill_area_scale=1.1,
                        domain_mode=dom_mode, side=dom_side)
                    FOS_base = res_base["fos"] if res_base else float("nan")
                    FOS_cu2 = res_cu2["fos"] if res_cu2 else float("nan")
                    FOS_g11 = res_g11["fos"] if res_g11 else float("nan")
                    FOS_fill11 = res_fill11["fos"] if res_fill11 else float("nan")
                    W_base = res_base["W_total"] if res_base else float("nan")
                    W_cu2 = res_cu2["W_total"] if res_cu2 else float("nan")
                    W_g11 = res_g11["W_total"] if res_g11 else float("nan")
                    W_fill11 = res_fill11["W_total"] if res_fill11 else float("nan")
                    pass_cu2 = FOS_cu2 > FOS_base if res_cu2 and res_base else False
                    pass_g11 = FOS_g11 < FOS_base if res_g11 and res_base else False
                    pass_fill11 = FOS_fill11 < FOS_base if res_fill11 and res_base else False
                    sanity_rows = [
                        {"Case": "Base case", "FOS": FOS_base, "W_total (kN/m)": W_base, "Expected": "-", "PASS": "-"},
                        {"Case": "cu ×2", "FOS": FOS_cu2, "W_total (kN/m)": W_cu2, "Expected": "higher", "PASS": "✓" if pass_cu2 else "✗"},
                        {"Case": "gamma ×1.1", "FOS": FOS_g11, "W_total (kN/m)": W_g11, "Expected": "lower", "PASS": "✓" if pass_g11 else "✗"},
                        {"Case": "fill ×1.1", "FOS": FOS_fill11, "W_total (kN/m)": W_fill11, "Expected": "lower", "PASS": "✓" if pass_fill11 else "✗"},
                    ]
                    sanity_df = pd.DataFrame(sanity_rows)
                    st.dataframe(sanity_df, use_container_width=True, hide_index=True)

                    if st.button("Quick sensitivity: denser search", key="sens_dense"):
                        with st.spinner("Running denser grid search..."):
                            grid_nx_sens = int(grid_nx * 1.5)
                            grid_nz_sens = int(grid_nz * 1.5)
                            radius_steps_sens = int(radius_steps * 2)
                            sens_result = slope_stability_grid_search(
                                df1, x_stability, grid_x_min, grid_x_max, grid_z_min, grid_z_max,
                                grid_nx_sens, grid_nz_sens, circle_radius_min, circle_radius_max, n_slices,
                                cu, gamma_fill, gamma_clay, unit_weight_for_W, B_top, n_radii=radius_steps_sens,
                                max_depth_below_ground=max_depth_below_ground, span_mode=span_requirement,
                                depth_constraint_mode=depth_constraint_mode, bedrock_margin=bedrock_margin,
                                domain_mode="half" if is_half_domain else "full", side=stability_side, tol=intersection_tolerance,
                                require_pass_through_embankment=require_pass_through_embankment if is_half_domain else False,
                                max_cover_height=max_cover_height if is_half_domain else 2.0)
                            min_FOS_sens = sens_result[0]
                        st.markdown(f"**Base min_FOS:** {min_FOS:.4f} | **Denser min_FOS:** {min_FOS_sens:.4f}" if min_FOS_sens is not None else f"**Base min_FOS:** {min_FOS:.4f} | **Denser:** no valid circles")
                        if min_FOS_sens is not None and min_FOS > 1e-12:
                            pct_diff = 100.0 * abs(min_FOS_sens - min_FOS) / min_FOS
                            st.markdown(f"**% difference:** {pct_diff:.1f}%")
                            if pct_diff > 10.0:
                                st.warning("Min FOS changes >10% with denser search; increase search resolution for final results.")
            st.caption("**Values carried forward →** Min FOS, required c_u feed into design decisions")

    # -------------------------------------------------------------------------
    # 6) Summary (Values carried forward)
    # -------------------------------------------------------------------------
    st.header("Summary (Values carried forward)")
    sum_rows = [
        {"Metric": "Max H_fill (m)", "Value": f"{df1['H_fill'].max():.3f}"},
        {"Metric": "Max q_equiv (kPa)", "Value": f"{df1['q_equiv'].max():.2f}"},
        {"Metric": "Max ρ_total (m)", "Value": f"{df1['rho'].max():.4f}"},
        {"Metric": "Max Z_construct (mAOD)", "Value": f"{df1['Z_rev'].max():.3f}"},
    ]
    x_vol = df1["x"].values
    A_vol = df1["A_trap"].values
    try:
        V_fill = np.trapezoid(A_vol, x_vol)
    except AttributeError:
        # Fallback if trapezoid isn't available for any reason
        V_fill = float(((A_vol[:-1] + A_vol[1:]) * 0.5 * (x_vol[1:] - x_vol[:-1])).sum())
    sum_rows.append({"Metric": "Fill volume (m³)", "Value": f"{V_fill:,.0f}"})
    if run_slope_stability and slope_stab_result is not None:
        min_FOS_val = slope_stab_result[0]
        if min_FOS_val is not None:
            sum_rows.append({"Metric": "Min FOS", "Value": f"{min_FOS_val:.3f}"})
            cu_req = cu * min_FOS_required / min_FOS_val
            sum_rows.append({"Metric": "Required c_u for target FOS (kPa)", "Value": f"{cu_req:.1f}"})
    summary_table_df = pd.DataFrame(sum_rows)
    st.dataframe(summary_table_df, use_container_width=True, hide_index=True)

    idx_we = (df1["x"] - 500.0).abs().idxmin()
    rw_we = df1.loc[idx_we]
    st.subheader("At x=500 (worked example)")
    st.markdown(f"""
| Quantity | Value |
|----------|-------|
| H₀ | {float(rw_we['H0']):.3f} m |
| H_fill | {float(rw_we['H_fill']):.3f} m |
| B_base | {float(rw_we['B_base']):.3f} m |
| q | {float(rw_we['q_equiv']):.3f} kPa |
| ρ_i | {float(rw_we['rho_i']):.4f} m |
| ρ_c | {float(rw_we['rho_c']):.4f} m |
| ρ_total | {float(rw_we['rho']):.4f} m |
| Z_construct | {float(rw_we['Z_rev']):.3f} mAOD |
""")

    with st.expander("Detailed tables", expanded=False):
        st.markdown("**Chainage df**")
        st.dataframe(df1, use_container_width=True, hide_index=True)
        st.markdown("**Key sections df**")
        st.dataframe(key_df, use_container_width=True, hide_index=True)
        st.markdown("**Week2 time df**")
        st.dataframe(week2_chainage_df, use_container_width=True, hide_index=True)
        if run_slope_stability and slope_stab_result is not None and slope_stab_result[5]:
            sorted_res = sorted(slope_stab_result[5], key=lambda x: x["fos"])[:10]
            top10_slope_df = pd.DataFrame(sorted_res).rename(columns={"fos": "FOS"})
            st.markdown("**Slope top10 df**")
            st.dataframe(top10_slope_df, use_container_width=True, hide_index=True)
        val_df = pd.DataFrame(settlement_summary)
        st.markdown("**Settlement summary (key chainages)**")
        st.dataframe(val_df, use_container_width=True, hide_index=True)
        if monotonic_warnings:
            warn_df = pd.DataFrame(monotonic_warnings)
            st.warning("Non-monotonic settlement vs load detected (H_fill ↑ but ρ_c ↓). See table below.")
            st.dataframe(warn_df, use_container_width=True, hide_index=True)

else:
    st.info("Click **Run calculations** in the sidebar to run.")

st.caption(f"Build: {APP_BUILD}")
