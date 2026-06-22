# QuickCell-12 Limited-run Report: OR-AND

## Table I — Ablation Results

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected Candidates | Candidates | Total Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OR-AND | 16701685 | 100000 | 85282 | 85282 | 80504 | 80175 | 58857 | 29353 | 8925 | 4485 | 1957 | 1321 | 1321 | 8 |  | 8 | 1656.9904 |


## Table II — Phase-wise Summary

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 80175 | 80.175 | 19.825 | 1.2473 |  |
| Phase 2 | F5-F10 | 80175 | 1321 | 1.6476 | 98.3524 | 60.6927 |  |
| Phase 3 | F11-F12 | 1321 | 8 | 0.6056 | 99.3944 | 165.125 |  |
| Total | F1-F12 | 100000 | 8 | 0.008 | 99.992 | 12500.0 | 1656.9904 |


## Table III — Original QC-3 vs QuickCell-12

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 99409 | 80175 | 1.24x fewer |
| Before expensive enumerative pruning | 99409 | 1321 | 75.25x fewer |
| Before final verification | 6650 | 8 | 831.25x fewer |
| Candidate implementations | 6650 | 8 | 831.25x fewer |
| Search-space reduction | 15.0376 | 12500.0 | 831.25x fewer |


## Numerical Speedup Calculation

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 16701685 |
| Input patterns for 3-input gate | 8 |
| Assumed simulation time per layout/input [s] | 0.01 |
| Estimated brute-force time for processed sample [s] | 8000.0 |
| Estimated brute-force time for full |Ld| [s] | 1336134.8 |
| QC-3 candidates before verification | 6650 |
| QuickCell-12 candidates before verification | 8 |
| QuickCell-12 candidate reduction over QC-3 | 831.2500x |
| Measured QuickCell-12 wall time [s] | 1656.9904 |


**Note:** This is a limited-run / sampling-based evaluation.
