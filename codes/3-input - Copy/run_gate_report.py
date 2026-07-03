

# run_gate_report.py ------------------> ****>>>>OOOOOO

from __future__ import annotations
import argparse
import math
import multiprocessing as mp
import os
import random
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from src.data_structures import Layout
from src.physics import PhysicalParameters, get_potential
from src.gates import (
    get_3input_gate,
    get_all_3input_gate_names,
    normalize_gate_name,
)
from src.paper_benchmarks import (
    paper_like_skeleton_3in_1out_25,
    paper_like_canvas_143,
)
from src.filters import (
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
)
from src.reporting import (
    write_csv,
    write_json,
    write_markdown,
    markdown_table,
)


QC12_FILTERS = [
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
]


_G: Dict[str, Any] = {}


def _override(default_value, override_value):
    return default_value if override_value is None else override_value

def make_params(
    profile: str,
    io_margin_override: Optional[float],
    pressure_margin_override: Optional[float],
    wire_radius_override: Optional[float],
    input_disturbance_override: Optional[float],
    connectivity_radius_override: Optional[float] = None,
) -> PhysicalParameters:
    profile = str(profile).strip().lower()

    if profile == "safe":
        return PhysicalParameters(
            mu_minus=-0.31,
            mu_plus=-0.80,
            lambda_tf=5.0,
             epsilon_r=5.6,
            check_fixed_io_population=False,
            check_configuration_stability=False,
            relaxed_enumeration=True,
            instability_check_inputs=False,
            f10_check_input_inversions=False,
             charge_min_fraction=0.0,
            charge_max_fraction=1.0,
            bit0_requires_positive_pressure=False,
             wire_forbidden_radius=_override(0.35, wire_radius_override),
            connectivity_radius=connectivity_radius_override,
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=None,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=input_disturbance_override,
        )

    if profile == "balanced":
        return PhysicalParameters(
            mu_minus=-0.31,
            mu_plus=-0.80,
            lambda_tf=5.0,
             epsilon_r=5.6,
            check_fixed_io_population=False,
            check_configuration_stability=False,
            relaxed_enumeration=True,
             instability_check_inputs=False,
            f10_check_input_inversions=False,
            charge_min_fraction=0.0,
            charge_max_fraction=1.0,
            bit0_requires_positive_pressure=False,
             wire_forbidden_radius=_override(0.40, wire_radius_override),
            connectivity_radius=connectivity_radius_override,
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=None,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=input_disturbance_override,
        )

    if profile == "strict":
        return PhysicalParameters(
            mu_minus=-0.31,
            mu_plus=-0.80,
            lambda_tf=5.0,
            epsilon_r=5.6,
             check_fixed_io_population=False,
            check_configuration_stability=False,
            relaxed_enumeration=True,
            instability_check_inputs=False,
             f10_check_input_inversions=False,
            charge_min_fraction=0.0,
            charge_max_fraction=1.0,
            bit0_requires_positive_pressure=False,
             wire_forbidden_radius=_override(0.45, wire_radius_override),
            connectivity_radius=_override(2.5 * 5.0, connectivity_radius_override),
             pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=None,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=_override(0.45, input_disturbance_override),
        )

    raise ValueError("Unknown strict profile. Use: safe, balanced, strict")

def fixed_charges_ordered(skeleton, x: Tuple[int, ...], y: Tuple[int, ...]) -> List[int]:
    charges = []

    for i, pin in enumerate(skeleton.input_pins):
        charges.extend([q for _, q in pin.charges_for_bit(x[i])])

    for i, pin in enumerate(skeleton.output_pins):
        charges.extend([q for _, q in pin.charges_for_bit(y[i])])

    for _ in skeleton.wire_sidbs:
        charges.append(0)

    return charges


def precompute_potential_matrix(skeleton, canvas, params):
    positions = skeleton.all_positions() + canvas.positions
    n = len(positions)

    P = np.zeros((n, n), dtype=float)

    for i in range(n):
        for j in range(i + 1, n):
            v = get_potential(positions[i], positions[j], params)
            P[i, j] = v
            P[j, i] = v

    return P

