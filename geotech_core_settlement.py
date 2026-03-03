"""Core settlement and consolidation calculations (evidence-based).

This module provides stress calculations, primary consolidation (Terzaghi 1D),
and consolidation time relationships using the Uv–Tv series solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle
import pandas as pd

SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0
SECONDS_PER_YEAR_NOTES = 31536000.0  # 365*24*3600 (locked for lecturer notebook parity)

SAND_DRAIN_N_POINTS = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0]
TR_UR_085 = [0.222, 0.373, 0.467, 0.534, 0.587, 0.629, 0.697, 0.750, 0.793, 0.861, 0.914]
TR_UR_090 = [0.270, 0.455, 0.567, 0.649, 0.712, 0.764, 0.847, 0.911, 0.963, 1.046, 1.110]


@dataclass
class StressInputs:
    gamma_unsat_kN_m3: float
    gamma_sat_kN_m3: float
    gamma_w_kN_m3: float = 9.81
    z_wt_m: float = 0.0


def _total_stress_kpa(z: float, stress: StressInputs) -> float:
    """Total vertical stress σv at depth z (kPa)."""
    if z <= 0.0:
        return 0.0
    z_unsat = min(z, stress.z_wt_m)
    sigma = stress.gamma_unsat_kN_m3 * z_unsat
    if z > stress.z_wt_m:
        sigma += stress.gamma_sat_kN_m3 * (z - stress.z_wt_m)
    return float(sigma)


def _pore_pressure_kpa(z: float, stress: StressInputs) -> float:
    """Hydrostatic pore pressure u at depth z (kPa)."""
    if z <= stress.z_wt_m:
        return 0.0
    return float(stress.gamma_w_kN_m3 * (z - stress.z_wt_m))


def sigma_v0_prime_kpa(z: float, stress: StressInputs, eps_kpa: float = 1e-3) -> float:
    """Pre-fill effective stress σ′v0 clipped to eps to avoid log(0)."""
    sigma_total = _total_stress_kpa(z, stress)
    u = _pore_pressure_kpa(z, stress)
    sigma_eff = sigma_total - u
    return float(max(sigma_eff, eps_kpa))


def _integration_rows(
    H0: float,
    Cc: float,
    e0: float,
    delta_sigma_func: Callable[[float], float],
    stress: StressInputs,
    n_slices: int = 60,
    log_base: float = 10.0,
    eps_kpa: float = 1e-3,
) -> List[dict]:
    if H0 <= 0.0:
        return []
    dz = H0 / float(n_slices)
    rows: List[dict] = []
    s_cum = 0.0
    for i in range(n_slices):
        z_mid = (i + 0.5) * dz
        sigma0 = sigma_v0_prime_kpa(z_mid, stress, eps_kpa=eps_kpa)
        delta_sigma = float(delta_sigma_func(z_mid))
        sigma_final = sigma0 + delta_sigma
        ratio = sigma_final / max(eps_kpa, sigma0)
        if ratio <= 0.0:
            raise ValueError("Stress ratio non-positive; check Δσ and σ′v0.")
        ds = (Cc / (1.0 + e0)) * dz * math.log(ratio, log_base)
        s_cum += ds
        rows.append({
            "z_mid_m": z_mid,
            "dz_m": dz,
            "sigma_v0_prime_kpa": sigma0,
            "delta_sigma_kpa": delta_sigma,
            "sigma_vf_prime_kpa": sigma_final,
            "ds_m": ds,
            "s_cum_m": s_cum,
        })
    return rows


def settlement_primary_1d(
    H0: float,
    Cc: float,
    e0: float,
    delta_sigma_func: Callable[[float], float],
    stress: StressInputs,
    n_slices: int = 60,
    log_base: float = 10.0,
    eps_kpa: float = 1e-3,
) -> Tuple[float, List[dict]]:
    """Terzaghi 1D primary consolidation settlement (log10 form)."""
    rows = _integration_rows(H0, Cc, e0, delta_sigma_func, stress, n_slices, log_base, eps_kpa)
    if not rows:
        return 0.0, []
    return float(rows[-1]["s_cum_m"]), rows


def build_settlement_integration_table(
    H0: float,
    Cc: float,
    e0: float,
    delta_sigma_func: Callable[[float], float],
    stress: StressInputs,
    n_slices: int = 60,
    log_base: float = 10.0,
    eps_kpa: float = 1e-3,
) -> pd.DataFrame:
    """Return slice-by-slice integration table for settlement."""
    rows = _integration_rows(H0, Cc, e0, delta_sigma_func, stress, n_slices, log_base, eps_kpa)
    return pd.DataFrame(rows)


def build_settlement_integration_table_mv(
    H0: float,
    m_v: float,
    delta_sigma_func,
    stress: StressInputs,
    n_slices: int = 60,
) -> dict:
    """Return slice-by-slice mv settlement integration outputs."""
    if H0 <= 0.0:
        return {
            "rows": pd.DataFrame(columns=[
                "z_mid_m",
                "dz_m",
                "sigma_v0_prime_kpa",
                "delta_sigma_kpa",
                "ds_m",
                "s_cum_m",
            ]),
            "S_total_m": 0.0,
            "dz_m": 0.0,
            "n_slices": int(n_slices),
        }
    dz = H0 / float(n_slices)
    rows: List[dict] = []
    s_cum = 0.0
    for i in range(n_slices):
        z_mid = (i + 0.5) * dz
        sigma0 = sigma_v0_prime_kpa(z_mid, stress)
        delta_sigma = float(delta_sigma_func(z_mid))
        ds = float(m_v) * delta_sigma * dz
        s_cum += ds
        rows.append({
            "z_mid_m": z_mid,
            "dz_m": dz,
            "sigma_v0_prime_kpa": sigma0,
            "delta_sigma_kpa": delta_sigma,
            "ds_m": ds,
            "s_cum_m": s_cum,
        })
    return {
        "rows": pd.DataFrame(rows),
        "S_total_m": float(s_cum),
        "dz_m": float(dz),
        "n_slices": int(n_slices),
    }


def Uv_from_Tv(Tv: float, terms: int = 80) -> float:
    """Average degree of consolidation U(Tv) via series solution."""
    if Tv <= 0.0:
        return 0.0
    s = 0.0
    for n in range(terms):
        coef = 8.0 / (math.pi ** 2 * (2 * n + 1) ** 2)
        s += coef * math.exp(-((2 * n + 1) ** 2) * (math.pi ** 2) * Tv / 4.0)
    return float(1.0 - s)


def Tv_from_Uv(U_target: float, tol: float = 1e-6, max_iter: int = 200, terms: int = 80) -> float:
    """Invert U(Tv) using bisection."""
    if U_target <= 0.0:
        return 0.0
    if U_target >= 1.0:
        return float("inf")
    lo, hi = 0.0, 1.0
    while Uv_from_Tv(hi, terms) < U_target:
        hi *= 2.0
        if hi > 1e6:
            raise ValueError("Failed to bracket Tv for requested U.")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        Umid = Uv_from_Tv(mid, terms)
        if abs(Umid - U_target) < tol:
            return float(mid)
        if Umid < U_target:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def consolidation_time_years(Cv: float, Hd: float, U_target: float) -> tuple:
    """Return (Tv, t_years) for a target U."""
    if Cv <= 0.0:
        raise ValueError("Cv must be > 0 for consolidation time.")
    if Hd <= 0.0:
        raise ValueError("Hd must be > 0 for consolidation time.")
    Tv = Tv_from_Uv(U_target)
    t_seconds = Tv * (Hd ** 2) / Cv if math.isfinite(Tv) else float("inf")
    t_years = t_seconds / SECONDS_PER_YEAR if math.isfinite(t_seconds) else float("inf")
    return float(Tv), float(t_years)


def consolidation_times_table(
    Cv_m2_per_s: float,
    H0_m: float,
    drainage: str,
    U_targets: Iterable[float] = (0.20, 0.50, 0.90),
) -> pd.DataFrame:
    """Wide table of Tv and times for target U values."""
    drainage_mode = (drainage or "").strip().lower()
    if drainage_mode not in {"single", "double"}:
        raise ValueError("drainage must be 'single' or 'double'")
    Hd = H0_m if drainage_mode == "single" else H0_m / 2.0
    row = {
        "drainage": drainage_mode,
        "Hd_m": Hd,
        "Cv_m2_per_s": Cv_m2_per_s,
    }
    for U in U_targets:
        Tv, t_years = consolidation_time_years(Cv_m2_per_s, Hd, U)
        label = f"U{int(round(U * 100))}"
        row[f"{label}_Tv"] = Tv
        row[f"{label}_t_years"] = t_years
    return pd.DataFrame([row])


def _linear_interp_piecewise(x: float, x_list: List[float], y_list: List[float]) -> float:
    """Linear interpolation between nearest chart points (endpoint-clamped)."""
    if len(x_list) != len(y_list) or len(x_list) < 2:
        raise ValueError("x_list and y_list must have equal length >= 2.")
    if x <= x_list[0]:
        return float(y_list[0])
    if x >= x_list[-1]:
        return float(y_list[-1])
    for i in range(len(x_list) - 1):
        x0, x1 = float(x_list[i]), float(x_list[i + 1])
        if x0 <= x <= x1:
            y0, y1 = float(y_list[i]), float(y_list[i + 1])
            w = (x - x0) / (x1 - x0)
            return float(y0 + w * (y1 - y0))
    return float(y_list[-1])


def _validate_sand_drain_tr_table() -> None:
    if not TR_UR_085 or not TR_UR_090:
        raise ValueError("Fill TR_UR_085 and TR_UR_090 from lecture table")
    if len(SAND_DRAIN_N_POINTS) < 2 or len(TR_UR_085) != len(SAND_DRAIN_N_POINTS) or len(TR_UR_090) != len(SAND_DRAIN_N_POINTS):
        raise ValueError("Fill TR_UR_085 and TR_UR_090 from lecture table")
    if any(v is None for v in TR_UR_085) or any(v is None for v in TR_UR_090):
        raise ValueError("Fill TR_UR_085 and TR_UR_090 from lecture table")


def tr_from_table(n_value: float, ur_target: float) -> float:
    """Interpolate lecture TR(n, Ur) between Ur=0.85 and Ur=0.90 curves."""
    _validate_sand_drain_tr_table()
    n = float(n_value)
    ur = float(ur_target)
    n_min = float(SAND_DRAIN_N_POINTS[0])
    n_max = float(SAND_DRAIN_N_POINTS[-1])
    if n < n_min or n > n_max:
        raise ValueError(f"n={n:.3f} outside TR table range. Extend N_POINTS/TR arrays.")
    if ur < 0.85 or ur > 0.90:
        raise ValueError("Ur target outside available lecture curves. Extend TR table to cover more Ur curves.")
    alpha = (ur - 0.85) / 0.05
    tr85 = _linear_interp_piecewise(n, SAND_DRAIN_N_POINTS, TR_UR_085)
    tr90 = _linear_interp_piecewise(n, SAND_DRAIN_N_POINTS, TR_UR_090)
    return float(tr85 + alpha * (tr90 - tr85))


def sand_drain_n_from_spacing(s_m: float, rd_m: float) -> float:
    """n = R/rd with equal-area square-grid assumption R = s/sqrt(pi)."""
    s = float(s_m)
    rd = float(rd_m)
    if s <= 0.0:
        raise ValueError("Drain spacing s must be > 0.")
    if rd <= 0.0:
        raise ValueError("Drain radius rd must be > 0.")
    r_influence = s / math.sqrt(math.pi)
    n = r_influence / rd
    n_min = float(SAND_DRAIN_N_POINTS[0])
    n_max = float(SAND_DRAIN_N_POINTS[-1])
    if n < n_min or n > n_max:
        raise ValueError(f"n={n:.3f} outside TR table range. Extend N_POINTS/TR arrays.")
    return float(n)


def sand_drain_time_for_ur(ur_target: float, s_m: float, rd_m: float, ch_value: float) -> float:
    """
    Sand-drain radial consolidation time from lecture rearrangement:
    t = 4 * rd^2 * TR(n,Ur) * n^2 / Ch
    """
    ch = float(ch_value)
    if ch <= 0.0:
        raise ValueError("Ch must be > 0 for sand drain consolidation time.")
    n = sand_drain_n_from_spacing(s_m=float(s_m), rd_m=float(rd_m))
    tr = tr_from_table(n_value=n, ur_target=float(ur_target))
    return float(4.0 * (float(rd_m) ** 2) * tr * (n ** 2) / ch)


def sand_drain_design_fixed_point(
    Ur_target: float,
    Ch_m2_per_s: float,
    t_design_years: float,
    rd_m: float,
    max_iter: int = 80,
    tol: float = 1e-6,
) -> dict:
    """Solve n, R and spacing for sand-drain layout at target Ur/time."""
    if Ch_m2_per_s <= 0.0:
        raise ValueError("Ch_m2_per_s must be > 0.")
    if t_design_years <= 0.0:
        raise ValueError("t_design_years must be > 0.")
    if rd_m <= 0.0:
        raise ValueError("rd_m must be > 0.")
    if Ur_target < 0.85 or Ur_target > 0.90:
        raise ValueError("Ur target outside available lecture curves. Extend TR table to cover more Ur curves.")

    ch_m2_per_yr = float(Ch_m2_per_s) * SECONDS_PER_YEAR_NOTES
    n_guess = 10.0
    it_used = 0
    converged = False

    for it in range(int(max_iter)):
        it_used = it + 1
        tr_val = tr_from_table(n_guess, Ur_target)
        n_new = math.sqrt((ch_m2_per_yr * float(t_design_years)) / (4.0 * (float(rd_m) ** 2) * tr_val))
        if abs(n_new - n_guess) < tol:
            n_guess = float(n_new)
            converged = True
            break
        n_guess = float(n_new)

    n_final = float(n_guess)
    n_min = float(SAND_DRAIN_N_POINTS[0])
    n_max = float(SAND_DRAIN_N_POINTS[-1])
    if n_final < n_min or n_final > n_max:
        raise ValueError(f"n={n_final:.3f} outside TR table range. Extend N_POINTS/TR arrays.")
    tr_final = tr_from_table(n_final, Ur_target)
    r_m = n_final * float(rd_m)
    de_m = 2.0 * r_m
    s_m = math.sqrt(math.pi) * r_m
    return {
        "Ur_target": float(Ur_target),
        "Ch_m2_per_s": float(Ch_m2_per_s),
        "Ch_m2_per_yr": float(ch_m2_per_yr),
        "t_design_years": float(t_design_years),
        "rd_m": float(rd_m),
        "n_final": n_final,
        "R_m": float(r_m),
        "De_m": float(de_m),
        "S_m": float(s_m),
        "Tr_final": float(tr_final),
        "iterations": int(it_used),
        "converged": bool(converged),
    }


def sand_drain_ur_from_time(
    t_seconds: float,
    s_m: float,
    rd_m: float,
    ch_m2_per_s: float,
    tol: float = 1e-6,
    max_iter: int = 120,
) -> float:
    """
    Invert t -> Ur via lecture TR table, constrained to Ur in [0.85, 0.90].
    Raises when requested t is outside this band's invertible range.
    """
    t = float(t_seconds)
    if t < 0.0:
        raise ValueError("Time t must be >= 0.")
    t85 = sand_drain_time_for_ur(0.85, s_m=s_m, rd_m=rd_m, ch_value=ch_m2_per_s)
    t90 = sand_drain_time_for_ur(0.90, s_m=s_m, rd_m=rd_m, ch_value=ch_m2_per_s)
    t_lo = min(t85, t90)
    t_hi = max(t85, t90)
    if t < t_lo or t > t_hi:
        raise ValueError(
            "Time falls outside Ur=0.85..0.90 band for sand drains; "
            "extend TR table to cover more Ur curves."
        )
    lo, hi = 0.85, 0.90
    for _ in range(int(max_iter)):
        mid = 0.5 * (lo + hi)
        t_mid = sand_drain_time_for_ur(mid, s_m=s_m, rd_m=rd_m, ch_value=ch_m2_per_s)
        if abs(t_mid - t) < tol:
            return float(mid)
        if t_mid < t:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def consolidation_times_table_sand_drain(
    Cv_m2_per_s: float,
    H0_m: float,
    drainage: str,
    Ch_m2_per_s: float,
    spacing_s_m: float,
    rd_m: float,
    U_targets: Iterable[float] = (0.90,),
    tol: float = 1e-6,
    max_iter: int = 200,
) -> pd.DataFrame:
    """Wide table of combined U(t)=1-(1-Uv)(1-Ur) with sand-drain radial inversion."""
    drainage_mode = (drainage or "").strip().lower()
    if drainage_mode not in {"single", "double"}:
        raise ValueError("drainage must be 'single' or 'double'")
    if Cv_m2_per_s <= 0.0:
        raise ValueError("Cv_m2_per_s must be > 0")
    if Ch_m2_per_s <= 0.0:
        raise ValueError("Ch_m2_per_s must be > 0")
    if spacing_s_m <= 0.0:
        raise ValueError("spacing_s_m must be > 0")
    if rd_m <= 0.0:
        raise ValueError("rd_m must be > 0")
    n_value = sand_drain_n_from_spacing(spacing_s_m, rd_m)
    if H0_m <= 0.0:
        row = {
            "drainage": drainage_mode,
            "Hd_m": 0.0,
            "Cv_m2_per_s": float(Cv_m2_per_s),
            "Ch_m2_per_s": float(Ch_m2_per_s),
            "spacing_s_m": float(spacing_s_m),
            "rd_m": float(rd_m),
            "n_final": float(n_value),
        }
        for U in U_targets:
            label = f"U{int(round(U * 100))}"
            row[f"{label}_t_years"] = float("inf")
        return pd.DataFrame([row])

    Hd = H0_m if drainage_mode == "single" else H0_m / 2.0

    def combined_U_at_t_years(t_years: float) -> float:
        t_seconds = float(t_years) * SECONDS_PER_YEAR
        Tv = float(Cv_m2_per_s) * t_seconds / (float(Hd) ** 2)
        Uv = Uv_from_Tv(Tv)
        Ur = sand_drain_ur_from_time(
            t_seconds=t_seconds,
            s_m=spacing_s_m,
            rd_m=rd_m,
            ch_m2_per_s=Ch_m2_per_s,
            tol=tol,
            max_iter=max_iter,
        )
        return float(1.0 - (1.0 - Uv) * (1.0 - Ur))

    t85_seconds = sand_drain_time_for_ur(0.85, s_m=spacing_s_m, rd_m=rd_m, ch_value=Ch_m2_per_s)
    t90_seconds = sand_drain_time_for_ur(0.90, s_m=spacing_s_m, rd_m=rd_m, ch_value=Ch_m2_per_s)
    t_lo_years = min(t85_seconds, t90_seconds) / SECONDS_PER_YEAR
    t_hi_years = max(t85_seconds, t90_seconds) / SECONDS_PER_YEAR

    def solve_time_for_U(U_target: float) -> float:
        if U_target <= 0.0:
            return 0.0
        if U_target >= 1.0:
            return float("inf")
        lo, hi = float(t_lo_years), float(t_hi_years)
        u_lo = combined_U_at_t_years(lo)
        u_hi = combined_U_at_t_years(hi)
        if U_target < u_lo or U_target > u_hi:
            raise ValueError(
                "Requested combined U is outside the Ur=0.85..0.90 invertible band; "
                "extend TR table to cover more Ur curves."
            )
        for _ in range(int(max_iter)):
            mid = 0.5 * (lo + hi)
            Umid = combined_U_at_t_years(mid)
            if abs(Umid - U_target) < tol:
                return float(mid)
            if Umid < U_target:
                lo = mid
            else:
                hi = mid
        return float(0.5 * (lo + hi))

    row = {
        "drainage": drainage_mode,
        "Hd_m": float(Hd),
        "Cv_m2_per_s": float(Cv_m2_per_s),
        "Ch_m2_per_s": float(Ch_m2_per_s),
        "spacing_s_m": float(spacing_s_m),
        "rd_m": float(rd_m),
        "n_final": float(n_value),
    }
    for U in U_targets:
        label = f"U{int(round(U * 100))}"
        row[f"{label}_t_years"] = float(solve_time_for_U(float(U)))
    return pd.DataFrame([row])


def plot_sand_drains_plan_view(
    length_m: float,
    width_m: float,
    spacing_s: float,
    rd: float,
    margin: float,
    title: str,
    motorway_width_m: float | None = None,
):
    """Return a matplotlib figure for sand-drain plan layout and embankment boundaries."""
    length = float(length_m)
    base_width = float(width_m)
    spacing = float(spacing_s)
    radius = float(rd)
    edge_margin = float(margin)
    if length <= 0.0 or base_width <= 0.0:
        raise ValueError("length_m and width_m must be > 0.")
    if spacing <= 0.0:
        raise ValueError("spacing_s must be > 0.")
    if radius <= 0.0:
        raise ValueError("rd must be > 0.")
    if edge_margin < 0.0:
        raise ValueError("margin must be >= 0.")
    if motorway_width_m is None:
        drain_band_width = base_width
    else:
        drain_band_width = float(motorway_width_m)
        if drain_band_width <= 0.0:
            raise ValueError("motorway_width_m must be > 0.")
        if drain_band_width > base_width:
            raise ValueError("motorway_width_m cannot exceed embankment base width.")

    y0_drain = 0.5 * (base_width - drain_band_width)
    y1_drain = y0_drain + drain_band_width
    x_centres = np.arange(edge_margin, max(edge_margin, length - edge_margin) + 1e-12, spacing)
    y_centres = np.arange(y0_drain + edge_margin, max(y0_drain + edge_margin, y1_drain - edge_margin) + 1e-12, spacing)
    if len(x_centres) == 0 or len(y_centres) == 0:
        raise ValueError("No drain centres fit in selected motorway-width band. Reduce margin or spacing.")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    footprint = Rectangle((0.0, 0.0), length, base_width, fill=False, linewidth=1.8, edgecolor="black")
    ax.add_patch(footprint)
    ax.plot([0.0, length], [0.0, 0.0], color="black", linewidth=2.0)
    ax.plot([0.0, length], [base_width, base_width], color="black", linewidth=2.0)
    ax.axhline(y=0.5 * base_width, linestyle="--", linewidth=1.0, color="gray")
    if drain_band_width < base_width:
        motorway_band = Rectangle(
            (0.0, y0_drain),
            length,
            drain_band_width,
            fill=False,
            linewidth=1.2,
            linestyle="--",
            edgecolor="#2c7fb8",
        )
        ax.add_patch(motorway_band)

    count = 0
    for x_val in x_centres:
        for y_val in y_centres:
            if x_val <= length - edge_margin + 1e-12 and y_val <= y1_drain - edge_margin + 1e-12:
                ax.add_patch(Circle((x_val, y_val), radius=radius, fill=False, linewidth=0.7, edgecolor="#1f77b4"))
                count += 1

    ax.set_xlim(-0.5, length + 0.5)
    ax.set_ylim(-0.5, base_width + 0.5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Chainage direction (m)")
    ax.set_ylabel("Width direction (m)")
    ax.set_title(
        f"{title} | s={spacing:.2f} m, dia={2.0 * radius:.3f} m, "
        f"motorway width={drain_band_width:.2f} m, drains={count}"
    )
    ax.grid(alpha=0.25, linestyle=":")
    fig.tight_layout()
    return fig
