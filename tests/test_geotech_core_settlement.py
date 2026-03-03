import math
import numpy as np

from geotech_core_settlement import (
    StressInputs,
    Tv_from_Uv,
    Uv_from_Tv,
    consolidation_times_table,
    consolidation_times_table_sand_drain,
    consolidation_time_years,
    sand_drain_design_fixed_point,
    settlement_primary_1d,
    sigma_v0_prime_kpa,
)


def test_Tv_from_U_known_values_close():
    # Standard reference approximate values (average consolidation):
    # U=20% -> Tv ~ 0.0314
    # U=50% -> Tv ~ 0.196
    # U=90% -> Tv ~ 0.848
    tv20 = Tv_from_Uv(0.20)
    tv50 = Tv_from_Uv(0.50)
    tv90 = Tv_from_Uv(0.90)

    assert abs(tv20 - 0.0314) < 0.002
    assert abs(tv50 - 0.196) < 0.01
    assert abs(tv90 - 0.848) < 0.03


def test_Uv_from_Tv_inverts_reasonably():
    for U in [0.20, 0.50, 0.90]:
        Tv = Tv_from_Uv(U)
        U_back = Uv_from_Tv(Tv)
        assert abs(U_back - U) < 1e-4


def test_effective_stress_water_table_at_ground():
    # WT at ground => z_wt=0; below WT total uses gamma_sat; u uses gamma_w
    s = StressInputs(gamma_unsat_kN_m3=18.0, gamma_sat_kN_m3=20.0, gamma_w_kN_m3=9.81, z_wt_m=0.0)
    z = 10.0
    # σ' = (γ_sat - γw)*z
    expected = (20.0 - 9.81) * z
    got = sigma_v0_prime_kpa(z, s)
    assert abs(got - expected) < 1e-6


def test_effective_stress_water_table_below_ground_piecewise():
    s = StressInputs(gamma_unsat_kN_m3=18.0, gamma_sat_kN_m3=20.0, gamma_w_kN_m3=9.81, z_wt_m=2.0)

    # z above WT: u=0, σv=γ_unsat*z
    z1 = 1.0
    got1 = sigma_v0_prime_kpa(z1, s)
    exp1 = 18.0 * z1
    assert abs(got1 - exp1) < 1e-6

    # z below WT:
    # σv=γ_unsat*zw + γ_sat*(z-zw)
    # u=γw*(z-zw)
    z2 = 6.0
    exp2 = (18.0 * 2.0 + 20.0 * (6.0 - 2.0)) - (9.81 * (6.0 - 2.0))
    got2 = sigma_v0_prime_kpa(z2, s)
    assert abs(got2 - exp2) < 1e-6


def test_settlement_zero_if_no_load():
    s = StressInputs(gamma_unsat_kN_m3=18.0, gamma_sat_kN_m3=20.0, gamma_w_kN_m3=9.81, z_wt_m=0.0)
    H0 = 10.0
    Cc = 0.25
    e0 = 1.0
    S, _rows = settlement_primary_1d(
        H0=H0,
        Cc=Cc,
        e0=e0,
        delta_sigma_func=lambda z: 0.0,
        stress=s,
        n_slices=50,
        log_base=10,
    )
    assert abs(S) < 1e-12


def test_settlement_increases_with_load_same_point():
    s = StressInputs(gamma_unsat_kN_m3=18.0, gamma_sat_kN_m3=20.0, gamma_w_kN_m3=9.81, z_wt_m=0.0)
    H0 = 10.0
    Cc = 0.25
    e0 = 1.0

    S1, _ = settlement_primary_1d(
        H0=H0,
        Cc=Cc,
        e0=e0,
        delta_sigma_func=lambda z: 50.0,
        stress=s,
        n_slices=60,
        log_base=10,
    )
    S2, _ = settlement_primary_1d(
        H0=H0,
        Cc=Cc,
        e0=e0,
        delta_sigma_func=lambda z: 55.0,
        stress=s,
        n_slices=60,
        log_base=10,
    )
    assert S2 > S1


def test_consolidation_time_increases_with_U():
    Cv = 1e-7
    Hd = 8.0
    _Tv20, t20 = consolidation_time_years(Cv, Hd, 0.20)
    _Tv50, t50 = consolidation_time_years(Cv, Hd, 0.50)
    _Tv90, t90 = consolidation_time_years(Cv, Hd, 0.90)
    assert t20 < t50 < t90


def test_pvd_design_matches_notebook_target_spacing():
    design = sand_drain_design_fixed_point(
        Ur_target=0.88764,
        Ch_m2_per_s=1e-7,
        t_design_years=2.0,
        rd_m=0.15,
    )
    assert abs(float(design["n_final"]) - 12.69) < 0.05
    assert abs(float(design["S_m"]) - 3.374) < 0.02


def test_pvd_combined_t90_is_lower_than_vertical_only():
    H0 = 8.0
    Cv = 1e-7
    drainage = "double"
    design = sand_drain_design_fixed_point(
        Ur_target=0.88764,
        Ch_m2_per_s=1e-7,
        t_design_years=2.0,
        rd_m=0.15,
    )
    vertical = consolidation_times_table(Cv_m2_per_s=Cv, H0_m=H0, drainage=drainage, U_targets=(0.2, 0.5, 0.9))
    combined = consolidation_times_table_sand_drain(
        Cv_m2_per_s=Cv,
        H0_m=H0,
        drainage=drainage,
        Ch_m2_per_s=1e-7,
        spacing_s_m=float(design["S_m"]),
        rd_m=float(design["rd_m"]),
        U_targets=(0.9,),
    )
    assert float(combined.iloc[0]["U90_t_years"]) < float(vertical.iloc[0]["U90_t_years"])