def build_fixed_data(skeleton, func, params, P):
    n_s = len(skeleton.all_sidbs)
    data = {}

    for x in func.all_inputs():
        for y in func.all_outputs():
            charges = fixed_charges_ordered(skeleton, x, y)

            e_fixed_pair = 0.0

            for i in range(n_s):
                for j in range(i + 1, n_s):
                    e_fixed_pair += charges[i] * charges[j] * P[i, j]

            n_neg = sum(1 for q in charges if q == -1)
            e_fixed = e_fixed_pair + n_neg * params.mu_minus * abs(params.qe)

            data[(tuple(x), tuple(y))] = {
                "charges": charges,
                "e_fixed": e_fixed,
            }

    return data

def _init_worker(skeleton, canvas, params, func):
    _G["skeleton"] = skeleton
    _G["canvas"] = canvas
    _G["params"] = params
    _G["func"] = func

    P = precompute_potential_matrix(skeleton, canvas, params)
    _G["P"] = P
    _G["fixed_data"] = build_fixed_data(skeleton, func, params, P)
    _G["n_skel"] = len(skeleton.all_sidbs)


def make_layout(combo: Tuple[int, ...]) -> Layout:
    canvas = _G["canvas"]
    skeleton = _G["skeleton"]

    positions = [canvas.positions[i] for i in combo]

    return Layout(
        skeleton=skeleton,
        canvas_positions=positions,
        canvas_indices=combo,
    )

def min_relaxed_energy(combo: Tuple[int, ...], x: Tuple[int, ...], y: Tuple[int, ...]) -> float:
    params = _G["params"]
    P = _G["P"]
    n_s = _G["n_skel"]
    fixed_data = _G["fixed_data"][(tuple(x), tuple(y))]

    fixed_charges = fixed_data["charges"]
    e_fixed = fixed_data["e_fixed"]
    canvas_global = [n_s + i for i in combo]
    d = len(canvas_global)

    linear = []

    for cidx in canvas_global:
        contribution = params.mu_minus * abs(params.qe)

        for i, q in enumerate(fixed_charges):
            contribution += q * (-1) * P[i, cidx]

        linear.append(contribution)

    pair_cc = np.zeros((d, d), dtype=float)

    for i in range(d):
        for j in range(i + 1, d):
            pair_cc[i, j] = P[canvas_global[i], canvas_global[j]]

    best = float("inf")

    for mask in range(1 << d):
        e = e_fixed
        active = []

        for i in range(d):
            if mask & (1 << i):
                e += linear[i]
                active.append(i)

        for a_i in range(len(active)):
            for b_i in range(a_i + 1, len(active)):
                e += pair_cc[active[a_i], active[b_i]]

        if e < best:
            best = e

    return best


def fast_f12_relaxed(combo: Tuple[int, ...]) -> bool:
    params = _G["params"]
    func = _G["func"]

    tol = max(params.energy_tolerance, params.io_instability_margin)

    for x in func.all_inputs():
        y_correct = func.eval(x)
        e_correct = min_relaxed_energy(combo, tuple(x), tuple(y_correct))

        for y_alt in func.all_outputs():
            y_alt = tuple(y_alt)

            if y_alt == tuple(y_correct):
                continue

            e_alt = min_relaxed_energy(combo, tuple(x), y_alt)

            if e_alt < e_correct - tol:
                return True

    return False


def fast_energy_margin(combo: Tuple[int, ...]) -> float:
    func = _G["func"]
    min_margin = float("inf")

    for x in func.all_inputs():
        y_correct = tuple(func.eval(x))
        e_correct = min_relaxed_energy(combo, tuple(x), y_correct)

        best_alt = float("inf")

        for y_alt in func.all_outputs():
            y_alt = tuple(y_alt)

            if y_alt == y_correct:
                continue

            e_alt = min_relaxed_energy(combo, tuple(x), y_alt)

            if e_alt < best_alt:
                best_alt = e_alt

        margin = best_alt - e_correct

        if margin < min_margin:
            min_margin = margin

    return float(min_margin)


