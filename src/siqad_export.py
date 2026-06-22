# src/siqad_export.py

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from html import escape
from typing import Dict, Any, List, Tuple

from .data_structures import Layout


DEFAULT_A1_X = 3.84
DEFAULT_A2_Y = 7.68

DEFAULT_BASIS = {
    0: (0.0, 0.0),
    1: (0.0, 2.25),
}


def _fmt(v: float) -> str:
    s = f"{float(v):.9f}"
    s = s.rstrip("0").rstrip(".")

    if s == "-0":
        s = "0"

    return s


def _arr_to_list(p):
    return [float(p[0]), float(p[1]), float(p[2])]


def _nearest_lattice_coord(
    x: float,
    y: float,
    used: set,
    a1_x: float = DEFAULT_A1_X,
    a2_y: float = DEFAULT_A2_Y,
    basis: Dict[int, Tuple[float, float]] = DEFAULT_BASIS,
    max_radius: int = 50,
) -> Dict[str, Any]:
    for radius in range(max_radius + 1):
        candidates = []

        for l, (bx, by) in basis.items():
            n0 = round((x - bx) / a1_x)
            m0 = round((y - by) / a2_y)

            for dn in range(-radius, radius + 1):
                for dm in range(-radius, radius + 1):
                    n = n0 + dn
                    m = m0 + dm

                    key = (int(n), int(m), int(l))

                    if key in used:
                        continue

                    sx = n * a1_x + bx
                    sy = m * a2_y + by

                    dist2 = (sx - x) ** 2 + (sy - y) ** 2
                    candidates.append((dist2, int(n), int(m), int(l), sx, sy))

        if candidates:
            candidates.sort(key=lambda t: t[0])
            dist2, n, m, l, sx, sy = candidates[0]
            used.add((n, m, l))

            return {
                "n": n,
                "m": m,
                "l": l,
                "siqad_x": float(sx),
                "siqad_y": float(sy),
                "snap_error": float(dist2 ** 0.5),
            }

    raise RuntimeError("Could not find an unused SiQAD lattice coordinate.")


def collect_layout_rows(layout: Layout) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    skeleton = layout.skeleton
    site_id = 0

    for pin_idx, pin in enumerate(skeleton.input_pins):
        rows.append({
            "site_id": site_id,
            "kind": "skeleton_input",
            "role": f"IN{pin_idx}_A",
            "pin_index": pin_idx,
            "x": float(pin.pos_a[0]),
            "y": float(pin.pos_a[1]),
            "z": float(pin.pos_a[2]),
        })
        site_id += 1

        rows.append({
            "site_id": site_id,
            "kind": "skeleton_input",
            "role": f"IN{pin_idx}_B",
            "pin_index": pin_idx,
            "x": float(pin.pos_b[0]),
            "y": float(pin.pos_b[1]),
            "z": float(pin.pos_b[2]),
        })
        site_id += 1

    for pin_idx, pin in enumerate(skeleton.output_pins):
        rows.append({
            "site_id": site_id,
            "kind": "skeleton_output",
            "role": f"OUT{pin_idx}_A",
            "pin_index": pin_idx,
            "x": float(pin.pos_a[0]),
            "y": float(pin.pos_a[1]),
            "z": float(pin.pos_a[2]),
        })
        site_id += 1

        rows.append({
            "site_id": site_id,
            "kind": "skeleton_output",
            "role": f"OUT{pin_idx}_B",
            "pin_index": pin_idx,
            "x": float(pin.pos_b[0]),
            "y": float(pin.pos_b[1]),
            "z": float(pin.pos_b[2]),
        })
        site_id += 1

    for wire_idx, w in enumerate(skeleton.wire_sidbs):
        p = w.coords

        rows.append({
            "site_id": site_id,
            "kind": "skeleton_wire",
            "role": f"WIRE{wire_idx}",
            "pin_index": "",
            "x": float(p[0]),
            "y": float(p[1]),
            "z": float(p[2]),
        })
        site_id += 1

    for canvas_idx, p in enumerate(layout.canvas_positions):
        rows.append({
            "site_id": site_id,
            "kind": "canvas",
            "role": f"CANVAS{canvas_idx}",
            "pin_index": "",
            "x": float(p[0]),
            "y": float(p[1]),
            "z": float(p[2]),
        })
        site_id += 1

    return rows


