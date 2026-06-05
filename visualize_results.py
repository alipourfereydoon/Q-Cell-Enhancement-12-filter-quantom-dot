# visualize_results.py
# Compare QuickCell original 3-filter flow with QuickCell-8.
# Generates CSV, PNG plots, and HTML report.

import os
import csv
import numpy as np
import matplotlib.pyplot as plt

import core_sidb

from core_sidb import FUNCTIONS, number_of_candidates, CORE_VERSION, PARAMS
from quickcell_original import run_quickcell_original
from quickcell_8 import run_quickcell_8


OUT_DIR = "quickcell8_report"
os.makedirs(OUT_DIR, exist_ok=True)


def safe_speedup(t_old, t_new):
    if t_new <= 0:
        return float("inf")
    return t_old / t_new


def run_all():
    print("Imported core_sidb from:", core_sidb.__file__)
    print("CORE_VERSION:", CORE_VERSION)
    print("PARAMS.v_scale:", PARAMS.v_scale)

    print("\n Running QuickCell original vs QuickCell-8 ...")
    print(" Candidates:", number_of_candidates(d=3))

    results = []

    for fn in FUNCTIONS.keys():
        r3 = run_quickcell_original(fn, d=3)
        r8 = run_quickcell_8(fn, d=3)

        t3 = r3.get("time", 0.0)
        t8 = r8.get("time", 0.0)

        speedup = safe_speedup(t3, t8)

        item = {
            "fn": fn,
            "initial": r8.get("initial", number_of_candidates(d=3)),
            "P1": r8.get("P1", 0),
            "P2": r8.get("P2", 0),
            "P3": r8.get("P3", 0),
            "valid3": r3.get("valid", 0),
            "valid8": r8.get("valid", 0),
            "t3": t3,
            "t8": t8,
            "speedup": speedup,
            "stats8": r8.get("stats", {}),
        }

        results.append(item)

        print(
            f"   {fn}: "
            f"3-f={item['valid3']}, "
            f"8-f={item['valid8']}, "
            f"t_3={item['t3']:.4f}s, "
            f"t_8={item['t8']:.4f}s"
        )

    return results


def print_table(results):
    print("\n" + "=" * 92)
    print("  QuickCell (3 filters) vs QuickCell-8 (8 filters)")
    print("=" * 92)

    print(
        f"{'Fn':<8} {'|Ld|':>5} {'P1':>4} {'P2':>4} {'P3':>4} "
        f"{'|L*|3':>7} {'t_3(s)':>9} "
        f"{'|L*|8':>8} {'t_8(s)':>9} {'Speedup':>8}"
    )

    print("-" * 92)

    for r in results:
        print(
            f"{r['fn']:<8} "
            f"{r['initial']:>5} "
            f"{r['P1']:>4} "
            f"{r['P2']:>4} "
            f"{r['P3']:>4} "
            f"{r['valid3']:>7} "
            f"{r['t3']:>9.4f} "
            f"{r['valid8']:>8} "
            f"{r['t8']:>9.4f} "
            f"{r['speedup']:>7.2f}×"
        )

    print("=" * 92)


def save_csv(results):
    path = os.path.join(OUT_DIR, "quickcell8_results.csv")

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        writer.writerow([
            "Function",
            "|Ld|",
            "P1",
            "P2",
            "P3",
            "|L*|_3",
            "t3_s",
            "|L*|_8",
            "t8_s",
            "Speedup",
            "F1",
            "F2",
            "F3",
            "F4",
            "F5",
            "F6",
            "F7",
            "F8",
            "F9",
            "F10",
            "F11",
            "F12",
        ])

        for r in results:
            stats = r["stats8"]

            writer.writerow([
                r["fn"],
                r["initial"],
                r["P1"],
                r["P2"],
               r["P3"],
                r["valid3"],
                r["t3"],
                r["valid8"],
                r["t8"],
                r["speedup"],
                stats.get("F1", 0),
               stats.get("F2", 0),
                stats.get("F3", 0),
                "REMOVED",
                stats.get("F5", 0),
                "REMOVED",
               stats.get("F7", 0),
                "REMOVED",
               stats.get("F9", 0),
                "REMOVED",
               stats.get("F11", 0),
                stats.get("F12", 0),
            ])


