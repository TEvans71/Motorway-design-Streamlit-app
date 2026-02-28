import math
import numpy as np

from geotech_core_settlement import (
    StressInputs,
    sigma_v0_prime_kpa,
    settlement_primary_1d,
    Uv_from_Tv,
    Tv_from_Uv,
    consolidation_time_years,
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
