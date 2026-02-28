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
    "xw": 500.0, "xs": 500.0,
    "cdm": "Layered (sum over N layers)", "Nlayers": 20, "csp": "Centre (x = 0)",
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

# Layered consolidation options
consolidation_depth_method = "Layered (sum over N layers)"
N_layers = 20
consol_stress_point = "Centre (x = 0)"

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
    consol_point = consol_stress_point

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
    Eu = Eu_over_cu * cu
    rho_i = [(q * B * Is / Eu) if Eu > 0.0 else 0.0 for q, B in zip(qeq, B_base)]

    Delta_sigma_mid = []
    rho_c = []
    rho_c_centre_list = []
    rho_c_edge_list = []
    rho_c_method_list = []
    rho_c_point_list = []
    layer_tables_by_chainage = {}
    sigma_v0_prime_mins = []

    stress_inputs_by_chainage = {}
    n_slices_settlement = 60
    log_base_settlement = 10.0
    consol_method_value = str(consol_method).strip().lower()
    S_cc_slices_by_chainage = {}
    S_mv_slices_by_chainage = {}

    for chainage_idx, (q, B, h0, x_val, g_level) in enumerate(zip(qeq, B_base, H0_list, chainages, ground)):
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
        delta_sigma_func = (lambda z, qval=q: float(qval))

        if h0 <= 0.0 or q <= 0.0:
            Delta_sigma_mid.append(0.0)
            rho_c.append(0.0)
            rho_c_centre_list.append(0.0)
            rho_c_edge_list.append(0.0)
            rho_c_method_list.append("mv slices (uniform Δσ)" if consol_method_value == "mv" else "Terzaghi 1D log10 (uniform Δσ)")
            rho_c_point_list.append("centre (uniform Δσ)")
            S_cc_slices_by_chainage[x_val] = 0.0
            S_mv_slices_by_chainage[x_val] = 0.0
            layer_tables_by_chainage[x_val] = pd.DataFrame(columns=[
                "z_mid_m", "dz_m", "sigma_v0_prime_kpa", "delta_sigma_kpa",
                "sigma_vf_prime_kpa", "ds_m", "s_cum_m",
            ])
            continue

        Delta_sigma_mid.append(delta_sigma_func(0.5 * h0))

        S_cc_slices_m, _ = settlement_primary_1d(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=delta_sigma_func,
            stress=stress_inputs,
            n_slices=n_slices_settlement,
            log_base=log_base_settlement,
        )
        layer_table = build_settlement_integration_table(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=delta_sigma_func,
            stress=stress_inputs,
            n_slices=n_slices_settlement,
            log_base=log_base_settlement,
        )
        mv_result = build_settlement_integration_table_mv(
            H0=h0,
            m_v=float(m_v),
            delta_sigma_func=delta_sigma_func,
            stress=stress_inputs,
            n_slices=int(n_slices_settlement),
        )
        if isinstance(mv_result, dict):
            if "S_total_m" in mv_result:
                S_mv_slices_m = float(mv_result["S_total_m"])
            else:
                mv_rows = mv_result.get("rows")
                S_mv_slices_m = float(mv_rows["s_cum_m"].iloc[-1]) if mv_rows is not None and len(mv_rows) > 0 else 0.0
        else:
            S_mv_slices_m = float(mv_result[1]) if len(mv_result) > 1 else 0.0

        S_cc_slices_by_chainage[x_val] = float(S_cc_slices_m)
        S_mv_slices_by_chainage[x_val] = float(S_mv_slices_m)

        if consol_method_value == "mv":
            rho_c_x = float(S_mv_slices_m)
        else:
            rho_c_x = float(S_cc_slices_m)

        layer_tables_by_chainage[x_val] = layer_table.copy()
        if len(layer_table) > 0:
            sigma_v0_prime_mins.append(layer_table["sigma_v0_prime_kpa"].min())

        # --- Local monotonicity check (evidence-based, same chainage) ---
        # Settlement should increase if the applied load increases at the SAME x (same σ'0 + same H0).
        # This is the only valid monotonicity sanity check.
        eps = 0.05  # 5% load bump (small enough to be "local")
        q_base = float(q)  # q_equiv_kpa at this chainage
        S_base = float(S_cc_slices_m)
        S_plus_m, _ = settlement_primary_1d(
            H0=h0,
            Cc=Cc,
            e0=e0,
            delta_sigma_func=lambda z, qval=q_base * (1.0 + eps): float(qval),
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
        rho_c_centre_list.append(rho_c_x)
        rho_c_edge_list.append(rho_c_x)
        rho_c_method_list.append("mv slices (uniform Δσ)" if consol_method_value == "mv" else "Terzaghi 1D log10 (uniform Δσ)")
        rho_c_point_list.append("centre (uniform Δσ)")

    rho = [ri + rc for ri, rc in zip(rho_i, rho_c)]
    rho_total_centre = [ri + rc for ri, rc in zip(rho_i, rho_c_centre_list)]
    rho_total_edge = [ri + rc for ri, rc in zip(rho_i, rho_c_edge_list)]
    delta_rho_c_edge_minus_centre = [re - rc for re, rc in zip(rho_c_edge_list, rho_c_centre_list)]
    Z_rev = [zf + r for zf, r in zip(Z_finish, rho)]
    df = pd.DataFrame({
        "x": chainages, "ground level": ground, "bedrock level": bedrock, "H0": H0_list,
        "Z_finish": Z_finish, "H_fill": H_fill, "B_base": B_base, "A_trap": Atrap,
        "W_line": Wline, "q_equiv": qeq, "rho_i": rho_i, "Delta_sigma_mid": Delta_sigma_mid,
        "rho_c": rho_c, "rho": rho, "Z_rev": Z_rev,
        "rho_c_centre (m)": rho_c_centre_list, "rho_c_edge (m)": rho_c_edge_list,
        "rho_total_centre (m)": rho_total_centre, "rho_total_edge (m)": rho_total_edge,
        "delta_rho_c_edge_minus_centre (m)": delta_rho_c_edge_minus_centre,
        "rho_c_method": rho_c_method_list, "rho_c_point": rho_c_point_list,
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
    report.append(f"  E_u = (E/c_u)c_u = {Eu_over_cu:.1f}*{cu:.3f} = {Eu_over_cu*cu:.3f} kPa")
    report.append(f"  ρ_i = ({float(rw['q_equiv']):.3f}*{float(rw['B_base']):.3f}*{Is:.3f})/{Eu_over_cu*cu:.3f} = {float(rw['rho_i']):.3f} m")
    report.append("")
    report.append("Pre-fill effective stress σ′v0 (natural ground only)")
    report.append("  σv(z) = γ_unsat z (z ≤ z_wt); else γ_unsat z_wt + γ_sat (z - z_wt)")
    report.append(f"  σv(z_mid={z_mid:.3f}) = {sigma_total_mid:.3f} kPa")
    report.append(f"  u(z_mid) = γ_w (z - z_wt) = {u_mid:.3f} kPa")
    report.append(f"  σ′v0 = σv - u = {sigma_eff_mid:.3f} kPa (clipped to {sigma_eff_mid_clipped:.3f} kPa)")
    report.append("")
    report.append("Δσ assumption (wide embankment → near-uniform stress)")
    report.append("  Δσ(z) = q_equiv (constant with depth)")
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

    return (
        df,
        key_df,
        report_df,
        summary_df,
        layers_df_for_x_section,
        settlement_summary,
        neg_dsigma_chainages,
        layer_table_x0,
        monotonic_warnings,
    )


# =============================================================================
# 4) EXPORT WEEK 1
# =============================================================================

def export_week1_excel(df, key_df, report_df, summary_df, layers_df_for_x_section=None):
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
        "consol_method": consol_method, "m_v": m_v, "Cc": Cc, "e0": e0, "x_worked": x_worked,
        "consolidation_depth_method": consolidation_depth_method,
        "N_layers": N_layers,
        "consol_stress_point": consol_stress_point,
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
        for name in ["Inputs", "Week1_Chainage", "Week1_KeySections", "Week1_Report", "Week1_ConsolLayers_xSection"]:
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
                out[k] = float(times_row[k])

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


def export_additional_csvs(df, week2_chainage_df, layer_table_x0=None):
    """CSV exports for settlement and consolidation evidence."""
    ensure_dir(OUTPUT_FOLDER)
    paths = {}

    if df is not None and len(df) > 0:
        sett_df = pd.DataFrame({
            "x_m": df["x"],
            "S_primary_m": df["rho_c"],
            "S_primary_mm": df["rho_c"] * 1000.0,
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
        align_df = pd.DataFrame({
            "chainage_m": df["x"],
            "Z_design_mAOD": df["Z_finish"],
            "settlement_total_m": df["rho"],
            "Z_construct_mAOD": df["Z_rev"],
            "note": "Z_construct = Z_design + settlement (design as post-settlement target).",
        })
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
if st.sidebar.button("Reset to group defaults", type="secondary"):
    for k, v in GROUP_DEFAULTS.items():
        st.session_state[k] = v
    st.rerun()

st.sidebar.header("Project Inputs")
with st.sidebar.expander("Chainage & geometry", expanded=True):
    L = st.number_input("L (m)", value=1000.0, min_value=100.0, step=50.0, key="L")
    dx = st.number_input("dx (m)", value=50.0, min_value=10.0, step=10.0, key="dx")
    ground_A = st.number_input("ground_A (mAOD)", value=49.6, step=0.1, key="ga")
    ground_B = st.number_input("ground_B (mAOD)", value=50.5, step=0.1, key="gb")
    x_c = st.number_input("x_c (m)", value=500.0, step=50.0, key="xc")
    bedrock_c = st.number_input("bedrock_c (m)", value=30.05, step=0.1, key="bc")
    bedrock_goes_down_towards_B = st.checkbox("bedrock_goes_down_towards_B", value=True, key="bdown")
    B_top = st.number_input("B_top (m)", value=43.3, min_value=1.0, step=1.0, key="btop")
    m = st.number_input("m (side slope 2H:1V)", value=2.0, min_value=0.5, step=0.5, key="m")
with st.sidebar.expander("Finished road"):
    flood_level = st.number_input("flood_level (m)", value=54.0, step=0.5, key="flood")
    freeboard = st.number_input("freeboard (m)", value=1.0, step=0.1, key="fb")
    Z_peak_finish = st.number_input("Z_peak_finish (m)", value=55.0, step=0.5, key="z0")
    grade = st.number_input("grade (m/m)", value=1.0/200.0, format="%.6f", step=0.001, key="grade")
with st.sidebar.expander("Soils & consolidation"):
    gamma_fill = st.number_input("γ_fill (kN/m³)", value=20.0, min_value=1.0, step=1.0, key="gf")
    gamma_clay = st.number_input("γ_clay (kN/m³)", value=18.0, step=1.0, key="gc")
    gamma_w = st.number_input("γ_w (kN/m³)", value=10.0, step=1.0, key="gw")
    water_table_at_ground = st.checkbox("water_table_at_ground", value=True, key="wt")
    use_flood_wt = st.checkbox("Use 10-year flood level as water level (54 m AOD)", value=True)
    z_wt_m = st.number_input("z_wt_m (m below ground)", value=0.0, min_value=0.0, step=0.1, key="zw", help="Water table depth below ground. If WT at ground, set 0.")
    consol_method = st.selectbox(
        "Primary consolidation settlement model",
        ["mv", "Cc"],
        index=0,
        key="cm",
        format_func=lambda v: "mv (given)" if v == "mv" else "Cc/log10 (normally consolidated)",
    )
    m_v = st.number_input("m_v (m²/kN)", value=0.0005, format="%.6f", step=0.0001, key="mv")
    Cc = st.number_input("Cc", value=0.35, step=0.05, key="Cc")
    e0 = st.number_input("e0", value=0.335, step=0.01, key="e0")
    cu = st.number_input("c_u (kPa)", value=15.0, min_value=0.1, step=1.0, key="cu")
    Is = st.number_input("I_s", value=1.0, step=0.1, key="Is")
    Eu_over_cu = st.number_input("E_u/c_u", value=300.0, min_value=1.0, step=50.0, key="Ecu")
    x_worked = st.number_input("x_worked (m)", value=500.0, step=50.0, key="xw")
    consolidation_depth_method = st.selectbox(
        "Consolidation depth method",
        options=["Single-point (lecture baseline: z = H0/2)", "Layered (sum over N layers)"],
        index=1,
        key="cdm"
    )
    if consolidation_depth_method == "Layered (sum over N layers)":
        N_layers = st.number_input(
            "N layers for consolidation (N)",
            value=20,
            min_value=2,
            max_value=200,
            step=1,
            key="Nlayers"
        )
    else:
        N_layers = 20
    consol_stress_point = st.selectbox(
        "Stress point for consolidation Δσ",
        options=["Centre (x = 0)", "Edge (x = B/2)"],
        index=0,
        key="csp"
    )

st.sidebar.header("Vertical consolidation")
with st.sidebar.expander("Vertical consolidation", expanded=True):
    Cv_m2_per_s = st.number_input("Cv (m²/s)", value=1e-7, format="%.0e", step=1e-8, key="Cv")
    vertical_drainage = st.selectbox("vertical_drainage", ["double", "single"], index=0, key="vd")
    Uv_targets_str = st.text_input("Uv_targets (comma-sep)", value="0.20, 0.50, 0.90", key="Uvt")

x_section = st.sidebar.number_input("Cross-section chainage x_section (m)", value=500.0, min_value=0.0, step=50.0, key="xs")

st.sidebar.header("Slope stability (short-term)")
if "run_slope" not in st.session_state:
    st.session_state["run_slope"] = True
with st.sidebar.expander("Slope stability (short-term)", expanded=False):
    run_slope_stability = st.checkbox(
        "Run slope stability analysis",
        value=True,
        key="run_slope",
        help="Week 5 short-term undrained circular slip grid search."
    )
    stability_analysis_domain = st.selectbox(
        "Stability analysis domain",
        options=[
            "Half embankment (crest → toe) [coursework]",
            "Full embankment (toe → toe) [optional]",
        ],
        index=0,
        key="stab_domain",
        help="Half: analyse one side slope only (crest to toe). Full: analyse full width."
    )
    is_half_domain = "Half" in stability_analysis_domain
    if is_half_domain:
        stability_side = st.selectbox(
            "Side",
            options=["Right", "Left"],
            index=0,
            key="stab_side",
            help="Which half of the embankment to analyse."
        )
    else:
        stability_side = "Right"
    intersection_tolerance = st.number_input(
        "Intersection tolerance (m)",
        value=2.0,
        min_value=0.1,
        max_value=10.0,
        step=0.5,
        key="intersection_tol",
        help="How close the slip circle must intersect crest/toe."
    )
    mirror_for_display = st.checkbox(
        "Mirror for display",
        value=False,
        key="mirror_display",
        help="(HALF mode only) Also plot the mirrored arc in a lighter line."
    )
    if is_half_domain:
        require_pass_through_embankment = st.checkbox(
            "Require pass through embankment",
            value=True,
            key="req_pass_emb",
            help="(HALF only) Slip arc must cut into the embankment wedge (match lecture sketch)."
        )
        max_cover_height = st.number_input(
            "Max cover height (m)",
            value=2.0,
            min_value=0.5,
            max_value=10.0,
            step=0.5,
            key="max_cover_height",
            help="Slip arc must come within this vertical distance of the embankment surface on the slope face."
        )
    else:
        require_pass_through_embankment = False
        max_cover_height = 2.0
    x_stability = st.number_input("x_stability (chainage, m)", value=float(x_section), min_value=0.0, step=50.0, key="xstab")
    n_slices = st.number_input("n_slices", value=30, min_value=10, max_value=200, step=5, key="nslices")
    grid_x_min = st.number_input("grid_x_min (m)", value=-120.0, step=10.0, key="gxmin")
    grid_x_max = st.number_input("grid_x_max (m)", value=120.0, step=10.0, key="gxmax")
    _ground_est = lin(x_stability, 0.0, ground_A, L, ground_B)
    grid_z_min = st.number_input("grid_z_min (mAOD)", value=round(_ground_est - 5.0, 2), format="%.2f", step=1.0, key="gzmin",
                                 help="Lower z bound for centre grid (default ground-5)")
    grid_z_max = st.number_input("grid_z_max (mAOD)", value=round(_ground_est + 80.0, 2), format="%.2f", step=1.0, key="gzmax",
                                 help="Upper z bound for centre grid (default ground+80; include above ground for toe circles)")
    grid_nx = st.number_input("grid_nx", value=15, min_value=2, max_value=50, step=1, key="gnx")
    grid_nz = st.number_input("grid_nz", value=10, min_value=2, max_value=30, step=1, key="gnz")
    circle_radius_min = st.number_input("circle_radius_min (m)", value=10.0, min_value=1.0, step=5.0, key="rmin")
    circle_radius_max = st.number_input("circle_radius_max (m)", value=400.0, min_value=10.0, step=10.0, key="rmax")
    radius_steps = st.number_input("radius_steps", value=120, min_value=10, max_value=500, step=10, key="radsteps",
                                   help="Number of radius values in grid search")
    span_requirement = st.selectbox(
        "Span requirement",
        options=["Base toes (strict)", "Top width only (lenient)", "None (debug)"],
        index=0,
        key="span_req",
        help="Base toes: arc must span full base width. Top width: arc spans top only. None: no span check."
    )
    min_FOS_required = st.number_input("min_FOS_required", value=1.3, min_value=1.0, step=0.1, key="minFOS")
    max_depth_below_ground = st.number_input(
        "Max slip depth below ground (m)",
        value=40.0,
        min_value=5.0,
        max_value=200.0,
        step=5.0,
        key="max_depth_below_ground",
        help="Prevents unrealistic deep circles. Does NOT assume bedrock is rigid."
    )
    depth_constraint_mode = st.selectbox(
        "Depth constraint mode",
        options=[
            "Limit below ground (current)",
            "Limit below bedrock (recommended)"
        ],
        index=1,
        key="depth_constraint_mode"
    )
    if depth_constraint_mode == "Limit below bedrock (recommended)":
        bedrock_margin = st.number_input(
            "Allow slip below bedrock (m)",
            value=0.0,
            min_value=0.0,
            max_value=20.0,
            step=0.5,
            key="bedrock_margin",
            help="0 means slip surface cannot go below bedrock."
        )
    else:
        bedrock_margin = 0.0
    unit_weight_for_W = st.selectbox(
        "Unit weight for slice weight W",
        options=["gamma_fill", "gamma_clay", "gamma_fill_above_ground + gamma_clay_below"],
        index=2,
        key="uw_W"
    )

run_btn = st.sidebar.button("Run calculations", type="primary")

try:
    Uv_targets = [float(x.strip()) for x in Uv_targets_str.split(",") if x.strip()]
except ValueError:
    Uv_targets = [0.20, 0.50, 0.90]

Zmin_finish = flood_level + freeboard

df1 = key_df = report_df = summary_df = None
week2_chainage_df = None
out_path = None
layers_df_for_x_section = None
layer_table_x0 = None
settlement_summary = []
neg_dsigma_chainages = []
monotonic_warnings = []
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
            monotonic_warnings,
        ) = week1_calculate()
        out_path = export_week1_excel(df1, key_df, report_df, summary_df, layers_df_for_x_section)
        week2_chainage_df = week2_run(df1)
        out_path = export_add_week2_sheets(out_path, week2_chainage_df)
        csv_paths = export_additional_csvs(df1, week2_chainage_df, layer_table_x0)
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
    half_w = max(80, B_base_sec / 2 + 20)
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    ax2.set_xlabel("Horizontal (m)")
    ax2.set_ylabel("Level (mAOD)")
    ax2.set_title(f"Cross section at chainage x = {float(r['x']):.0f} m")
    ax2.axhline(ground_lev, color="brown", ls="-", lw=2, label="ground")
    ax2.axhline(bedrock_lev, color="sienna", ls="--", lw=1.5, label="bedrock")
    ax2.fill_between([-half_w, half_w], bedrock_lev, ground_lev, color="sienna", alpha=0.2)
    if layers_df_for_x_section is not None and len(layers_df_for_x_section) > 0:
        dz_col = "dz_m" if "dz_m" in layers_df_for_x_section.columns else "dz (m)"
        dz_sec = float(layers_df_for_x_section.iloc[0][dz_col])
        N_sec = len(layers_df_for_x_section)
        for i in range(N_sec):
            z_top = i * dz_sec
            z_bot = (i + 1) * dz_sec
            y_top = ground_lev - z_top
            y_bot = ground_lev - z_bot
            lbl = f"clay layers (N={N_sec})" if i == 0 else None
            ax2.fill_between([-half_w, half_w], y_bot, y_top, color="sienna", alpha=0.15, edgecolor="saddlebrown", lw=0.5, label=lbl)
    if H_fill_sec > 0:
        trap_x = [-B_base_sec/2, -B_top/2, B_top/2, B_base_sec/2, -B_base_sec/2]
        trap_z = [ground_lev, ground_lev + H_fill_sec, ground_lev + H_fill_sec, ground_lev, ground_lev]
        ax2.fill(trap_x, trap_z, color="green", alpha=0.3, label="embankment")
        ax2.plot(trap_x, trap_z, color="darkgreen", lw=2.5)
    ax2.annotate(f"B_top = {B_top:.1f} m", xy=(0, ground_lev + H_fill_sec + 0.5), fontsize=9, ha="center")
    ax2.annotate(f"B_base = {B_base_sec:.1f} m", xy=(0, ground_lev - 1.5), fontsize=9, ha="center")
    ax2.annotate(f"H_fill = {H_fill_sec:.1f} m", xy=(-B_base_sec/2 - 3, ground_lev + H_fill_sec/2), fontsize=9, ha="right", va="center")
    ax2.annotate(f"H0 = {H0_sec:.1f} m", xy=(B_base_sec/2 + 3, ground_lev - H0_sec/2), fontsize=9, ha="left", va="center")
    ax2.annotate(f"m = 2H:1V", xy=(-B_base_sec/2 - 5, ground_lev + H_fill_sec*0.3), fontsize=9, ha="right")
    ax2.set_ylim(bedrock_lev - 2, ground_lev + H_fill_sec + 4)
    ax2.set_xlim(-half_w, half_w)
    ax2.legend(loc="upper right")
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
        ax3.fill(trap_c_x, trap_c_z, color="red", alpha=0.2, label="Construction surface (raised by settlement)")
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
        edge_gt_centre = with_clay["delta_rho_c_edge_minus_centre (m)"] > 0
        if edge_gt_centre.all():
            st.warning("Edge ρ_c > centre ρ_c at all chainages (H0>0). Stress normally decreases toward strip edge—check x sign in Craig strip geometry if unexpected.")

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
        st.caption("Longitudinal profile (ρ, Z_construct) shown in Geometry section.")
    with st.expander("Settlement integration table at x_section (slices)", expanded=False):
        if layers_df_for_x_section is not None:
            st.dataframe(layers_df_for_x_section, use_container_width=True, hide_index=True)
        else:
            st.info("No settlement slices available (H0<=0 or settlement not computed at this chainage).")

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
        # Assumption: same Δσ(z) model as current workflow (uniform with depth).
        delta_sigma_func_cross = lambda z, qval=q_sec: float(qval)

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
        st.latex(r"E_u = (E_u/c_u) \cdot c_u")
        st.latex(r"\rho_i = \frac{q \cdot B \cdot I_s}{E_u}\quad \text{(B = B\_base)}")
        st.latex(r"\sigma_v(z)=\gamma_{\text{unsat}}z\ (z\le z_{wt});\ \sigma_v=\gamma_{\text{unsat}}z_{wt}+\gamma_{\text{sat}}(z-z_{wt})\ (z>z_{wt})")
        st.latex(r"u(z)=0\ (z\le z_{wt});\ u=\gamma_w(z-z_{wt})\ (z>z_{wt});\ \sigma'_{v0}=\max(\sigma_v-u,10^{-3}\text{ kPa})")
        st.markdown(r"**Δσ assumption:** Δσ(z)=q_equiv (constant with depth; wide embankment preliminary model)")
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

st.caption("Build stamp: slope-stability-graphics-v1")
