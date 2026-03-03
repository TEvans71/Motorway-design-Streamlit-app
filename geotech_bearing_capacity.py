import numpy as np
import pandas as pd


CU_PROFILE_POINTS = [
    (0.0, 6.0),
    (2.0, 7.0),
    (5.0, 9.0),
    (10.0, 14.0),
    (15.0, 20.0),
    (20.0, 25.0),
]
CU_PROFILE_Z_MAX_M = max(z for z, _ in CU_PROFILE_POINTS)
# TODO: Replace with lecture-derived points.


def cu_at_depth_kpa(z_m: float, points=CU_PROFILE_POINTS) -> float:
    if z_m is None or pd.isna(z_m):
        return np.nan

    try:
        z_val = float(z_m)
    except (TypeError, ValueError):
        return np.nan

    if z_val < 0.0:
        return np.nan

    sorted_points = sorted(points, key=lambda p: float(p[0]))
    z_points = np.array([float(p[0]) for p in sorted_points], dtype=float)
    cu_points = np.array([float(p[1]) for p in sorted_points], dtype=float)
    return float(np.interp(z_val, z_points, cu_points))


def cu_min_over_depth_kpa(z_max_m: float, points=CU_PROFILE_POINTS, n=200) -> float:
    if z_max_m is None or pd.isna(z_max_m):
        return np.nan
    try:
        z_max_val = float(z_max_m)
    except (TypeError, ValueError):
        return np.nan
    if z_max_val < 0.0:
        return np.nan

    z_samples = np.linspace(0.0, z_max_val, int(n))
    cu_samples = np.array([cu_at_depth_kpa(z, points=points) for z in z_samples], dtype=float)
    return float(np.min(cu_samples))


def compute_bearing_capacity_table(
    df,
    gamma_fill_kN_m3: float = 20.0,
    gamma_f: float = 1.35,
    Nc: float = 5.14,
    gamma_M: float = 1.4,
    z_ref_m: float = 5.0,
    z_mode: str = "at_ref",
    z_ref_series=None,
) -> pd.DataFrame:
    required_columns = ["x", "H_fill", "H0"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    out = df.copy()
    out["h_fill_m"] = pd.to_numeric(out["H_fill"], errors="coerce")
    out["p_kPa"] = out["h_fill_m"] * float(gamma_fill_kN_m3)
    out["Ed_kPa"] = out["p_kPa"] * float(gamma_f)
    if z_ref_series is not None:
        out["z_ref_m"] = pd.to_numeric(z_ref_series, errors="coerce")
    else:
        out["z_ref_m"] = float(z_ref_m)

    if z_mode == "at_ref":
        out["Cu_kPa"] = out["z_ref_m"].apply(lambda z: cu_at_depth_kpa(z))
    elif z_mode == "min_0_to_ref":
        out["Cu_kPa"] = out["z_ref_m"].apply(lambda z: cu_min_over_depth_kpa(z))
    else:
        raise ValueError("z_mode must be 'at_ref' or 'min_0_to_ref'")
    out["Cu_d_kPa"] = out["Cu_kPa"] / float(gamma_M)
    out["qf_kPa"] = float(Nc) * out["Cu_d_kPa"] + out["p_kPa"]

    # Dimensionally consistent fix: safe bearing capacity equals gross design resistance.
    out["qs_kPa"] = out["qf_kPa"]

    out["utilisation"] = out["Ed_kPa"] / out["qs_kPa"]
    out["Cu_req_user_kPa"] = out["Ed_kPa"] / float(Nc)
    out["Cu_req_consistent_kPa"] = float(gamma_M) * (out["Ed_kPa"] - out["p_kPa"]) / float(Nc)
    out["Cu_req_consistent_kPa"] = out["Cu_req_consistent_kPa"].clip(lower=0.0)

    return out
