# analyze_siqad_results.py

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from glob import glob


TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "y",
    "ok",
    "pass",
    "passed",
}

FALSE_VALUES = {
    "0",
    "false",
    "no",
    "n",
    "fail",
    "failed",
}


def parse_bool(value: str):
    value = str(value).strip().lower()

    if value in TRUE_VALUES:
        return True

    if value in FALSE_VALUES:
        return False

    return None


def is_blank_row(row: dict) -> bool:
    if row is None:
        return True

    for v in row.values():
        if str(v).strip() != "":
            return False

    return True


def safe_int_key(value: str):
    value = str(value).strip()

    try:
        return (0, int(value))
    except Exception:
        return (1, value)


def analyze_sheet(path: str, quiet: bool = False):
    rows = []
    warnings = []

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        required_columns = {
            "gate",
            "candidate_id",
            "input_bits",
            "expected_output",
            "observed_output",
            "io_integrity_ok",
            "siqad_file",
            "notes",
        }

        if reader.fieldnames is None:
            raise RuntimeError(f"CSV file has no header row: {path}")

        missing_cols = required_columns - set(reader.fieldnames)

        if missing_cols:
            raise RuntimeError(
                f"CSV file {path} is missing required columns: "
                + ", ".join(sorted(missing_cols))
            )

        for line_no, row in enumerate(reader, start=2):
            if is_blank_row(row):
                continue

            cid = str(row.get("candidate_id", "")).strip()

            if cid == "":
                warnings.append(
                    f"Line {line_no}: skipped row with empty candidate_id."
                )
                continue

            input_bits = str(row.get("input_bits", "")).strip()

            if input_bits == "":
                warnings.append(
                    f"Line {line_no}: skipped row with empty input_bits."
                )
                continue

            rows.append(row)

    if not rows:
        if not quiet:
            print(f"No valid rows found in validation sheet: {path}")
        return {
            "sheet": path,
            "gate": "",
            "valid_rows": 0,
            "filled_rows": 0,
            "candidates": 0,
            "passed_candidates": 0,
            "failed_or_incomplete_candidates": 0,
            "summary_path": "",
        }

    by_candidate = defaultdict(list)

    for row in rows:
        cid = str(row["candidate_id"]).strip()
        by_candidate[cid].append(row)

    summary = []
    gate_name = str(rows[0].get("gate", "")).strip()

    for cid, items in sorted(by_candidate.items(), key=lambda x: safe_int_key(x[0])):
        total = len(items)
        filled = 0
        correct = 0
        integrity_ok_count = 0
        missing = False

        failed_inputs = []
        incomplete_inputs = []

        for row in items:
            input_bits = str(row.get("input_bits", "")).strip()
            expected = str(row.get("expected_output", "")).strip()
            observed = str(row.get("observed_output", "")).strip()

            integrity_raw = str(row.get("io_integrity_ok", "")).strip()
            integrity = parse_bool(integrity_raw)

            if observed == "":
                missing = True
                incomplete_inputs.append(input_bits)
                continue

            if integrity is None:
                missing = True
                incomplete_inputs.append(input_bits)
                continue

            filled += 1

            output_correct = observed == expected

            if output_correct:
                correct += 1
            else:
                failed_inputs.append(input_bits)

            if integrity:
                integrity_ok_count += 1
            else:
                if input_bits not in failed_inputs:
                    failed_inputs.append(input_bits)

        pass_candidate = (
            not missing
            and filled == total
            and correct == total
            and integrity_ok_count == total
        )

        summary.append({
            "gate": gate_name,
            "candidate_id": cid,
            "total_inputs": total,
            "filled_inputs": filled,
            "correct_outputs": correct,
            "io_integrity_ok": integrity_ok_count,
            "candidate_pass": pass_candidate,
            "failed_inputs": " ".join(failed_inputs),
            "incomplete_inputs": " ".join(incomplete_inputs),
        })

    out_dir = os.path.dirname(path)

    summary_path = os.path.join(
        out_dir,
        "siqad_validation_summary.csv",
    )

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "gate",
            "candidate_id",
            "total_inputs",
            "filled_inputs",
            "correct_outputs",
            "io_integrity_ok",
            "candidate_pass",
            "failed_inputs",
            "incomplete_inputs",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    total_candidates = len(summary)
    passed = sum(1 for row in summary if row["candidate_pass"])
    failed_or_incomplete = total_candidates - passed

    total_rows = len(rows)
    filled_rows = sum(
        1
        for row in rows
        if str(row.get("observed_output", "")).strip() != ""
        and parse_bool(row.get("io_integrity_ok", "")) is not None
    )

    result = {
        "sheet": path,
        "gate": gate_name,
        "valid_rows": total_rows,
        "filled_rows": filled_rows,
        "candidates": total_candidates,
        "passed_candidates": passed,
        "failed_or_incomplete_candidates": failed_or_incomplete,
        "summary_path": summary_path,
    }

    if not quiet:
        print("=" * 80)
        print("SiQAD validation analysis")
        print(f"Sheet: {path}")
        print(f"Gate: {gate_name}")
        print(f"Valid input rows: {total_rows}")
        print(f"Filled rows: {filled_rows}")
        print(f"Candidates: {total_candidates}")
        print(f"Passed candidates: {passed}")
        print(f"Failed or incomplete candidates: {failed_or_incomplete}")
        print(f"Summary CSV: {summary_path}")
        print("=" * 80)

    return result


def analyze_all(root: str):
    pattern = os.path.join(root, "*", "validation_sheet.csv")
    sheets = sorted(glob(pattern))

    if not sheets:
        print(f"No validation_sheet.csv files found under: {root}")
        return

    results = []

    for sheet in sheets:
        res = analyze_sheet(sheet, quiet=True)
        results.append(res)

    out_path = os.path.join(root, "all_gates_siqad_validation_summary.csv")

    fieldnames = [
        "gate",
        "sheet",
        "valid_rows",
        "filled_rows",
        "candidates",
        "passed_candidates",
        "failed_or_incomplete_candidates",
        "summary_path",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    print("=" * 80)
    print("All-gate SiQAD validation summary")
    print(f"Root: {root}")
    print(f"Sheets analyzed: {len(sheets)}")
    print(f"Combined summary: {out_path}")
    print("=" * 80)

    for r in results:
        print(
            f"{r['gate']}: "
            f"passed {r['passed_candidates']}/{r['candidates']} candidates, "
            f"filled rows {r['filled_rows']}/{r['valid_rows']}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Analyze filled SiQAD validation sheet(s)."
    )

    parser.add_argument("--sheet", default="")
    parser.add_argument("--root", default="validation_exports")
    parser.add_argument("--all", action="store_true")

    args = parser.parse_args()

    if args.all:
        analyze_all(args.root)
    else:
        if not args.sheet:
            raise RuntimeError("Please provide --sheet or use --all.")

        analyze_sheet(args.sheet)


if __name__ == "__main__":
    main()