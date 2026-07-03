# main_2input.py
print("=" * 70)
print("QuickCell-12 for 2-input gates")
print("=" * 70)
print()

# ── All 2-input gates in the table ──
print("Available gates:")
print("  2-in 1-out : AND, NAND, OR, NOR, XOR, XNOR, LT, GT, LE, GE")
print("  2-in 2-out : DOUBLE_WIRE, CX, HA")
print("  1-in 1-out : WIRE, INV")
print()

# ── Run single gate ──
print("Run a single gate (tables only):")
print("  python run_gate_report_2input.py --gate AND --samples 100000 "
      "--workers 4 --strict-profile balanced")
print()

# ── Run all gates ──
print("Run ALL gates:")
print("  python run_gate_report_2input.py --gate ALL --samples 100000 "
      "--workers 4 --strict-profile balanced")
print()

# ── Export SiQAD files ──
print("Export SiQAD validation files for a single gate:")
print("  python export_siqad_validation_2input.py --gate AND "
      "--samples 100000 --workers 4 --max-candidates 20")
print()

# ── Export ALL gates ──
print("Export SiQAD for ALL gates:")
print("  python export_siqad_validation_2input.py --gate ALL "
      "--samples 100000 --workers 4 --max-candidates 20")
print()

# ── Analyze ──
print("Analyze validation sheets:")
print("  python analyze_siqad_results.py "
      "--root validation_exports_2input --all")
print()
print("=" * 70)