def run_filter_sequence_for_qc12(layout: Layout) -> Tuple[List[int], bool]:
    params = _G["params"]
    func = _G["func"]
    skeleton = _G["skeleton"]
    canvas = _G["canvas"]

    after = [0] * 12

    for i, f in enumerate(QC12_FILTERS):
        discard = f(
            layout=layout,
            params=params,
            func=func,
            skeleton=skeleton,
            canvas=canvas,
        )

        if discard:
            return after, False

        after[i] = 1

    f11_mode = getattr(params, "f11_mode", "counted")

    if f11_mode == "counted":
        after[10] = 1
    else:
        discard_f11 = F11_physical_infeasibility(
            layout=layout,
            params=params,
            func=func,
            skeleton=skeleton,
            canvas=canvas,
        )

        if discard_f11:
            return after, False

        after[10] = 1

    discard_f12 = fast_f12_relaxed(tuple(layout.canvas_indices))

    if discard_f12:
        return after, False

    after[11] = 1

    return after, True
   

def run_filter_sequence_for_qc3(layout: Layout) -> Dict[str, int]:
    params = _G["params"]
    func = _G["func"]
    skeleton = _G["skeleton"]
    canvas = _G["canvas"]

    out = {
        "after_f4": 0,
        "after_f11": 0,
        "after_f12": 0,
    }

    discard_f4 = F4_positive_charge(
        layout=layout,
        params=params,
        func=func,
        skeleton=skeleton,
        canvas=canvas,
    )

    if discard_f4:
        return out

    out["after_f4"] = 1
    out["after_f11"] = 1

    discard_f12 = fast_f12_relaxed(tuple(layout.canvas_indices))

    if discard_f12:
        return out

    out["after_f12"] = 1

    return out


def worker_process_chunk(chunk: List[Tuple[int, ...]]) -> Dict[str, Any]:
    qc12_after = [0] * 12
    qc12_passed = []

    qc3_after_f4 = 0
    qc3_after_f11 = 0
    qc3_after_f12 = 0

    for combo in chunk:
        layout = make_layout(combo)

        after, passed = run_filter_sequence_for_qc12(layout)

        for i in range(12):
            qc12_after[i] += after[i]

        if passed:
            qc12_passed.append(combo)

        qc3 = run_filter_sequence_for_qc3(layout)

        qc3_after_f4 += qc3["after_f4"]
        qc3_after_f11 += qc3["after_f11"]
        qc3_after_f12 += qc3["after_f12"]

    return {
        "processed": len(chunk),
        "qc12_after": qc12_after,
         "qc12_passed": qc12_passed,
        "qc3_after_f4": qc3_after_f4,
         "qc3_after_f11": qc3_after_f11,
        "qc3_after_f12": qc3_after_f12,
    }


def random_combinations(n: int, d: int, count: int, seed: int):
    rng = random.Random(seed)
    seen = set()
    total_possible = math.comb(n, d)
    count = min(count, total_possible)

    while len(seen) < count:
        combo = tuple(sorted(rng.sample(range(n), d)))

        if combo in seen:
            continue

        seen.add(combo)
        yield combo


def chunked(iterable, chunk_size: int):
    batch = []

    for item in iterable:
        batch.append(item)

        if len(batch) >= chunk_size:
            yield batch
            batch = []

    if batch:
        yield batch


def merge(total: Dict[str, Any], part: Dict[str, Any]):
    total["processed"] += part["processed"]

    for i in range(12):
        total["qc12_after"][i] += part["qc12_after"][i]

    total["qc12_passed"].extend(part["qc12_passed"])

    total["qc3_after_f4"] += part["qc3_after_f4"]
    total["qc3_after_f11"] += part["qc3_after_f11"]
    total["qc3_after_f12"] += part["qc3_after_f12"]


