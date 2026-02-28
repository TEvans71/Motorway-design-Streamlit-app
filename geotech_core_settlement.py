"""Core settlement and consolidation calculations (evidence-based).

This module provides stress calculations, primary consolidation (Terzaghi 1D),
and consolidation time relationships using the Uv–Tv series solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, List, Tuple

import pandas as pd

SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0


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
