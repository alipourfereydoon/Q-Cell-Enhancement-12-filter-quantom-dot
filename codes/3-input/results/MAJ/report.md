# QuickCell-12 Limited-run Report: MAJ

## Table I — Ablation Results

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected Candidates | Candidates | Total Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAJ | 16701685 | 100000 | 52605 | 52605 | 30317 | 22580 | 19637 | 6722 | 6722 | 6717 | 5717 | 2588 | 2588 | 3 |  | 3 | 1296.5222 |


## Table II — Phase-wise Summary

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 22580 | 22.58 | 77.42 | 4.4287 |  |
| Phase 2 | F5-F10 | 22580 | 2588 | 11.4615 | 88.5385 | 8.7249 |  |
| Phase 3 | F11-F12 | 2588 | 3 | 0.1159 | 99.8841 | 862.6667 |  |
| Total | F1-F12 | 100000 | 3 | 0.003 | 99.997 | 33333.3333 | 1296.5222 |


## Table III — Original QC-3 vs QuickCell-12

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 47022 | 22580 | 2.08x fewer |
| Before expensive enumerative pruning | 47022 | 2588 | 18.17x fewer |
| Before final verification | 7 | 3 | 2.33x fewer |
| Candidate implementations | 7 | 3 | 2.33x fewer |
| Search-space reduction | 14285.7143 | 33333.3333 | 2.33x fewer |


## Numerical Speedup Calculation

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 16701685 |
| Input patterns for 3-input gate | 8 |
| Assumed simulation time per layout/input [s] | 0.01 |
| Estimated brute-force time for processed sample [s] | 8000.0 |
| Estimated brute-force time for full |Ld| [s] | 1336134.8 |
| QC-3 candidates before verification | 7 |
| QuickCell-12 candidates before verification | 3 |
| QuickCell-12 candidate reduction over QC-3 | 2.3333x |
| Measured QuickCell-12 wall time [s] | 1296.5222 |


**Note:** This is a limited-run / sampling-based evaluation.