def select_ranked_candidates(
    combos: List[Tuple[int, ...]],
    target: Optional[int],
    min_margin: Optional[float],
) -> Tuple[List[Tuple[int, ...]], List[Dict[str, Any]]]:
    scored = []

    for combo in combos:
        margin = fast_energy_margin(combo)
        scored.append((margin, combo))

    scored.sort(key=lambda t: (-t[0], t[1]))

    selected = []
    rows = []

    for margin, combo in scored:
        if min_margin is not None and margin < min_margin:
            continue

        if target is not None and target > 0 and len(selected) >= target:
            break

        selected.append(combo)

        rows.append({
            "rank": len(selected),
            "energy_margin": margin,
            "canvas_indices": " ".join(str(i) for i in combo),
        })

    return selected, rows


def compute_phase_rows(total: Dict[str, Any], elapsed: float, selection_enabled: bool):
    processed = total["processed"]
    a = total["qc12_after"]

    rows = []

    def row(name, filters, inp, out, runtime=""):
        retention = out / inp if inp else 0.0
        pruning = 1.0 - retention
        reduction = inp / out if out else float("inf")

        return {
            "Phase": name,
            "Filters": filters,
            "Input Layouts": inp,
             "Output Layouts": out,
            "Retention Ratio [%]": round(retention * 100.0, 4),
             "Pruning Ratio [%]": round(pruning * 100.0, 4),
            "Reduction Factor": "inf" if reduction == float("inf") else round(reduction, 4),
            "Runtime [s]": runtime,
        }

    rows.append(row("Phase 1", "F1-F4", processed, a[3]))
    rows.append(row("Phase 2", "F5-F10", a[3], a[9]))
    rows.append(row("Phase 3", "F11-F12", a[9], a[11]))

    if selection_enabled:
        rows.append(row("Post-F12 Selection", "Energy-margin ranking", a[11], total["selected_candidates"]))
        final_out = total["selected_candidates"]
        total_label = "F1-F12 + selection"
    else:
        final_out = a[11]
        total_label = "F1-F12"

    rows.append(row("Total", total_label, processed, final_out, round(elapsed, 4)))

    return rows


def compute_comparison_rows(total: Dict[str, Any], selection_enabled: bool):
    processed = total["processed"]
    a = total["qc12_after"]

    qc3_before = total["qc3_after_f12"]
    qc12_before = total["selected_candidates"] if selection_enabled else a[11]

    qc3_after_early = total["qc3_after_f4"]
    qc12_after_phase1 = a[3]

    qc12_before_enum = a[9]
    qc3_before_enum = qc3_after_early

    def improvement_fewer(old, new):
        if new == 0:
            return "inf"
        return f"{old / new:.2f}x fewer"

    return [
        {
            "Metric": "Number of pruning filters",
            "Original QC-3": 3,
            "QuickCell-12": 12,
            "Improvement": "4.0x more",
        },
        {
            "Metric": "Processed layouts",
            "Original QC-3": processed,
             "QuickCell-12": processed,
            "Improvement": "same",
        },
        {
            "Metric": "After early pruning / Phase 1",
             "Original QC-3": qc3_after_early,
            "QuickCell-12": qc12_after_phase1,
            "Improvement": improvement_fewer(qc3_after_early, qc12_after_phase1),
        },
        {
            "Metric": "Before expensive enumerative pruning",
            "Original QC-3": qc3_before_enum,
            "QuickCell-12": qc12_before_enum,
             "Improvement": improvement_fewer(qc3_before_enum, qc12_before_enum),
        },
        {
             "Metric": "Before final verification",
            "Original QC-3": qc3_before,
            "QuickCell-12": qc12_before,
            "Improvement": improvement_fewer(qc3_before, qc12_before),
        },
        {
            "Metric": "Candidate implementations",
             "Original QC-3": qc3_before,
            "QuickCell-12": qc12_before,
            "Improvement": improvement_fewer(qc3_before, qc12_before),
        },
        {
            "Metric": "Search-space reduction",
             "Original QC-3": round(processed / qc3_before, 4) if qc3_before else "inf",
            "QuickCell-12": round(processed / qc12_before, 4) if qc12_before else "inf",
             "Improvement": improvement_fewer(qc3_before, qc12_before),
        },
    ]


