# QuickCell-12 Limited-run Report: ONEHOT

## Table I — Ablation Results

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected Candidates | Candidates | Total Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ONEHOT | 16701685 | 100000 | 85282 | 42816 | 40439 | 40261 | 29537 | 14656 | 4445 | 2253 | 979 | 633 | 633 | 2 |  | 2 | 940.077 |


## Table II — Phase-wise Summary

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 40261 | 40.261 | 59.739 | 2.4838 |  |
| Phase 2 | F5-F10 | 40261 | 633 | 1.5722 | 98.4278 | 63.6035 |  |
| Phase 3 | F11-F12 | 633 | 2 | 0.316 | 99.684 | 316.5 |  |
| Total | F1-F12 | 100000 | 2 | 0.002 | 99.998 | 50000.0 | 940.077 |


## Table III — Original QC-3 vs QuickCell-12

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 99409 | 40261 | 2.47x fewer |
| Before expensive enumerative pruning | 99409 | 633 | 157.04x fewer |
| Before final verification | 6639 | 2 | 3319.50x fewer |
| Candidate implementations | 6639 | 2 | 3319.50x fewer |
| Search-space reduction | 15.0625 | 50000.0 | 3319.50x fewer |


## Numerical Speedup Calculation

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 16701685 |
| Input patterns for 3-input gate | 8 |
| Assumed simulation time per layout/input [s] | 0.01 |
| Estimated brute-force time for processed sample [s] | 8000.0 |
| Estimated brute-force time for full |Ld| [s] | 1336134.8 |
| QC-3 candidates before verification | 6639 |
| QuickCell-12 candidates before verification | 2 |
| QuickCell-12 candidate reduction over QC-3 | 3319.5000x |
| Measured QuickCell-12 wall time [s] | 940.077 |


**Note:** This is a limited-run / sampling-based evaluation.