def plot_runtime_comparison(results):
    names = [r["fn"] for r in results]
    t3 = [r["t3"] for r in results]
    t8 = [r["t8"] for r in results]

    x = np.arange(len(names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))

    bars3 = ax.bar(
        x - width / 2,
        t3,
        width,
        label="QuickCell (3 filters)",
        color="#1f77b4",
        edgecolor="black",
    )

    bars8 = ax.bar(
        x + width / 2,
        t8,
        width,
        label="QuickCell-8 (8 filters)",
        color="#ff7f0e",
        edgecolor="black",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Runtime [s]")
    ax.set_title("Runtime Comparison: QuickCell vs QuickCell-8")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()

    ymax = max(t3 + t8) if max(t3 + t8) > 0 else 1.0
    offset = ymax * 0.015

    for bar in bars3:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + offset,
            f"{h:.2f}s",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    for bar in bars8:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + offset,
            f"{h:.2f}s",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "runtime_comparison.png"), dpi=300)
    plt.close()


def plot_search_space_reduction(results):
    names = [r["fn"] for r in results]

    initial = [r["initial"] for r in results]
    p1 = [r["P1"] for r in results]
    p2 = [r["P2"] for r in results]
    p3 = [r["P3"] for r in results]

    x = np.arange(len(names))
    width = 0.20

    fig, ax = plt.subplots(figsize=(12, 6))

    b0 = ax.bar(
        x - 1.5 * width,
        initial,
        width,
        label="Candidates",
        color="#cccccc",
        edgecolor="black",
    )

    b1 = ax.bar(
        x - 0.5 * width,
        p1,
        width,
        label="After Phase 1",
        color="#9ecae1",
        edgecolor="black",
    )

    b2 = ax.bar(
        x + 0.5 * width,
        p2,
        width,
        label="After Phase 2",
        color="#4292c6",
        edgecolor="black",
    )

    b3 = ax.bar(
        x + 1.5 * width,
        p3,
        width,
        label="After Phase 3",
        color="#08519c",
        edgecolor="black",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("# Layouts")
    ax.set_title("QuickCell-8 — Search Space Reduction Across Phases")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()

    ymax = max(initial + p1 + p2 + p3) if max(initial + p1 + p2 + p3) > 0 else 1
    offset = ymax * 0.015

    for bars in [b0, b1, b2, b3]:
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + offset,
                f"{int(h)}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "search_space_reduction.png"), dpi=300)
    plt.close()


def plot_filter_breakdown(results):
    names = [r["fn"] for r in results]
    filters = [f"F{i}" for i in range(1, 13)]

    x = np.arange(len(names))
    bottom = np.zeros(len(names))

    fig, ax = plt.subplots(figsize=(14, 6))

    colors = plt.cm.tab20(np.linspace(0, 1, 12))

    for idx, f in enumerate(filters):
        if f in ["F4", "F6", "F8", "F10"]:
            vals = np.zeros(len(names))
            label = f"{f} removed"
        else:
            vals = np.array([r["stats8"].get(f, 0) for r in results])
            label = f

        ax.bar(
            x,
            vals,
            bottom=bottom,
            label=label,
            color=colors[idx],
            edgecolor="black",
        )

        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("# Layouts Pruned")
    ax.set_title("QuickCell-8 — Per-Filter Pruning Breakdown")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(ncol=2, bbox_to_anchor=(1.02, 1), loc="upper left")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "filter_breakdown.png"), dpi=300)
    plt.close()


