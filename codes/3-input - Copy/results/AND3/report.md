# QuickCell-12 Limited-run Report: AND3

## Table I — Ablation Results

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected Candidates | Candidates | Total Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AND3 | 16701685 | 500 | 240 | 240 | 128 | 93 | 93 | 18 | 18 | 18 | 17 | 8 | 8 | 1 |  | 1 | 29.4293 |


## Table II — Phase-wise Summary

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 500 | 93 | 18.6 | 81.4 | 5.3763 |  |
| Phase 2 | F5-F10 | 93 | 8 | 8.6022 | 91.3978 | 11.625 |  |
| Phase 3 | F11-F12 | 8 | 1 | 12.5 | 87.5 | 8.0 |  |
| Total | F1-F12 | 500 | 1 | 0.2 | 99.8 | 500.0 | 29.4293 |


## Table III — Original QC-3 vs QuickCell-12

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 500 | 500 | same |
| After early pruning / Phase 1 | 222 | 93 | 2.39x fewer |
| Before expensive enumerative pruning | 222 | 8 | 27.75x fewer |
| Before final verification | 14 | 1 | 14.00x fewer |
| Candidate implementations | 14 | 1 | 14.00x fewer |
| Search-space reduction | 35.7143 | 500.0 | 14.00x fewer |


## Numerical Speedup Calculation

| Quantity | Value |
| --- | --- |
| Processed layouts | 500 |
| Full search space |Ld| | 16701685 |
| Input patterns for 3-input gate | 8 |
| Assumed simulation time per layout/input [s] | 0.01 |
| Estimated brute-force time for processed sample [s] | 40.0 |
| Estimated brute-force time for full |Ld| [s] | 1336134.8 |
| QC-3 candidates before verification | 14 |
| QuickCell-12 candidates before verification | 1 |
| QuickCell-12 candidate reduction over QC-3 | 14.0000x |
| Measured QuickCell-12 wall time [s] | 29.4293 |


**Note:** This is a limited-run / sampling-based evaluation.
