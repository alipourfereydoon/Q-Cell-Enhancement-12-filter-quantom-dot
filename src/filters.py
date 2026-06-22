# src/filters.py

from __future__ import annotations

import math
from collections import deque
from itertools import product
from typing import Dict, List, Optional, Tuple

import numpy as np

from .data_structures import (
    BooleanFunction,
    Canvas,
    Layout,
    Skeleton,
    coord_key,
)
from .physics import (
    PhysicalParameters,
    euclidean,
    get_potential,
    get_total_energy,
)
from .stability import (
    interval_intersects_charge_state,
    is_metastable,
    is_population_stable_charge,
)


def _config_positions_charges(
    config: List[Tuple[np.ndarray, int]],
) -> Tuple[List[np.ndarray], List[int]]:
    return [p for p, _ in config], [int(c) for _, c in config]


def _fixed_config_for_io(
    skeleton: Skeleton,
    x: Tuple[int, ...],
    y: Tuple[int, ...],
) -> List[Tuple[np.ndarray, int]]:
    config = skeleton.io_charge_config(x, y)

    for w in skeleton.wire_sidbs:
        config.append((w.coords, 0))

    return config


def _potential_from_sources(
    target: np.ndarray,
    source_positions: List[np.ndarray],
    source_charges: List[int],
    params: PhysicalParameters,
    exclude_keys: Optional[set] = None,
) -> float:
    exclude_keys = exclude_keys or set()
    t_key = coord_key(target)

    v = 0.0

    for p, q in zip(source_positions, source_charges):
        p_key = coord_key(p)

        if p_key == t_key:
            continue

        if p_key in exclude_keys:
            continue

        v += int(q) * get_potential(target, p, params)

    return float(v)


def _canvas_free_indices(
    n_fixed: int,
    n_total: int,
    params: PhysicalParameters,
):
    if params.check_fixed_io_population:
        return None

    return range(n_fixed, n_total)


def _permute_tuple_old_to_new(
    values: Tuple[int, ...],
    old_to_new: Tuple[int, ...],
) -> Tuple[int, ...]:
    out = [0] * len(values)

    for old, new in enumerate(old_to_new):
        out[new] = values[old]

    return tuple(out)


def is_valid_partial_f1(
    layout: Layout,
    params: PhysicalParameters,
    **kwargs,
) -> bool:
    pts = layout.canvas_positions

    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if euclidean(pts[i], pts[j]) < params.d_min:
                return False

    return True