def prepare_siqad_rows(
    rows: List[Dict[str, Any]],
    snap_to_lattice: bool = True,
) -> List[Dict[str, Any]]:
    out = []
    used = set()

    for row in rows:
        r = dict(row)

        nearest = _nearest_lattice_coord(
            x=float(row["x"]),
            y=float(row["y"]),
            used=used,
        )

        r.update(nearest)

        if snap_to_lattice:
            r["export_x"] = nearest["siqad_x"]
            r["export_y"] = nearest["siqad_y"]
        else:
            r["export_x"] = float(row["x"])
            r["export_y"] = float(row["y"])

        out.append(r)

    return out


def color_for_kind(kind: str) -> str:
    if kind == "skeleton_input":
        return "#ff66ccff"
    if kind == "skeleton_output":
        return "#ffffcc66"
    if kind == "skeleton_wire":
        return "#ffc8c8c8"
    if kind == "canvas":
        return "#ff66dd66"
    return "#ffc8c8c8"


def write_rows_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fieldnames = [
        "site_id",
        "kind",
        "role",
        "pin_index",
        "x",
        "y",
        "z",
        "n",
        "m",
        "l",
        "siqad_x",
        "siqad_y",
        "export_x",
        "export_y",
        "snap_error",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_siqad_033_sqd(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if rows:
        xs = [float(r["export_x"]) for r in rows]
        ys = [float(r["export_y"]) for r in rows]
        margin = 10.0
        x1 = min(xs) - margin
        x2 = max(xs) + margin
        y1 = min(ys) - margin
        y2 = max(ys) + margin
    else:
        x1, x2, y1, y2 = -50, 50, -50, 50

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<siqad>\n")

        f.write("    <program>\n")
        f.write("        <file_purpose>save</file_purpose>\n")
        f.write("        <version>0.3.3</version>\n")
        f.write(f"        <date>{escape(now)}</date>\n")
        f.write("    </program>\n")

        f.write("    <gui>\n")
        f.write("        <zoom>0.1</zoom>\n")
        f.write(
            f'        <displayed_region x1="{_fmt(x1)}" y1="{_fmt(y1)}" '
            f'x2="{_fmt(x2)}" y2="{_fmt(y2)}"/>\n'
        )
        f.write('        <scroll x="0" y="0"/>\n')
        f.write("    </gui>\n")

        f.write("    <layers>\n")

        f.write("        <layer_prop>\n")
        f.write("            <name>Lattice</name>\n")
        f.write("            <type>Lattice</type>\n")
        f.write("            <role>Design</role>\n")
        f.write("            <zoffset>0</zoffset>\n")
        f.write("            <zheight>0</zheight>\n")
        f.write("            <visible>1</visible>\n")
        f.write("            <active>0</active>\n")
        f.write("            <lat_vec>\n")
        f.write('                <a1 x="3.84" y="0"/>\n')
        f.write('                <a2 x="0" y="7.68"/>\n')
        f.write("                <N>2</N>\n")
        f.write('                <b1 x="0" y="0"/>\n')
        f.write('                <b2 x="0" y="2.25"/>\n')
        f.write("            </lat_vec>\n")
        f.write("        </layer_prop>\n")

        f.write("        <layer_prop>\n")
        f.write("            <name>Screenshot Overlay</name>\n")
        f.write("            <type>Misc</type>\n")
        f.write("            <role>Overlay</role>\n")
        f.write("            <zoffset>0</zoffset>\n")
        f.write("            <zheight>0</zheight>\n")
        f.write("            <visible>1</visible>\n")
        f.write("            <active>0</active>\n")
        f.write("        </layer_prop>\n")

        f.write("        <layer_prop>\n")
        f.write("            <name>Surface</name>\n")
        f.write("            <type>DB</type>\n")
        f.write("            <role>Design</role>\n")
        f.write("            <zoffset>0</zoffset>\n")
        f.write("            <zheight>0</zheight>\n")
        f.write("            <visible>1</visible>\n")
        f.write("            <active>0</active>\n")
        f.write("        </layer_prop>\n")

        f.write("        <layer_prop>\n")
        f.write("            <name>Metal</name>\n")
        f.write("            <type>Electrode</type>\n")
        f.write("            <role>Design</role>\n")
        f.write("            <zoffset>1000</zoffset>\n")
        f.write("            <zheight>100</zheight>\n")
        f.write("            <visible>1</visible>\n")
        f.write("            <active>0</active>\n")
        f.write("        </layer_prop>\n")

        f.write("    </layers>\n")

        f.write("    <design>\n")
        f.write('        <layer type="Lattice"/>\n')
        f.write('        <layer type="Misc"/>\n')
        f.write('        <layer type="DB">\n')

        for row in rows:
            color = color_for_kind(row["kind"])

            f.write(f"            <!-- {escape(str(row['kind']))} {escape(str(row['role']))} -->\n")
            f.write("            <dbdot>\n")
            f.write("                <layer_id>2</layer_id>\n")
            f.write(
                f'                <latcoord n="{int(row["n"])}" '
                f'm="{int(row["m"])}" l="{int(row["l"])}"/>\n'
            )
            f.write(
                f'                <physloc x="{_fmt(row["export_x"])}" '
                f'y="{_fmt(row["export_y"])}"/>\n'
            )
            f.write(f"                <color>{color}</color>\n")
            f.write("            </dbdot>\n")

        f.write("        </layer>\n")
        f.write('        <layer type="Electrode"/>\n')
        f.write("    </design>\n")
        f.write("</siqad>\n")


def _arr_to_list(p):
    return [float(p[0]), float(p[1]), float(p[2])]


def layout_to_json_dict(
    gate_name: str,
    candidate_id: int,
    layout: Layout,
    expected_truth_table: Dict[str, Any],
    siqad_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    skeleton = layout.skeleton

    return {
        "gate": gate_name,
        "candidate_id": candidate_id,
        "canvas_indices": list(layout.canvas_indices),
        "input_pins": [
            {
                "pin_index": i,
                "pos_a": _arr_to_list(pin.pos_a),
                "pos_b": _arr_to_list(pin.pos_b),
                "encoding": {
                    "0": {"pos_a": -1, "pos_b": 0},
                    "1": {"pos_a": 0, "pos_b": -1},
                },
            }
            for i, pin in enumerate(skeleton.input_pins)
        ],
        "output_pins": [
            {
                "pin_index": i,
                "pos_a": _arr_to_list(pin.pos_a),
                "pos_b": _arr_to_list(pin.pos_b),
                "encoding": {
                    "0": {"pos_a": -1, "pos_b": 0},
                    "1": {"pos_a": 0, "pos_b": -1},
                },
            }
            for i, pin in enumerate(skeleton.output_pins)
        ],
        "wire_sidbs": [_arr_to_list(w.coords) for w in skeleton.wire_sidbs],
        "canvas_sidbs": [_arr_to_list(p) for p in layout.canvas_positions],
        "expected_truth_table": expected_truth_table,
        "siqad_export_rows": siqad_rows,
    }


def write_candidate_export(
    root_dir: str,
    gate_name: str,
    candidate_id: int,
    layout: Layout,
    expected_truth_table: Dict[str, Any],
    snap_to_lattice: bool = True,
) -> Dict[str, str]:
    candidate_dir = os.path.join(
        root_dir,
        "candidates",
        f"candidate_{candidate_id:06d}",
    )

    os.makedirs(candidate_dir, exist_ok=True)

    raw_rows = collect_layout_rows(layout)

    siqad_rows = prepare_siqad_rows(
        raw_rows,
        snap_to_lattice=snap_to_lattice,
    )

    csv_path = os.path.join(candidate_dir, "all_sidbs.csv")
    sqd_path = os.path.join(candidate_dir, "candidate.sqd")
    json_path = os.path.join(candidate_dir, "candidate.json")

    write_rows_csv(csv_path, siqad_rows)
    write_siqad_033_sqd(sqd_path, siqad_rows)

    data = layout_to_json_dict(
        gate_name=gate_name,
        candidate_id=candidate_id,
        layout=layout,
        expected_truth_table=expected_truth_table,
        siqad_rows=siqad_rows,
    )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {
        "candidate_dir": candidate_dir,
        "csv": csv_path,
        "sqd": sqd_path,
        "json": json_path,
    }