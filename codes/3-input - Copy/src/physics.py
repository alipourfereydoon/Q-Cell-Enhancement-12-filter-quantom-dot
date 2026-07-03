# src/physics.py

from __future__ import annotations

import math
from typing import List, Sequence

import numpy as np


def _lambertw_positive(z: float) -> float:
    z = float(z)

    if z == 0.0:
        return 0.0

    w = math.log1p(z) if z > 1.0 else z
    w = max(w, 1e-12)

    for _ in range(80):
        ew = math.exp(w)
        f = w * ew - z
        fp = ew * (w + 1.0)

        if abs(fp) < 1e-30:
            break

        w_new = w - f / fp

        if abs(w_new - w) < 1e-14:
            return float(w_new)

        w = max(w_new, 0.0)

    return float(w)


class PhysicalParameters:
    def __init__(
        self,
         mu_minus: float = -0.31,
        mu_plus: float = -0.80,
        lambda_tf: float = 5.0,
         epsilon_r: float = 5.6,
        qe: float = -1.0,
        k_coulomb: float = 1.43996,

        connectivity_radius: float | None = None,
        wire_forbidden_radius: float | None = None,
        charge_min_fraction: float = 0.0,
        charge_max_fraction: float = 1.0,
        input_disturbance_limit: float | None = None,
        enforce_input_population: bool = False,

        check_fixed_io_population: bool = False,
        check_configuration_stability: bool = True,

        relaxed_enumeration: bool = False,

        instability_check_inputs: bool = False,
        f10_check_input_inversions: bool = False,
        pressure_margin: float = 0.0,
        energy_tolerance: float = 1e-9,
        energy_bound_margin: float | None = None,

        io_instability_margin: float = 0.0,

        bit0_requires_positive_pressure: bool = False,
    ):
        self.mu_minus = float(mu_minus)
        self.mu_plus = float(mu_plus)
        self.lambda_tf = float(lambda_tf)
        self.epsilon_r = float(epsilon_r)
        self.qe = float(qe)
        self.k_coulomb = float(k_coulomb)

        self.connectivity_radius = connectivity_radius
        self.wire_forbidden_radius = wire_forbidden_radius
        self.charge_min_fraction = float(charge_min_fraction)
        self.charge_max_fraction = float(charge_max_fraction)

        self.input_disturbance_limit = input_disturbance_limit
        self.enforce_input_population = bool(enforce_input_population)
        self.check_fixed_io_population = bool(check_fixed_io_population)
        self.check_configuration_stability = bool(check_configuration_stability)
        self.relaxed_enumeration = bool(relaxed_enumeration)

        self.instability_check_inputs = bool(instability_check_inputs)
        self.f10_check_input_inversions = bool(f10_check_input_inversions)
        self.pressure_margin = float(pressure_margin)
        self.energy_tolerance = float(energy_tolerance)
        self.energy_bound_margin = energy_bound_margin
        self.io_instability_margin = float(io_instability_margin)

        self.bit0_requires_positive_pressure = bool(bit0_requires_positive_pressure)

        self.d_min = self._compute_d_min()

    def _compute_d_min(self) -> float:
        if self.lambda_tf <= 0 or abs(self.mu_plus) < 1e-15:
            return 0.0

        A = self.k_coulomb / self.epsilon_r
        z = A / (self.lambda_tf * abs(self.mu_plus))

        return self.lambda_tf * _lambertw_positive(z)

    def cache_key(self) -> tuple:
        return (
            round(self.mu_minus, 12),
            round(self.mu_plus, 12),
            round(self.lambda_tf, 12),
            round(self.epsilon_r, 12),
            round(self.qe, 12),
             round(self.k_coulomb, 12),
            self.check_fixed_io_population,
             self.check_configuration_stability,
            self.relaxed_enumeration,
            round(self.energy_tolerance, 15),
            round(self.io_instability_margin, 15),
        )


def euclidean(
    p1: Sequence[float] | np.ndarray,
    p2: Sequence[float] | np.ndarray,
) -> float:
    return float(
        np.linalg.norm(
            np.asarray(p1, dtype=float) - np.asarray(p2, dtype=float)
        )
    )


def get_potential(
    p1: Sequence[float] | np.ndarray,
    p2: Sequence[float] | np.ndarray,
    params: PhysicalParameters,
) -> float:
    d = euclidean(p1, p2)

    if d < 1e-12:
        return float("inf")

    return (
        params.k_coulomb
        / (params.epsilon_r * d)
        * math.exp(-d / params.lambda_tf)
    )


def get_local_potential(
    positions: List[np.ndarray],
    charges: List[int],
    i: int,
    params: PhysicalParameters,
) -> float:
    v = 0.0

    for j in range(len(positions)):
        if i == j:
            continue

        v += int(charges[j]) * get_potential(positions[i], positions[j], params)

    return float(v)


def get_total_energy(
    positions: List[np.ndarray],
    charges: List[int],
    params: PhysicalParameters,
) -> float:
    n = len(positions)
    e_interaction = 0.0

    for i in range(n):
        for j in range(i + 1, n):
            pot = get_potential(positions[i], positions[j], params)
            e_interaction += int(charges[i]) * int(charges[j]) * pot

    n_negative = sum(1 for q in charges if int(q) == -1)
    e_chemical = n_negative * params.mu_minus * abs(params.qe)

    return float(e_interaction + e_chemical)