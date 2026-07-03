# QuickCell-12 Report (2-input): CX

## Table I

| Benchmark | |Ld| | Processed | After F1 | After F2 | After F3 | After F4 | After F5 | After F6 | After F7 | After F8 | After F9 | After F10 | After F11 | After F12 | Selected | Candidates | Time [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CX | 1072445 | 100000 | 94606 | 94606 | 90086 | 90086 | 70860 | 60908 | 60908 | 7585 | 858 | 203 | 203 | 0 |  | 0 | 567.1707 |


## Table II

| Phase | Filters | Input Layouts | Output Layouts | Retention Ratio [%] | Pruning Ratio [%] | Reduction Factor | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 | F1-F4 | 100000 | 90086 | 90.086 | 9.914 | 1.1101 |  |
| Phase 2 | F5-F10 | 90086 | 203 | 0.2253 | 99.7747 | 443.7734 |  |
| Phase 3 | F11-F12 | 203 | 0 | 0.0 | 100.0 | inf |  |
| Total | F1-F12 | 100000 | 0 | 0.0 | 100.0 | inf | 567.1707 |


## Table III

| Metric | Original QC-3 | QuickCell-12 | Improvement |
| --- | --- | --- | --- |
| Number of pruning filters | 3 | 12 | 4.0x more |
| Processed layouts | 100000 | 100000 | same |
| After early pruning / Phase 1 | 100000 | 90086 | 1.11x fewer |
| Before expensive enumerative pruning | 100000 | 203 | 492.61x fewer |
| Before final verification | 0 | 0 | inf |
| Candidate implementations | 0 | 0 | inf |
| Search-space reduction | inf | inf | inf |


## Speedup

| Quantity | Value |
| --- | --- |
| Processed layouts | 100000 |
| Full search space |Ld| | 1072445 |
| Input patterns (4) | 4 |
| Assumed sim time per layout/input [s] | 0.01 |
| Estimated brute-force (sample) [s] | 4000.0 |
| Estimated brute-force (full) [s] | 42897.8 |
| QC-3 candidates | 0 |
| QuickCell-12 candidates | 0 |
| Candidate reduction over QC-3 | inf |
| Wall time [s] | 567.1707 |