def F1_min_distance(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction | None = None,
    skeleton: Skeleton | None = None,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    return not is_valid_partial_f1(layout, params)


_SYMMETRY_CACHE: Dict[Tuple[int, int, str, Tuple], List[List[int]]] = {}


def _transform_point(
    p: np.ndarray,
    name: str,
    center: Tuple[float, float],
) -> np.ndarray:
    x, y, z = float(p[0]), float(p[1]), float(p[2])
    cx, cy = center

    if name == "identity":
        return np.array([x, y, z])

    if name == "reflect_x":
        return np.array([2 * cx - x, y, z])

    if name == "reflect_y":
        return np.array([x, 2 * cy - y, z])

    if name == "rotate_180":
        return np.array([2 * cx - x, 2 * cy - y, z])

    if name == "rotate_90":
        return np.array([cx - (y - cy), cy + (x - cx), z])

    if name == "rotate_270":
        return np.array([cx + (y - cy), cy - (x - cx), z])

    raise ValueError(f"Unknown transform {name}")


def _pin_mapping_for_transform(
    pins: List[Skeleton.Pin],
    name: str,
    center: Tuple[float, float],
) -> Optional[Tuple[int, ...]]:
    target = {}

    for pin in pins:
        target[(coord_key(pin.pos_a), coord_key(pin.pos_b))] = pin.pin_index

    mapping: List[int] = []

    for pin in pins:
        a_t = coord_key(_transform_point(pin.pos_a, name, center))
        b_t = coord_key(_transform_point(pin.pos_b, name, center))

        idx = target.get((a_t, b_t), None)

        if idx is None:
            return None

        mapping.append(idx)

    if len(set(mapping)) != len(mapping):
        return None

    return tuple(mapping)


def _wire_maps_to_itself(
    skeleton: Skeleton,
    name: str,
    center: Tuple[float, float],
) -> bool:
    if not skeleton.wire_sidbs:
        return True

    wire_set = {coord_key(w.coords) for w in skeleton.wire_sidbs}

    mapped = {
        coord_key(_transform_point(w.coords, name, center))
        for w in skeleton.wire_sidbs
    }

    return mapped == wire_set


def _function_invariant(
    func: BooleanFunction,
    input_perm_old_to_new: Tuple[int, ...],
    output_perm_old_to_new: Tuple[int, ...],
) -> bool:
    for x in func.all_inputs():
        x_t = _permute_tuple_old_to_new(x, input_perm_old_to_new)

        y = func.eval(x)
        y_t_expected = _permute_tuple_old_to_new(y, output_perm_old_to_new)

        if func.eval(x_t) != y_t_expected:
            return False

    return True


def _get_allowed_symmetry_perms(
    skeleton: Skeleton,
    canvas: Canvas,
    func: BooleanFunction,
) -> List[List[int]]:
    truth_key = tuple(func.eval(x) for x in func.all_inputs())
    cache_key = (id(skeleton), id(canvas), func.name, truth_key)

    if cache_key in _SYMMETRY_CACHE:
        return _SYMMETRY_CACHE[cache_key]

    xs = [p[0] for p in canvas.positions]
    ys = [p[1] for p in canvas.positions]

    center = (
        (min(xs) + max(xs)) / 2.0,
        (min(ys) + max(ys)) / 2.0,
    )

    candidate_names = [
        "identity",
        "reflect_x",
        "reflect_y",
        "rotate_180",
        "rotate_90",
        "rotate_270",
    ]

    canvas_map = canvas.position_to_index
    allowed: List[List[int]] = []

    for name in candidate_names:
        perm: List[int] = []
        ok = True

        for p in canvas.positions:
            p_t = _transform_point(p, name, center)
            idx = canvas_map.get(coord_key(p_t), None)

            if idx is None:
                ok = False
                break

            perm.append(idx)

        if not ok:
            continue

        in_perm = _pin_mapping_for_transform(skeleton.input_pins, name, center)
        out_perm = _pin_mapping_for_transform(skeleton.output_pins, name, center)

        if in_perm is None or out_perm is None:
            continue

        if not _wire_maps_to_itself(skeleton, name, center):
            continue

        if not _function_invariant(func, in_perm, out_perm):
            continue

        allowed.append(perm)

    if not allowed:
        allowed = [list(range(canvas.n_pos))]

    _SYMMETRY_CACHE[cache_key] = allowed

    return allowed


def _layout_canvas_indices(
    layout: Layout,
    canvas: Optional[Canvas],
) -> Optional[Tuple[int, ...]]:
    if all(i is not None for i in layout.canvas_indices):
        return tuple(sorted(int(i) for i in layout.canvas_indices if i is not None))

    if canvas is None:
        return None

    indices = []

    for p in layout.canvas_positions:
        idx = canvas.index_of(p)

        if idx is None:
            return None

        indices.append(idx)

    return tuple(sorted(indices))


def F2_symmetry(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    if canvas is None:
        return False

    current = _layout_canvas_indices(layout, canvas)

    if current is None:
        return False

    perms = _get_allowed_symmetry_perms(skeleton, canvas, func)

    orbit = []

    for perm in perms:
        mapped = tuple(sorted(perm[i] for i in current))
        orbit.append(mapped)

    canonical = min(orbit)

    return current != canonical


def _point_segment_distance(
    p: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
) -> float:
    ab = b - a
    denom = float(np.dot(ab, ab))

    if denom < 1e-18:
        return euclidean(p, a)

    t = float(np.dot(p - a, ab) / denom)
    t = max(0.0, min(1.0, t))

    nearest = a + t * ab

    return euclidean(p, nearest)


def F3_wire_interference(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction | None = None,
    skeleton: Skeleton | None = None,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    if skeleton is None or not skeleton.wire_sidbs:
        return False

    r_forbidden = params.wire_forbidden_radius

    if r_forbidden is None:
        r_forbidden = max(params.d_min, 0.5 * params.lambda_tf)

    wire_pts = [w.coords for w in skeleton.wire_sidbs]

    for c in layout.canvas_positions:
        for w in wire_pts:
            if euclidean(c, w) < r_forbidden:
                return True

        for a, b in zip(wire_pts[:-1], wire_pts[1:]):
            if _point_segment_distance(c, a, b) < r_forbidden:
                return True

    return False


def F4_positive_charge(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction | None = None,
    skeleton: Skeleton | None = None,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    """
    F4: Positive charge pruning.

    Return True  => discard layout
    Return False => keep layout

    The optional parameter params.positive_charge_margin makes the
    filter stricter:

        activation = mu_plus + qe * v_local

    Original condition:
        activation > 0

    Margin condition:
        activation + margin > 0
        equivalently activation > -margin
    """
    margin = float(getattr(params, "positive_charge_margin", 0.0))

    positions = layout.all_positions

    for i in range(len(positions)):
        v_local = 0.0

        for j in range(len(positions)):
            if i == j:
                continue

            # Worst-case assumption: all other SiDBs are negatively charged.
            v_local += -1 * get_potential(positions[i], positions[j], params)

        activation = params.mu_plus + params.qe * v_local

        if activation + margin > 0:
            return True

    return False


def _max_independent_canvas_capacity(
    canvas_positions: List[np.ndarray],
    conflict_radius: float,
) -> int:
    """
    Maximum number of canvas SiDBs that can be simultaneously negative
    if pairs closer than conflict_radius are treated as charge-count conflicts.

    This is exact for small d by brute-force subset enumeration.
    In your experiments d = 4, so this is very cheap.
    """
    d = len(canvas_positions)

    if d == 0:
        return 0

    conflict = [[False for _ in range(d)] for _ in range(d)]

    for i in range(d):
        for j in range(i + 1, d):
            if euclidean(canvas_positions[i], canvas_positions[j]) < conflict_radius:
                conflict[i][j] = True
                conflict[j][i] = True

    best = 0

    for mask in range(1 << d):
        ok = True
        count = 0

        for i in range(d):
            if mask & (1 << i):
                count += 1

        if count <= best:
            continue

        for i in range(d):
            if not (mask & (1 << i)):
                continue

            for j in range(i + 1, d):
                if not (mask & (1 << j)):
                    continue

                if conflict[i][j]:
                    ok = False
                    break

            if not ok:
                break

        if ok:
            best = count

    return best


def F5_charge_count_bound(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    """
    F5: Charge-count bound pruning.

    Return True  => discard layout
    Return False => keep layout

    Original behavior:
        req_max = required_skeleton_negative_count + number_of_canvas_sites

    Improved layout-sensitive behavior:
        If params.charge_count_conflict_radius is set, nearby canvas SiDBs
        are treated as mutually conflicting for simultaneous negative charge.
        Then req_max uses the maximum independent-set capacity of the selected
        canvas sites.

    This makes F5 capable of pruning some layouts without becoming an
    all-or-nothing filter.
    """
    n_total = len(layout.all_positions)

    adm_min = math.ceil(params.charge_min_fraction * n_total)
    adm_max = math.floor(params.charge_max_fraction * n_total)

    adm_min = max(0, adm_min)
    adm_max = min(n_total, adm_max)

    conflict_radius = getattr(params, "charge_count_conflict_radius", None)

    if conflict_radius is None or float(conflict_radius) <= 0.0:
        max_canvas_negative_capacity = layout.n_canvas
    else:
        max_canvas_negative_capacity = _max_independent_canvas_capacity(
            layout.canvas_positions,
            float(conflict_radius),
        )

    for x in func.all_inputs():
        y = func.eval(x)

        io_config = _fixed_config_for_io(skeleton, x, y)

        n_req_skeleton = sum(
            1 for _, q in io_config
            if int(q) == -1
        )

        req_min = n_req_skeleton
        req_max = n_req_skeleton + max_canvas_negative_capacity

        if req_max < adm_min or req_min > adm_max:
            return True

    return False


def F6_input_pin_disturbance(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    if params.input_disturbance_limit is None:
        limit = abs(
            (-params.mu_minus / params.qe)
            - (-params.mu_plus / params.qe)
        )
    else:
        limit = float(params.input_disturbance_limit)

    for x in func.all_inputs():
        y = func.eval(x)

        full_skel_config = _fixed_config_for_io(skeleton, x, y)
        skel_pos, skel_chg = _config_positions_charges(full_skel_config)

        input_config = skeleton.input_charge_config(x)

        for site_pos, required_q in input_config:
            canvas_worst = sum(
                -get_potential(site_pos, c, params)
                for c in layout.canvas_positions
            )

            if params.enforce_input_population:
                base_v = _potential_from_sources(
                    site_pos,
                    skel_pos,
                    skel_chg,
                    params,
                )

                disturbed_v = base_v + canvas_worst

                if not is_population_stable_charge(
                    required_q,
                    disturbed_v,
                    params,
                ):
                    return True

            else:
                if abs(canvas_worst) > limit:
                    return True

    return False


def F7_path_connectivity(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction | None = None,
    skeleton: Skeleton | None = None,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    """
    F7: Electrostatic path connectivity pruning.

    Return True  => discard layout
    Return False => keep layout

    This stricter version requires every input pin to be connected
    to the output region through the effective-radius connectivity graph.
    """
    if skeleton is None:
        return False

    positions = layout.all_positions
    n = len(positions)

    if n == 0:
        return True

    r_eff = params.connectivity_radius
    if r_eff is None:
        r_eff = 3.0 * params.lambda_tf

    output_keys = {coord_key(p) for p in skeleton.output_positions()}

    output_indices = {
        i for i, p in enumerate(positions)
        if coord_key(p) in output_keys
    }

    if not output_indices:
        return True

    adj = [[] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            if euclidean(positions[i], positions[j]) <= r_eff:
                adj[i].append(j)
                adj[j].append(i)

    def reaches_output(source_indices):
        if not source_indices:
            return False

        visited = set(source_indices)
        q = deque(source_indices)

        while q:
            i = q.popleft()

            if i in output_indices:
                return True

            for j in adj[i]:
                if j not in visited:
                    visited.add(j)
                    q.append(j)

        return False

    # Every input pin must be connected to the output region.
    for pin in skeleton.input_pins:
        pin_keys = {coord_key(pin.pos_a), coord_key(pin.pos_b)}

        source_indices = [
            i for i, p in enumerate(positions)
            if coord_key(p) in pin_keys
        ]

        if not reaches_output(source_indices):
            return True

    return False

def F8_output_potential_bound(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    for x in func.all_inputs():
        y = func.eval(x)

        skel_config = _fixed_config_for_io(skeleton, x, y)
        skel_pos, skel_chg = _config_positions_charges(skel_config)

        output_config = skeleton.output_charge_config(y)

        for site_pos, required_q in output_config:
            base_v = _potential_from_sources(
                site_pos,
                skel_pos,
                skel_chg,
                params,
            )

            canvas_min = sum(
                -get_potential(site_pos, c, params)
                for c in layout.canvas_positions
            )

            canvas_max = 0.0

            v_min = base_v + canvas_min
            v_max = base_v + canvas_max

            if not interval_intersects_charge_state(
                v_min,
                v_max,
                required_q,
                params,
            ):
                return True

    return False


def F9_electrostatic_pressure(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    margin = params.pressure_margin

    for x in func.all_inputs():
        y = func.eval(x)

        skel_config = _fixed_config_for_io(skeleton, x, y)
        skel_pos, skel_chg = _config_positions_charges(skel_config)

        for out_idx, pin in enumerate(skeleton.output_pins):
            required_bit = int(y[out_idx])

            a = pin.pos_a
            b = pin.pos_b

            exclude = {coord_key(a), coord_key(b)}

            v_a = _potential_from_sources(
                a,
                skel_pos,
                skel_chg,
                params,
                exclude_keys=exclude,
            )

            v_b = _potential_from_sources(
                b,
                skel_pos,
                skel_chg,
                params,
                exclude_keys=exclude,
            )

            delta_base = v_a - v_b

            d_min = delta_base
            d_max = delta_base

            for c in layout.canvas_positions:
                delta_neg = (
                    -get_potential(a, c, params)
                    - (-get_potential(b, c, params))
                )

                d_min += min(0.0, delta_neg)
                d_max += max(0.0, delta_neg)

            if params.bit0_requires_positive_pressure:
                if required_bit == 0:
                    if d_max <= margin:
                        return True
                else:
                    if d_min >= -margin:
                        return True
            else:
                if required_bit == 0:
                    if d_min >= -margin:
                        return True
                else:
                    if d_max <= margin:
                        return True

    return False


def _energy_with_neutral_canvas(
    layout: Layout,
    fixed_config: List[Tuple[np.ndarray, int]],
    params: PhysicalParameters,
) -> float:
    pos, chg = _config_positions_charges(fixed_config)

    positions = pos + layout.canvas_positions
    charges = chg + [0] * layout.n_canvas

    return get_total_energy(positions, charges, params)


def _relaxed_min_energy_for_io(
    layout: Layout,
    fixed_config: List[Tuple[np.ndarray, int]],
    params: PhysicalParameters,
) -> float:
    """
    Layout-sensitive relaxed energy.

    Enumerates canvas charge states {-1, 0}^d and returns the minimum
    total energy without metastability / hop checks.

    This is cheaper than F11/F12 strict physical feasibility because it
    only evaluates energy values.
    """
    skel_pos, skel_chg = _config_positions_charges(fixed_config)

    positions = skel_pos + layout.canvas_positions

    best = float("inf")

    for canvas_charges in product([-1, 0], repeat=layout.n_canvas):
        charges = skel_chg + list(canvas_charges)
        e = get_total_energy(positions, charges, params)

        if e < best:
            best = e

    return float(best)


def F10_energy_lower_bound(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    """
    F10: Layout-sensitive relaxed energy guard.

    Return True  => discard layout
    Return False => keep layout

    This version compares the relaxed minimum energy of the correct
    output assignment against competing incorrect output assignments.

    It is intentionally a coarse pre-F12 guard:
        - F10 uses params.energy_bound_margin
        - F12 uses params.io_instability_margin

    Recommended:
        energy_bound_margin should usually be larger than io_instability_margin,
        so F10 removes only strong energetic failures and F12 remains the final
        finer energetic check.
    """
    tol = params.energy_tolerance

    if params.energy_bound_margin is None:
        # Conservative default. If this is too large, F10 may prune nothing.
        margin = abs(params.mu_minus) * max(1, layout.n_canvas)
    else:
        margin = float(params.energy_bound_margin)

    threshold = max(tol, margin)

    for x in func.all_inputs():
        y_correct = func.eval(x)

        e_correct = _relaxed_min_energy_for_io(
            layout,
            _fixed_config_for_io(skeleton, x, y_correct),
            params,
        )

        if params.f10_check_input_inversions:
            input_patterns = list(func.all_inputs())
        else:
            input_patterns = [x]

        for x_alt in input_patterns:
            for y_alt in func.all_outputs():
                if x_alt == x and y_alt == y_correct:
                    continue

                e_alt = _relaxed_min_energy_for_io(
                    layout,
                    _fixed_config_for_io(skeleton, x_alt, y_alt),
                    params,
                )

                # If an incorrect assignment is lower by more than margin,
                # reject this layout.
                if e_alt < e_correct - threshold:
                    return True

    return False



def ground_state_energy_for_io(
    layout: Layout,
    input_pattern: Tuple[int, ...],
    output_pattern: Tuple[int, ...],
    skeleton: Skeleton,
    params: PhysicalParameters,
) -> float:
    cache_key = (
        "ground_state_energy_for_io",
        tuple(input_pattern),
        tuple(output_pattern),
        params.cache_key(),
    )

    if cache_key in layout.cache:
        return layout.cache[cache_key]

    fixed_config = _fixed_config_for_io(
        skeleton,
        input_pattern,
        output_pattern,
    )

    skel_pos, skel_chg = _config_positions_charges(fixed_config)

    positions = skel_pos + layout.canvas_positions
    n_fixed = len(skel_pos)

    free_indices = _canvas_free_indices(
        n_fixed,
        len(positions),
        params,
    )

    best_metastable_e = float("inf")
    best_any_e = float("inf")

    for canvas_charges in product([-1, 0], repeat=layout.n_canvas):
        charges = skel_chg + list(canvas_charges)

        e = get_total_energy(positions, charges, params)

        if e < best_any_e:
            best_any_e = e

        if is_metastable(
            positions,
            charges,
            params,
            free_indices=free_indices,
            check_hops=params.check_configuration_stability,
        ):
            if e < best_metastable_e:
                best_metastable_e = e

    if math.isfinite(best_metastable_e):
        result = best_metastable_e
    elif params.relaxed_enumeration:
        result = best_any_e
    else:
        result = float("inf")

    layout.cache[cache_key] = result
    return result


def F11_physical_infeasibility(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    """
    F11: Physical infeasibility pruning.

    Return True  => discard layout
    Return False => keep layout

    Default strict meaning:
        For every input x, at least one metastable canvas charge assignment
        must support the correct I/O state.

    Optional robustness extension:
        params.f11_min_support_states = k

    If k > 1, the layout must have at least k metastable supporting
    canvas states for every input pattern.
    """
    min_support = int(getattr(params, "f11_min_support_states", 1))
    min_support = max(1, min_support)

    for x in func.all_inputs():
        y = func.eval(x)

        fixed_config = _fixed_config_for_io(
            skeleton,
            x,
            y,
        )

        skel_pos, skel_chg = _config_positions_charges(fixed_config)

        positions = skel_pos + layout.canvas_positions

        n_fixed = len(skel_pos)

        free_indices = _canvas_free_indices(
            n_fixed,
            len(positions),
            params,
        )

        support_count = 0

        for canvas_charges in product([-1, 0], repeat=layout.n_canvas):
            charges = skel_chg + list(canvas_charges)

            ok = is_metastable(
                positions,
                charges,
                params,
                free_indices=free_indices,
                check_hops=params.check_configuration_stability,
            )

            if ok:
                support_count += 1

                if support_count >= min_support:
                    break

        if support_count < min_support:
            return True

    return False


def F12_io_signal_instability(
    layout: Layout,
    params: PhysicalParameters,
    func: BooleanFunction,
    skeleton: Skeleton,
    canvas: Canvas | None = None,
    **kwargs,
) -> bool:
    tol = max(params.energy_tolerance, params.io_instability_margin)

    for x in func.all_inputs():
        y_correct = func.eval(x)

        e_correct = ground_state_energy_for_io(
            layout,
            x,
            y_correct,
            skeleton,
            params,
        )

        if not math.isfinite(e_correct):
            return True

        if params.instability_check_inputs:
            input_patterns = list(func.all_inputs())
        else:
            input_patterns = [x]

        for x_alt in input_patterns:
            for y_alt in func.all_outputs():
                if x_alt == x and y_alt == y_correct:
                    continue

                e_alt = ground_state_energy_for_io(
                    layout,
                    x_alt,
                    y_alt,
                    skeleton,
                    params,
                )

                if math.isfinite(e_alt) and e_alt < e_correct - tol:
                    return True

    return False


ALL_QC12_FILTERS = [
    F1_min_distance,
    F2_symmetry,
    F3_wire_interference,
    F4_positive_charge,
    F5_charge_count_bound,
    F6_input_pin_disturbance,
    F7_path_connectivity,
    F8_output_potential_bound,
    F9_electrostatic_pressure,
    F10_energy_lower_bound,
    F11_physical_infeasibility,
    F12_io_signal_instability,
]