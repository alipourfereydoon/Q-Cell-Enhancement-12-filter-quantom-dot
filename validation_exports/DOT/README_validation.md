# SiQAD Validation Package for DOT

Open `candidate.sqd` in each candidate folder.

Use `all_sidbs.csv` to identify IN/OUT BDL pairs.

Fill `validation_sheet.csv` after SiQAD simulation.

BDL encoding used by this prototype:

- bit 0: pos_a = -1, pos_b = 0
- bit 1: pos_a = 0, pos_b = -1

After filling the validation sheet, run:

```bash
python analyze_siqad_results.py --sheet validation_exports/<GATE>/validation_sheet.csv
```