def compute_speedup_rows(total: Dict[str, Any], full_ld: int, elapsed: float, sim_time: float, selection_enabled: bool):
    processed = total["processed"]

    qc3_candidates = total["qc3_after_f12"]
    qc_candidates = total["selected_candidates"] if selection_enabled else total["qc12_after"][11]

    limited_sota = processed * 8 * sim_time
    full_sota = full_ld * 8 * sim_time

    return [
        {"Quantity": "Processed layouts", "Value": processed},
        {"Quantity": "Full search space |Ld|", "Value": full_ld},
        {"Quantity": "Input patterns for 3-input gate", "Value": 8},
        {"Quantity": "Assumed simulation time per layout/input [s]", "Value": sim_time},
        {"Quantity": "Estimated brute-force time for processed sample [s]", "Value": round(limited_sota, 4)},
        {"Quantity": "Estimated brute-force time for full |Ld| [s]", "Value": round(full_sota, 4)},
        {"Quantity": "QC-3 candidates before verification", "Value": qc3_candidates},
        {"Quantity": "QuickCell-12 candidates before verification", "Value": qc_candidates},
        {
            "Quantity": "QuickCell-12 candidate reduction over QC-3",
            "Value": f"{(qc3_candidates / qc_candidates):.4f}x" if qc_candidates else "inf",
        },
        {"Quantity": "Measured QuickCell-12 wall time [s]", "Value": round(elapsed, 4)},
    ]


def write_reports(
    gate,
    full_ld,
    total,
    elapsed,
    output_dir,
    sim_time,
    selection_enabled,
    selected_rows,
):
    os.makedirs(output_dir, exist_ok=True)

    a = total["qc12_after"]

    table_i = [{
        "Benchmark": gate,
        "|Ld|": full_ld,
        "Processed": total["processed"],
        "After F1": a[0],
        "After F2": a[1],
        "After F3": a[2],
        "After F4": a[3],
        "After F5": a[4],
        "After F6": a[5],
        "After F7": a[6],
        "After F8": a[7],
        "After F9": a[8],
        "After F10": a[9],
        "After F11": a[10],
        "After F12": a[11],
        "Selected Candidates": total["selected_candidates"] if selection_enabled else "",
        "Candidates": total["selected_candidates"] if selection_enabled else a[11],
        "Total Time [s]": round(elapsed, 4),
    }]

    table_ii = compute_phase_rows(total, elapsed, selection_enabled)
    table_iii = compute_comparison_rows(total, selection_enabled)
    speedup = compute_speedup_rows(total, full_ld, elapsed, sim_time, selection_enabled)
    write_csv(os.path.join(output_dir, "table_I_ablation.csv"), table_i, list(table_i[0].keys()))
    write_csv(os.path.join(output_dir, "table_II_phase_summary.csv"), table_ii, list(table_ii[0].keys()))
    write_csv(os.path.join(output_dir, "table_III_comparison.csv"), table_iii, list(table_iii[0].keys()))
    write_csv(os.path.join(output_dir, "speedup_calculation.csv"), speedup, list(speedup[0].keys()))

    if selected_rows:
        write_csv(
            os.path.join(output_dir, "selected_candidates.csv"),
            selected_rows,
            list(selected_rows[0].keys()),
        )

    write_json(
        os.path.join(output_dir, "report.json"),
        {
            "gate": gate,
            "full_ld": full_ld,
            "total": total,
            "elapsed": elapsed,
            "selection_enabled": selection_enabled,
             "table_I": table_i,
            "table_II": table_ii,
             "table_III": table_iii,
            "speedup": speedup,
            "selected_candidates": selected_rows,
        },
    )

    md = []

    md.append(f"# QuickCell-12 Limited-run Report: {gate}\n")
    md.append("## Table I — Ablation Results\n")
    md.append(markdown_table(list(table_i[0].keys()), [list(table_i[0].values())]))
    md.append("\n\n## Table II — Phase-wise Summary\n")
    md.append(markdown_table(list(table_ii[0].keys()), [list(r.values()) for r in table_ii]))
    md.append("\n\n## Table III — Original QC-3 vs QuickCell-12\n")
    md.append(markdown_table(list(table_iii[0].keys()), [list(r.values()) for r in table_iii]))
    md.append("\n\n## Numerical Speedup Calculation\n")
    md.append(markdown_table(list(speedup[0].keys()), [list(r.values()) for r in speedup]))
    md.append("\n\n**Note:** This is a limited-run / sampling-based evaluation.\n")

    write_markdown(os.path.join(output_dir, "report.md"), "\n".join(md))