def write_html(results):
    rows = ""

    for r in results:
        rows += f"""
        <tr>
            <td><b>{r['fn']}</b></td>
            <td>{r['initial']}</td>
            <td>{r['P1']}</td>
            <td>{r['P2']}</td>
            <td>{r['P3']}</td>
            <td>{r['valid3']}</td>
            <td>{r['t3']:.4f}s</td>
            <td>{r['valid8']}</td>
            <td>{r['t8']:.4f}s</td>
            <td>{r['speedup']:.2f}×</td>
        </tr>
        """

    filter_rows = ""

    for r in results:
        stats = r["stats8"]

        cells = ""
        for i in range(1, 13):
            f = f"F{i}"

            if f in ["F4", "F6", "F8", "F10"]:
                cells += "<td style='background:#fff2cc'>REM</td>"
            else:
                cells += f"<td>{stats.get(f, 0)}</td>"

        filter_rows += f"<tr><td><b>{r['fn']}</b></td>{cells}</tr>"

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>QuickCell vs QuickCell-8</title>
<style>
body {{
    font-family: Segoe UI, sans-serif;
    background: #f5f7fa;
    padding: 30px;
    color: #2c3e50;
}}
h1 {{
    color: #1a237e;
    border-bottom: 3px solid #1a237e;
    padding-bottom: 8px;
}}
h2 {{
    color: #283593;
    margin-top: 35px;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    margin: 20px 0;
}}
th, td {{
    padding: 10px 14px;
    text-align: center;
    border: 1px solid #e0e0e0;
}}
th {{
    background: #1a237e;
    color: white;
}}
tr:nth-child(even) {{
    background: #f9f9f9;
}}
.note {{
    background: #fff2cc;
    border-left: 5px solid #d6b656;
    padding: 12px;
    margin: 20px 0;
}}
.warning {{
    background: #f4cccc;
    border-left: 5px solid #cc0000;
    padding: 12px;
    margin: 20px 0;
}}
img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 20px auto;
    background: white;
    padding: 10px;
}}
</style>
</head>
<body>

<h1>QuickCell vs QuickCell-8 Performance Report</h1>

<div class="note">
<b>QuickCell-8 definition:</b>
This version uses 8 filters. F4, F6, F8, and F10 are removed because they caused
over-pruning in the current toy benchmark.
</div>

<div class="warning">
<b>Important:</b>
This is still a debugging-scale benchmark with only 35 layouts.
If |L*| remains zero, the issue is most likely the toy geometry/model,
not only the pruning filters. For final paper-level results, use a calibrated
SiDB geometry and an exact physical simulator.
</div>

<h2>1. Headline Results</h2>
<table>
<tr>
<th>Function</th>
<th>|Ld|</th>
<th>P1</th>
<th>P2</th>
<th>P3</th>
<th>|L*| 3-f</th>
<th>t3</th>
<th>|L*| 8-f</th>
<th>t8</th>
<th>Speedup</th>
</tr>
{rows}
</table>

<h2>2. Per-Filter Breakdown</h2>
<table>
<tr>
<th>Function</th>
<th>F1</th><th>F2</th><th>F3</th><th>F4</th><th>F5</th>
<th>F6</th><th>F7</th><th>F8</th><th>F9</th>
<th>F10</th><th>F11</th><th>F12</th>
</tr>
{filter_rows}
</table>

<h2>3. Runtime Comparison</h2>
<img src="runtime_comparison.png">

<h2>4. Search Space Reduction</h2>
<img src="search_space_reduction.png">

<h2>5. Filter Breakdown</h2>
<img src="filter_breakdown.png">

<h2>6. Correct Interpretation</h2>
<ul>
<li>QuickCell original uses 3 filters: F4, F11, and F12.</li>
<li>QuickCell-8 uses 8 filters: F1, F2, F3, F5, F7, F9, F11, and F12.</li>
<li>F4, F6, F8, and F10 are intentionally removed in this debugging version.</li>
<li>If no valid implementation is found, the toy layout is not physically suitable for the target function.</li>
<li>The observed speedup is a debugging/runtime effect and should not be interpreted as final scalability evidence.</li>
</ul>

</body>
</html>
"""

    path = os.path.join(OUT_DIR, "quickcell8_report.html")

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    results = run_all()

    print_table(results)

    save_csv(results)
    plot_runtime_comparison(results)
    plot_search_space_reduction(results)
    plot_filter_breakdown(results)
    write_html(results)

    print("\nReport generated successfully.")
    print("Output folder:")
    print(os.path.abspath(OUT_DIR))


if __name__ == "__main__":
    main()