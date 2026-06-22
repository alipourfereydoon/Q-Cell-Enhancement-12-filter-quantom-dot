# export_siqad_validation.py
from __future__ import annotations

import argparse
import csv
import json
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
from src.siqad_export import write_candidate_export


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
    connectivity_radius_override: Optional[float],
    charge_min_fraction_override: Optional[float],
    charge_max_fraction_override: Optional[float],
    energy_margin_override: Optional[float],
) -> PhysicalParameters:
    """
    Create PhysicalParameters consistent with run_gate_report.py.

    Important:
    Some additional parameters such as d_min, positive_charge_margin,
    charge_count_conflict_radius, f11_mode, and f11_min_support_states
    are attached after this function, because they are either derived
    attributes or prototype-specific tuning attributes.
    """
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
            charge_min_fraction=_override(0.0, charge_min_fraction_override),
            charge_max_fraction=_override(1.0, charge_max_fraction_override),
            bit0_requires_positive_pressure=False,
            wire_forbidden_radius=_override(0.35, wire_radius_override),
            connectivity_radius=connectivity_radius_override,
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=energy_margin_override,
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
            charge_min_fraction=_override(0.0, charge_min_fraction_override),
            charge_max_fraction=_override(1.0, charge_max_fraction_override),
            bit0_requires_positive_pressure=False,
            wire_forbidden_radius=_override(0.40, wire_radius_override),
            connectivity_radius=connectivity_radius_override,
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=energy_margin_override,
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
            charge_min_fraction=_override(0.0, charge_min_fraction_override),
            charge_max_fraction=_override(1.0, charge_max_fraction_override),
            bit0_requires_positive_pressure=False,
            wire_forbidden_radius=_override(0.45, wire_radius_override),
            connectivity_radius=_override(2.5 * 5.0, connectivity_radius_override),
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=energy_margin_override,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=_override(0.45, input_disturbance_override),
        )

    raise ValueError("Unknown profile. Use: safe, balanced, strict")


def apply_runtime_overrides(
    params: PhysicalParameters,
    d_min: Optional[float],
    positive_charge_margin: Optional[float],
    charge_count_conflict_radius: Optional[float],
    f11_mode: str,
    f11_min_support_states: int,
) -> PhysicalParameters:
    """
    Apply prototype-specific tuning parameters after PhysicalParameters creation.
    """
    if d_min is not None:
        params.d_min = float(d_min)

    params.positive_charge_margin = float(positive_charge_margin or 0.0)
    params.charge_count_conflict_radius = charge_count_conflict_radius

    params.f11_mode = str(f11_mode)
    params.f11_min_support_states = int(f11_min_support_states)

    if params.f11_mode == "counted":
        # Old behavior: F11 is only counted as survived.
        params.relaxed_enumeration = True
        params.check_configuration_stability = False

    elif params.f11_mode == "strict-pop":
        # Real F11 with population stability only.
        params.relaxed_enumeration = False
        params.check_configuration_stability = False
        params.check_fixed_io_population = False

    elif params.f11_mode == "strict-hop":
        # Real F11 with population stability and hop stability.
        params.relaxed_enumeration = False
        params.check_configuration_stability = True
        params.check_fixed_io_population = False

    else:
        raise ValueError("Unknown --f11-mode. Use: counted, strict-pop, strict-hop")

    return params


def fixed_charges_ordered(
    skeleton,
    x: Tuple[int, ...],
    y: Tuple[int, ...],
) -> List[int]:
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

    return Layout(
        skeleton=skeleton,
        canvas_positions=[canvas.positions[i] for i in combo],
        canvas_indices=combo,
    )


def min_relaxed_energy(
    combo: Tuple[int, ...],
    x: Tuple[int, ...],
    y: Tuple[int, ...],
) -> float:
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
    """
    Return True if layout should be discarded by F12.
    """
    params = _G["params"]
    func = _G["func"]

    tol = max(params.energy_tolerance, params.io_instability_margin)

    for x in func.all_inputs():
        y_correct = func.eval(x)

        e_correct = min_relaxed_energy(
            combo,
            tuple(x),
            tuple(y_correct),
        )

        for y_alt in func.all_outputs():
            y_alt = tuple(y_alt)

            if y_alt == tuple(y_correct):
                continue

            e_alt = min_relaxed_energy(
                combo,
                tuple(x),
                y_alt,
            )

            if e_alt < e_correct - tol:
                return True

    return False