def parse_gate_argument(gate_arg: str):
    gate_arg = gate_arg.strip()

    if gate_arg.upper() == "ALL":
        return get_all_3input_gate_names()

    return [normalize_gate_name(g) for g in gate_arg.split(",") if g.strip()]


def run_gate(
    gate,
    samples,
    workers,
    chunksize,
    seed,
    sim_time,
    strict_profile,
    io_margin,
    pressure_margin,
    connectivity_radius,
    d_min,
     positive_charge_margin,
    charge_min_fraction,
    charge_max_fraction,
    charge_count_conflict_radius,
    input_disturbance,
     energy_margin,
    f11_mode,
     f11_min_support_states,
    selection_target,
    selection_min_margin,
):

    gate = normalize_gate_name(gate)

    func = get_3input_gate(gate)
    skeleton = paper_like_skeleton_3in_1out_25()
    canvas = paper_like_canvas_143()

    params = make_params(
        profile=strict_profile,
        io_margin_override=io_margin,
        pressure_margin_override=pressure_margin,
        wire_radius_override=None,
        input_disturbance_override=input_disturbance,
        connectivity_radius_override=connectivity_radius,
    )
    
    params.f11_mode = f11_mode
    if f11_mode == "counted":
        # Old behevior: F11 is only counted as surveived
        params.relaxed_enumeration = True
        params.check_configuration_stability = False

    elif f11_mode == "strict-pop":
        # Real F11 and but only population stability is checked
        # Less destructivee than strict-hop 
        params.relaxed_enumeration = False
        params.check_configuration_stability = False
        params.check_fixed_io_population = False

    elif f11_mode == "strict-hop":
        # Real F11 with populations stabileity and single-electron hop stability
        # This can be very strict
        params.relaxed_enumeration = False
        params.check_configuration_stability = True
        params.check_fixed_io_population = False

    if d_min is not None:
        params.d_min = float(d_min)
    params.positive_charge_margin = float(positive_charge_margin or 0.0)
    if charge_min_fraction is not None:
        params.charge_min_fraction = float(charge_min_fraction)
    if charge_max_fraction is not None:
        params.charge_max_fraction = float(charge_max_fraction)
    params.charge_count_conflict_radius = charge_count_conflict_radius
    params.energy_bound_margin = energy_margin
    params.f11_min_support_states = int(f11_min_support_states)

    full_ld = math.comb(canvas.n_pos, 4)

    selection_enabled = (
        selection_target is not None and selection_target > 0
    ) or (
        selection_min_margin is not None
    )

    print("=" * 80)
    print(f"Gate: {gate}")
    print(f"|C| = {canvas.n_pos}, d = 4, |Ld| = {full_ld:,}")
    print(f"Processed samples = {samples:,}")
    print(f"Workers = {workers}, chunksize = {chunksize}")
    print(f"Strict profile = {strict_profile}")
    print(f"F12 I/O margin = {params.io_instability_margin}")
    print(f"F9 pressure margin = {params.pressure_margin}")
    print(f"F7 connectivity radius = {params.connectivity_radius}")
    print(f"F1 minimum distance d_min = {params.d_min}")
    print(f"F4 positive charge margin = {params.positive_charge_margin}")
    print(f"F5 charge fraction = [{params.charge_min_fraction}, {params.charge_max_fraction}]")
    print(f"F5 charge-count conflict radius = {params.charge_count_conflict_radius}")
    print(f"F6 input disturbance limit = {params.input_disturbance_limit}")
    print(f"F10 energy margin = {params.energy_bound_margin}")
    print(f"F11 mode = {params.f11_mode}")
    print(f"F11 relaxed enumeration = {params.relaxed_enumeration}")

    print(f"F11 mode = {params.f11_mode}")
    print(f"F11 relaxed enumeration = {params.relaxed_enumeration}")
    print(f"F11 hop stability check = {params.check_configuration_stability}")
    print(f"F11 check fixed I/O population = {params.check_fixed_io_population}")
    print(f"F11 min support states = {params.f11_min_support_states}")


    print(f"F11 hop stability check = {params.check_configuration_stability}")
    print(f"Post-F12 selection enabled = {selection_enabled}")
    print(f"Selection target = {selection_target}")
    print(f"Selection min margin = {selection_min_margin}")
    print("=" * 80)

    total = {
        "processed": 0,
        "qc12_after": [0] * 12,
        "qc12_passed": [],
        "qc3_after_f4": 0,
        "qc3_after_f11": 0,
        "qc3_after_f12": 0,
        "selected_candidates": 0,
    }

    combos = random_combinations(canvas.n_pos, 4, samples, seed)
    chunks = list(chunked(combos, chunksize))

    start = time.time()

    if workers <= 1:
        _init_worker(skeleton, canvas, params, func)

        for chunk in chunks:
            part = worker_process_chunk(chunk)
            merge(total, part)
    else:
        ctx = mp.get_context("spawn")

        with ctx.Pool(
            processes=workers,
            initializer=_init_worker,
            initargs=(skeleton, canvas, params, func),
        ) as pool:
            for idx, part in enumerate(pool.imap_unordered(worker_process_chunk, chunks), 1):
                merge(total, part)

                if idx % 5 == 0 or idx == len(chunks):
                    print(
                        f"  progress: {total['processed']:,}/{samples:,} "
                        f"({100.0 * total['processed'] / samples:.2f}%)"
                    )

    # Re-initiealize in main proces for rankings
    _init_worker(skeleton, canvas, params, func)

    selected_rows = []

    if selection_enabled:
        selected_combos, selected_rows = select_ranked_candidates(
            total["qc12_passed"],
            target=selection_target,
            min_margin=selection_min_margin,
        )
        total["selected_candidates"] = len(selected_combos)
    else:
        total["selected_candidates"] = total["qc12_after"][11]

    elapsed = time.time() - start

    output_dir = os.path.join("results", gate)

    write_reports(
        gate=gate,
        full_ld=full_ld,
        total=total,
        elapsed=elapsed,
        output_dir=output_dir,
        sim_time=sim_time,
        selection_enabled=selection_enabled,
        selected_rows=selected_rows,
    )

    print("\nResult summary:")
    print(f"  Processed: {total['processed']:,}")
    print(f"  After F12: {total['qc12_after'][11]:,}")
    if selection_enabled:
        print(f"  Selected candidates: {total['selected_candidates']:,}")
    print(f"  Final Candidates: {total['selected_candidates']:,}")
    print(f"  QC-3 After F12: {total['qc3_after_f12']:,}")

    if total["selected_candidates"]:
        print(f"  Reduction over QC-3: {total['qc3_after_f12'] / total['selected_candidates']:.2f}x")

    print(f"  Wall time: {elapsed:.2f} s")
    print(f"  Output directory: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Run limited sample report for QuickCell-12 vs QC-3."
    )
    parser.add_argument(
    "--connectivity-radius",
    type=float,
    default=None,
    help="Override F7 connectivity radius. Smaller is stricter.",
    )

    parser.add_argument(
    "--d-min",
    type=float,
    default=None,
    help="Override F1 minimum canvas-canvas distance. Larger is stricter.",
    )

    parser.add_argument(
    "--positive-charge-margin",
    type=float,
    default=0.0,
    help="Override F4 positive-charge safety margin. Larger is stricter.",
    )

    parser.add_argument(
    "--charge-min-fraction",
    type=float,
    default=None,
    help="Override F5 minimum negative-charge fraction.",
    )

    parser.add_argument(
    "--charge-max-fraction",
    type=float,
    default=None,
    help="Override F5 maximum negative-charge fraction.",
    )

    parser.add_argument(
    "--charge-count-conflict-radius",
    type=float,
    default=None,
    help="F5 canvas negative-charge conflict radius. Larger is stricter.",
    )

    parser.add_argument(
    "--input-disturbance",
    type=float,
    default=None,
    help="Override F6 input disturbance limit. Smaller is stricter.",
    )

    parser.add_argument(
    "--energy-margin",
    type=float,
    default=None,
    help="Override F10 relaxed energy margin. Smaller is stricter.",
    )


    parser.add_argument(
        "--f11-mode",
        default="counted",
        choices=["counted", "strict-pop", "strict-hop"],
        help=(
            "F11 execution mode. "
            "counted = do not run F11; "
            "strict-pop = population stability only; "
            "strict-hop = population + hop stability."
        ),
    )

    parser.add_argument(
    "--f11-min-support-states",
    type=int,
    default=1,
    help="F11 minimum number of metastable supporting canvas states per input. Larger is stricter.",
    )

    parser.add_argument("--gate", required=True, help="Gate name, comma-separated list, or ALL")
    parser.add_argument("--samples", type=int, default=100000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--chunksize", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--sim-time", type=float, default=0.01)

    parser.add_argument(
        "--strict-profile",
        default="balanced",
        choices=["safe", "balanced", "strict"],
    )

    parser.add_argument(
        "--io-margin",
        type=float,
        default=None,
        help="Override F12 I/O instability margin. Smaller is stricter.",
    )

    parser.add_argument(
        "--pressure-margin",
        type=float,
        default=None,
        help="Override F9 pressure margin. Positive values may be too strict.",
    )

    parser.add_argument(
        "--selection-target",
        type=int,
        default=0,
        help="Optional post-F12 top-k selection target. 0 disables.",
    )

    parser.add_argument(
        "--selection-min-margin",
        type=float,
        default=None,
        help="Optional post-F12 minimum energy margin.",
    )

    args = parser.parse_args()

    gates = parse_gate_argument(args.gate)

    selection_target = args.selection_target if args.selection_target > 0 else None

    for gate in gates:
        run_gate(
            gate=gate,
            samples=args.samples,
            workers=args.workers,
            chunksize=args.chunksize,
            seed=args.seed,
            sim_time=args.sim_time,
            strict_profile=args.strict_profile,
            io_margin=args.io_margin,
            pressure_margin=args.pressure_margin,
            connectivity_radius=args.connectivity_radius,
             d_min=args.d_min,
            positive_charge_margin=args.positive_charge_margin,
            charge_min_fraction=args.charge_min_fraction,
            charge_max_fraction=args.charge_max_fraction,
            charge_count_conflict_radius=args.charge_count_conflict_radius,
            input_disturbance=args.input_disturbance,
            energy_margin=args.energy_margin,
            f11_mode=args.f11_mode,
             f11_min_support_states=args.f11_min_support_states,
            selection_target=selection_target,
            selection_min_margin=args.selection_min_margin,
        )


if __name__ == "__main__":
    main()