from __future__ import annotations
from typing import Iterable, List, Optional, Tuple
import numpy as np

from .physics import (
    PhysicalParameters,
    get_local_potential,
    get_total_energy,
)

def transition_threshold(mu: float, params: PhysicalParameters) -> float:
    return -float(mu) / params.qe

def negative_threshold(params: PhysicalParameters) -> float:
    return transition_threshold(params.mu_minus, params)

def positive_threshold(params: PhysicalParameters) -> float:
    return transition_threshold(params.mu_plus, params)

def neutral_window(params: PhysicalParameters) -> Tuple[float, float]:
    t1 = negative_threshold(params)
    t2 = positive_threshold(params)
    return min(t1, t2), max(t1, t2)

def is_population_stable_charge(
    charge: int,
    v_local: float,
    params: PhysicalParameters,
    tol: float = 1e-12,
) -> bool:
    charge = int(charge)

    neg_condition = params.mu_minus + params.qe * v_local < -tol
    pos_condition = params.mu_plus + params.qe * v_local > tol
    if charge == -1:
        return bool(neg_condition)

    if charge == 0:
        return bool((not neg_condition) and (not pos_condition))

    if charge == 1:
        return bool(pos_condition)

    return False


def charge_stability_window(
    charge: int,
    params: PhysicalParameters,
) -> Tuple[float, float]:
    charge = int(charge)

    t_minus = negative_threshold(params)
    t_plus = positive_threshold(params)
    lo = min(t_minus, t_plus)
    hi = max(t_minus, t_plus)

    if charge == -1:
        if params.qe < 0:
            return t_minus, float("inf")
        return float("-inf"), t_minus

    if charge == 0:
        return lo, hi

    if charge == 1:
        if params.qe < 0:
            return float("-inf"), t_plus
        return t_plus, float("inf")

    return float("inf"), float("-inf")


def interval_intersects_charge_state(
    v_min: float,
     v_max: float,
    charge: int,
    params: PhysicalParameters,
) -> bool:
    w_min, w_max = charge_stability_window(charge, params)
    return not (v_max < w_min or v_min > w_max)


def _local_potentials(
    positions: List[np.ndarray],
     charges: List[int],
    params: PhysicalParameters,
) -> List[float]:
    return [
        get_local_potential(positions, charges, i, params)
        for i in range(len(positions))
    ]


def is_metastable(
    positions: List[np.ndarray],
    charges: List[int],
     params: PhysicalParameters,
    free_indices: Optional[Iterable[int]] = None,
    check_hops: bool = True,
) -> bool:
    if len(positions) != len(charges):
        raise ValueError("positions and charges must have equal length.")

    if free_indices is None:
        free = list(range(len(positions)))
    else:
        free = sorted(set(int(i) for i in free_indices))

    local_vs = _local_potentials(positions, charges, params)

    for i in free:
        q = int(charges[i])

        if q not in (-1, 0, 1):
            return False

        if not is_population_stable_charge(q, local_vs[i], params):
            return False

    if check_hops:
        base_e = get_total_energy(positions, charges, params)
        tol = params.energy_tolerance

        for i in free:
            if int(charges[i]) != -1:
                continue

            for j in free:
                if i == j:
                    continue

                if int(charges[j]) != 0:
                    continue

                new_charges = list(charges)
                new_charges[i] = 0
                new_charges[j] = -1

                new_e = get_total_energy(positions, new_charges, params)
                if new_e < base_e - tol:
                    return False

    return True