def fast_energy_margin(combo: Tuple[int, ...]) -> float:
    """
    Minimum energy margin over all input patterns:
        best incorrect energy - correct energy

    Larger is better.
    """
    func = _G["func"]

    min_margin = float("inf")

    for x in func.all_inputs():
        y_correct = tuple(func.eval(x))

        e_correct = min_relaxed_energy(
            combo,
            tuple(x),
            y_correct,
        )

        best_alt = float("inf")

        for y_alt in func.all_outputs():
            y_alt = tuple(y_alt)

            if y_alt == y_correct:
                continue

            e_alt = min_relaxed_energy(
                combo,
                tuple(x),
                y_alt,
            )

            if e_alt < best_alt:
                best_alt = e_alt

        margin = best_alt - e_correct

        if margin < min_margin:
            min_margin = margin

    return float(min_margin)


def run_filter_sequence_for_qc12(layout: Layout) -> Tuple[List[int], bool]:
    """
    Run F1-F12 for one layout.

    after[i] = 1 means the layout survived filter i+1.
    Return:
        after, passed_all
    """
    params = _G["params"]
    func = _G["func"]
    skeleton = _G["skeleton"]
    canvas = _G["canvas"]

    after = [0] * 12

    # F1-F10
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

    # F11
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

    # F12
    discard_f12 = fast_f12_relaxed(tuple(layout.canvas_indices))

    if discard_f12:
        return after, False

    after[11] = 1

    return after, True


