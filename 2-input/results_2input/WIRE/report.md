# QuickCell-12 Report (2-input): WIRE

## Table I

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected | Candidates | Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WIRE | 1774630 | 100000 | 95189 | 95189 | 88738 | 88738 | 88589 | 78524 | 78524 | 14841 | 4649 | 2328 | 2328 | 16 |  | 16 | 242.313 |


## Table II

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 88738 | 88.738 | 11.262 | 1.1269 |  |
| Phase 2 | F5-F10 | 88738 | 2328 | 2.6235 | 97.3765 | 38.1177 |  |
| Phase 3 | F11-F12 | 2328 | 16 | 0.6873 | 99.3127 | 145.5 |  |
| Total | F1-F12 | 100000 | 16 | 0.016 | 99.984 | 6250.0 | 242.313 |


## Table III

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 100000 | 88738 | 1.13x fewer |
| Before expensive enumerative pruning | 100000 | 2328 | 42.96x fewer |
| Before final verification | 3088 | 16 | 193.00x fewer |
| Candidate implementations | 3088 | 16 | 193.00x fewer |
| Search-space reduction | 32.3834 | 6250.0 | 193.00x fewer |


## Speedup

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 1774630 |
| Input patterns (2) | 2 |
| Assumed sim time per layout/input [s] | 0.01 |
| Estimated brute-force (sample) [s] | 2000.0 |
| Estimated brute-force (full) [s] | 35492.6 |
| QC-3 candidates | 3088 |
| QuickCell-12 candidates | 16 |
| Candidate reduction over QC-3 | 193.0000x |
| Wall time [s] | 242.313 |