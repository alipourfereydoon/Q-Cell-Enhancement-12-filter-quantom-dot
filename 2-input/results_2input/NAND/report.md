# QuickCell-12 Report (2-input): NAND

## Table I

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected | Candidates | Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NAND | 156849 | 100000 | 92713 | 92713 | 79116 | 79116 | 53980 | 39126 | 39126 | 16580 | 8085 | 4111 | 4111 | 28 |  | 28 | 771.3124 |


## Table II

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 79116 | 79.116 | 20.884 | 1.264 |  |
| Phase 2 | F5-F10 | 79116 | 4111 | 5.1962 | 94.8038 | 19.245 |  |
| Phase 3 | F11-F12 | 4111 | 28 | 0.6811 | 99.3189 | 146.8214 |  |
| Total | F1-F12 | 100000 | 28 | 0.028 | 99.972 | 3571.4286 | 771.3124 |


## Table III

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 100000 | 79116 | 1.26x fewer |
| Before expensive enumerative pruning | 100000 | 4111 | 24.32x fewer |
| Before final verification | 2855 | 28 | 101.96x fewer |
| Candidate implementations | 2855 | 28 | 101.96x fewer |
| Search-space reduction | 35.0263 | 3571.4286 | 101.96x fewer |


## Speedup

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 156849 |
| Input patterns (4) | 4 |
| Assumed sim time per layout/input [s] | 0.01 |
| Estimated brute-force (sample) [s] | 4000.0 |
| Estimated brute-force (full) [s] | 6273.96 |
| QC-3 candidates | 2855 |
| QuickCell-12 candidates | 28 |
| Candidate reduction over QC-3 | 101.9643x |
| Wall time [s] | 771.3124 |