def worker_process_chunk(chunk: List[Tuple[int, ...]]) -> Dict[str, Any]:
    qc12_after = [0 for _ in range(12)]
    qc12_passed = []

    for combo in chunk:
        layout = make_layout(combo)

        after, passed = run_filter_sequence_for_qc12(layout)

        for i in range(12):
            qc12_after[i] += after[i]

        if passed:
            qc12_passed.append(combo)

    return {
        "processed": len(chunk),
        "qc12_after": qc12_after,
        "qc12_passed": qc12_passed,
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


def chunked(iterable, size: int):
    batch = []

    for item in iterable:
        batch.append(item)

        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def expected_truth_table(func) -> Dict[str, Any]:
    table = {}

    for x in func.all_inputs():
        key = "".join(str(i) for i in x)
        y = func.eval(x)
        table[key] = "".join(str(i) for i in y)

    return table


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

        rows.append(
            {
                "rank": len(selected),
                "energy_margin": margin,
                "canvas_indices": " ".join(str(i) for i in combo),
            }
        )

    return selected, rows


def write_csv_simple(path: str, rows: List[Dict[str, Any]]):
    if not rows:
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_validation_sheet(
    root_dir: str,
    gate: str,
    candidate_ids: List[int],
    func,
    candidate_file_map: Dict[int, str],
):
    path = os.path.join(root_dir, "validation_sheet.csv")

    fieldnames = [
        "gate",
        "candidate_id",
        "input_bits",
        "expected_output",
        "observed_output",
        "io_integrity_ok",
        "siqad_file",
        "notes",
    ]

    rows = []

    for cid in candidate_ids:
        for x in func.all_inputs():
            input_bits = "".join(str(i) for i in x)
            expected = "".join(str(i) for i in func.eval(x))

            rows.append(
                {
                    "gate": gate,
                    "candidate_id": cid,
                    "input_bits": input_bits,
                    "expected_output": expected,
                    "observed_output": "",
                    "io_integrity_ok": "",
                    "siqad_file": candidate_file_map[cid],
                    "notes": "",
                }
            )

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path


def write_readme(root_dir: str, gate: str):
    path = os.path.join(root_dir, "README_validation.md")

    lines = [
        f"# SiQAD Validation Package for {gate}",
        "",
        "Open `candidate.sqd` in each candidate folder.",
        "",
        "Use `all_sidbs.csv` to identify IN/OUT BDL pairs.",
        "",
        "Fill `validation_sheet.csv` after SiQAD simulation.",
        "",
        "BDL encoding used by this prototype:",
        "",
        "- bit 0: pos_a = -1, pos_b = 0",
        "- bit 1: pos_a = 0, pos_b = -1",
        "",
        "After filling the validation sheet, run:",
        "",
        "```bash",
        "python analyze_siqad_results.py --sheet validation_exports/<GATE>/validation_sheet.csv",
        "```",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def parse_gate_argument(gate_arg: str) -> List[str]:
    gate_arg = gate_arg.strip()

    if gate_arg.upper() == "ALL":
        return get_all_3input_gate_names()

    return [
        normalize_gate_name(g)
        for g in gate_arg.split(",")
        if g.strip()
    ]


def run_export_for_gate(args, gate: str) -> Dict[str, Any]:
    gate = normalize_gate_name(gate)

    func = get_3input_gate(gate)
    skeleton = paper_like_skeleton_3in_1out_25()
    canvas = paper_like_canvas_143()

    params = make_params(
        profile=args.strict_profile,
        io_margin_override=args.io_margin,
        pressure_margin_override=args.pressure_margin,
        wire_radius_override=args.wire_radius,
        input_disturbance_override=args.input_disturbance,
        connectivity_radius_override=args.connectivity_radius,
        charge_min_fraction_override=args.charge_min_fraction,
        charge_max_fraction_override=args.charge_max_fraction,
        energy_margin_override=args.energy_margin,
    )

    params = apply_runtime_overrides(
        params=params,
        d_min=args.d_min,
        positive_charge_margin=args.positive_charge_margin,
        charge_count_conflict_radius=args.charge_count_conflict_radius,
        f11_mode=args.f11_mode,
        f11_min_support_states=args.f11_min_support_states,
    )

    root_dir = os.path.join(args.output_dir, gate)
    os.makedirs(root_dir, exist_ok=True)

    combos = random_combinations(
        n=canvas.n_pos,
        d=4,
        count=args.samples,
        seed=args.seed,
    )

    chunks = list(chunked(combos, args.chunksize))

    print("=" * 80)
    print(f"Exporting SiQAD validation candidates for gate: {gate}")
    print(f"|C| = {canvas.n_pos}, d = 4, |Ld| = {math.comb(canvas.n_pos, 4):,}")
    print(f"Samples: {args.samples}")
    print(f"Max candidates to export: {args.max_candidates}")
    print(f"Workers: {args.workers}")
    print(f"Chunksize: {args.chunksize}")
    print(f"Seed: {args.seed}")
    print(f"Profile: {args.strict_profile}")
    print("-" * 80)
    print(f"F1 d_min = {params.d_min}")
    print(f"F3 wire forbidden radius = {params.wire_forbidden_radius}")
    print(f"F4 positive charge margin = {params.positive_charge_margin}")
    print(f"F5 charge fraction = [{params.charge_min_fraction}, {params.charge_max_fraction}]")
    print(f"F5 charge-count conflict radius = {params.charge_count_conflict_radius}")
    print(f"F6 input disturbance limit = {params.input_disturbance_limit}")
    print(f"F7 connectivity radius = {params.connectivity_radius}")
    print(f"F9 pressure margin = {params.pressure_margin}")
    print(f"F10 energy margin = {params.energy_bound_margin}")
    print(f"F11 mode = {params.f11_mode}")
    print(f"F11 min support states = {params.f11_min_support_states}")
    print(f"F11 relaxed enumeration = {params.relaxed_enumeration}")
    print(f"F11 hop stability check = {params.check_configuration_stability}")
    print(f"F12 I/O margin = {params.io_instability_margin}")
    print("-" * 80)
    print(f"Selection target: {args.selection_target}")
    print(f"Selection min margin: {args.selection_min_margin}")
    print("=" * 80)

    total_processed = 0
    after_counts = [0 for _ in range(12)]
    passed_all = []

    start = time.time()

    if args.workers <= 1:
        _init_worker(skeleton, canvas, params, func)

        for chunk in chunks:
            result = worker_process_chunk(chunk)

            total_processed += result["processed"]

            for i in range(12):
                after_counts[i] += result["qc12_after"][i]

            passed_all.extend(result["qc12_passed"])

            print(
                f"[{gate}] processed {total_processed}/{args.samples}, "
                f"raw passed {len(passed_all)}"
            )

    else:
        ctx = mp.get_context("spawn")

        with ctx.Pool(
            processes=args.workers,
            initializer=_init_worker,
            initargs=(skeleton, canvas, params, func),
        ) as pool:
            for idx, result in enumerate(
                pool.imap_unordered(worker_process_chunk, chunks),
                1,
            ):
                total_processed += result["processed"]

                for i in range(12):
                    after_counts[i] += result["qc12_after"][i]

                passed_all.extend(result["qc12_passed"])

                if idx % 5 == 0 or idx == len(chunks):
                    print(
                        f"[{gate}] processed {total_processed}/{args.samples}, "
                        f"raw passed {len(passed_all)}"
                    )

    # Reinitialize in main process for ranking/export.
    _init_worker(skeleton, canvas, params, func)

    ranking_rows: List[Dict[str, Any]] = []

    selection_enabled = (
        args.selection_target > 0
        or args.selection_min_margin is not None
    )

    if selection_enabled:
        selected_combos, ranking_rows = select_ranked_candidates(
            combos=passed_all,
            target=args.selection_target if args.selection_target > 0 else None,
            min_margin=args.selection_min_margin,
        )
    else:
        selected_combos = passed_all[: args.max_candidates]

    if len(selected_combos) > args.max_candidates:
        selected_combos = selected_combos[: args.max_candidates]

    candidate_ids: List[int] = []
    candidate_file_map: Dict[int, str] = {}
    summary_rows: List[Dict[str, Any]] = []

    truth = expected_truth_table(func)

    for combo in selected_combos:
        cid = len(candidate_ids) + 1

        layout = Layout(
            skeleton=skeleton,
            canvas_positions=[canvas.positions[i] for i in combo],
            canvas_indices=combo,
        )

        files = write_candidate_export(
            root_dir=root_dir,
            gate_name=gate,
            candidate_id=cid,
            layout=layout,
            expected_truth_table=truth,
            snap_to_lattice=not args.no_snap,
        )

        candidate_ids.append(cid)
        candidate_file_map[cid] = files["sqd"]

        margin = fast_energy_margin(combo)

        summary_rows.append(
            {
                "gate": gate,
                "candidate_id": cid,
                "energy_margin": margin,
                "canvas_indices": " ".join(str(i) for i in combo),
                "candidate_json": files["json"],
                "candidate_csv": files["csv"],
                "candidate_sqd": files["sqd"],
            }
        )

    sheet_path = write_validation_sheet(
        root_dir=root_dir,
        gate=gate,
        candidate_ids=candidate_ids,
        func=func,
        candidate_file_map=candidate_file_map,
    )

    write_csv_simple(
        os.path.join(root_dir, "export_summary.csv"),
        summary_rows,
    )

    if ranking_rows:
        write_csv_simple(
            os.path.join(root_dir, "candidate_ranking.csv"),
            ranking_rows,
        )

    readme_path = write_readme(root_dir, gate)

    elapsed = time.time() - start

    report = {
        "gate": gate,
        "samples_requested": args.samples,
        "samples_processed": total_processed,
        "raw_post_f12_candidates": len(passed_all),
        "exported_candidates": len(candidate_ids),
        "after_counts": {
            f"F{i + 1}": after_counts[i]
            for i in range(12)
        },
        "elapsed_seconds": elapsed,
        "validation_sheet": sheet_path,
        "readme": readme_path,
        "profile": args.strict_profile,
        "parameters": {
            "d_min": params.d_min,
            "wire_forbidden_radius": params.wire_forbidden_radius,
            "positive_charge_margin": params.positive_charge_margin,
            "charge_min_fraction": params.charge_min_fraction,
            "charge_max_fraction": params.charge_max_fraction,
            "charge_count_conflict_radius": params.charge_count_conflict_radius,
            "input_disturbance_limit": params.input_disturbance_limit,
            "connectivity_radius": params.connectivity_radius,
            "pressure_margin": params.pressure_margin,
            "energy_bound_margin": params.energy_bound_margin,
            "f11_mode": params.f11_mode,
            "f11_min_support_states": params.f11_min_support_states,
            "f11_relaxed_enumeration": params.relaxed_enumeration,
            "f11_hop_stability_check": params.check_configuration_stability,
            "io_instability_margin": params.io_instability_margin,
        },
    }

    with open(
        os.path.join(root_dir, "export_report.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\nFilter counts:")
    for i, v in enumerate(after_counts, start=1):
        print(f" After F{i}: {v}")

    print(f"\nExport completed for {gate}.")
    print(f"Output folder: {root_dir}")
    print(f"Validation sheet: {sheet_path}")
    print(f"Raw post-F12 candidates: {len(passed_all)}")
    print(f"Exported candidates: {len(candidate_ids)}")
    print(f"Elapsed time: {elapsed:.2f}s")

    return report


def write_global_summary(output_dir: str, reports: List[Dict[str, Any]]):
    os.makedirs(output_dir, exist_ok=True)

    path = os.path.join(output_dir, "all_gates_export_summary.csv")

    fieldnames = [
        "gate",
        "samples_requested",
        "samples_processed",
        "raw_post_f12_candidates",
        "exported_candidates",
        "elapsed_seconds",
        "validation_sheet",
        "profile",
        "d_min",
        "io_margin",
        "connectivity_radius",
        "pressure_margin",
        "energy_margin",
        "f11_mode",
        "f11_min_support_states",
    ]

    rows = []

    for r in reports:
        p = r.get("parameters", {})

        rows.append(
            {
                "gate": r.get("gate"),
                "samples_requested": r.get("samples_requested"),
                "samples_processed": r.get("samples_processed"),
                "raw_post_f12_candidates": r.get("raw_post_f12_candidates"),
                "exported_candidates": r.get("exported_candidates"),
                "elapsed_seconds": r.get("elapsed_seconds"),
                "validation_sheet": r.get("validation_sheet"),
                "profile": r.get("profile"),
                "d_min": p.get("d_min"),
                "io_margin": p.get("io_instability_margin"),
                "connectivity_radius": p.get("connectivity_radius"),
                "pressure_margin": p.get("pressure_margin"),
                "energy_margin": p.get("energy_bound_margin"),
                "f11_mode": p.get("f11_mode"),
                "f11_min_support_states": p.get("f11_min_support_states"),
            }
        )

    write_csv_simple(path, rows)

    print(f"\nGlobal export summary: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Export QuickCell candidates for SiQAD validation."
    )

    parser.add_argument(
        "--gate",
        required=True,
        help="Gate name, comma-separated list, or ALL.",
    )

    parser.add_argument("--samples", type=int, default=100000)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--chunksize", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--output-dir", default="validation_exports")

    parser.add_argument(
        "--strict-profile",
        default="balanced",
        choices=["safe", "balanced", "strict"],
    )

    # Existing / original margins
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
        help="Override F9 pressure margin. Larger is stricter.",
    )

    # Added tunable filters
    parser.add_argument(
        "--d-min",
        type=float,
        default=None,
        help="Override F1 minimum canvas-canvas distance. Larger is stricter.",
    )

    parser.add_argument(
        "--wire-radius",
        type=float,
        default=None,
        help="Override F3 wire forbidden radius. Larger is stricter.",
    )

    parser.add_argument(
        "--positive-charge-margin",
        type=float,
        default=0.0,
        help="F4 positive-charge safety margin. Larger is stricter.",
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
        "--connectivity-radius",
        type=float,
        default=None,
        help="Override F7 connectivity radius. Smaller is stricter.",
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
        help=(
            "F11 minimum number of metastable supporting canvas states "
            "per input. Larger is stricter."
        ),
    )

    # Candidate selection / export controls
    parser.add_argument(
        "--selection-target",
        type=int,
        default=0,
        help="Rank post-F12 candidates and export only top K. 0 disables.",
    )

    parser.add_argument(
        "--selection-min-margin",
        type=float,
        default=None,
        help="Optional minimum energy margin for exported candidates.",
    )

    parser.add_argument(
        "--no-snap",
        action="store_true",
        help="Do not snap exported SiDBs to nearest SiQAD lattice coordinates.",
    )

    args = parser.parse_args()

    gates = parse_gate_argument(args.gate)

    reports = []

    for gate in gates:
        report = run_export_for_gate(args, gate)
        reports.append(report)

    write_global_summary(args.output_dir, reports)


if __name__ == "__main__":
    main()