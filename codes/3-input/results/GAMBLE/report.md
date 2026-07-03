# QuickCell-12 Limited-run Report: GAMBLE

## Table I — Ablation Results

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected Candidates | Candidates | Total Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GAMBLE | 16701685 | 100000 | 52605 | 52605 | 30317 | 22580 | 19637 | 6722 | 6722 | 6718 | 5718 | 2591 | 2591 | 2 |  | 2 | 1076.6238 |


## Table II — Phase-wise Summary

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 22580 | 22.58 | 77.42 | 4.4287 |  |
| Phase 2 | F5-F10 | 22580 | 2591 | 11.4748 | 88.5252 | 8.7148 |  |
| Phase 3 | F11-F12 | 2591 | 2 | 0.0772 | 99.9228 | 1295.5 |  |
| Total | F1-F12 | 100000 | 2 | 0.002 | 99.998 | 50000.0 | 1076.6238 |


## Table III — Original QC-3 vs QuickCell-12

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 47022 | 22580 | 2.08x fewer |
| Before expensive enumerative pruning | 47022 | 2591 | 18.15x fewer |
| Before final verification | 13 | 2 | 6.50x fewer |
| Candidate implementations | 13 | 2 | 6.50x fewer |
| Search-space reduction | 7692.3077 | 50000.0 | 6.50x fewer |


## Numerical Speedup Calculation

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 16701685 |
| Input patterns for 3-input gate | 8 |
| Assumed simulation time per layout/input [s] | 0.01 |
| Estimated brute-force time for processed sample [s] | 8000.0 |
| Estimated brute-force time for full |Ld| [s] | 1336134.8 |
| QC-3 candidates before verification | 13 |
| QuickCell-12 candidates before verification | 2 |
| QuickCell-12 candidate reduction over QC-3 | 6.5000x |
| Measured QuickCell-12 wall time [s] | 1076.6238 |


**Note:** This is a limited-run / sampling-based evaluation.
