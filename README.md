
# ⚛️ QuickCell-12

> **Physics-Based Pruning Framework for Silicon Dangling Bond (SiDB) Logic Cell Discovery**

![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Research](https://img.shields.io/badge/Research-SiDB-red)
![Status](https://img.shields.io/badge/Status-Research-orange)

---

## 📖 Overview

QuickCell-12 is a research framework for discovering **Silicon Dangling Bond (SiDB)** logic cells using a multi-stage physics-aware pruning strategy.

Instead of performing expensive electrostatic simulations for every candidate layout, QuickCell-12 progressively removes infeasible layouts through a sequence of analytical filters before physical validation.

The framework supports both **2-input** and **3-input** logic gates and exports final candidates for **SiQAD** validation.

---

## ✨ Features

- Physics-based pruning
- Electrostatic analysis
- Parallel candidate evaluation
- SiQAD export
- Configurable pruning parameters
- Automatic report generation
- Support for 1, 2 and 3-input logic gates

---

## 🏗 Pipeline

```text
Random Layout Generation
          │
          ▼
 Phase I  (Geometric Filters)
          │
          ▼
 Phase II (Electrostatic Filters)
          │
          ▼
 Phase III (Physical Validation)
          │
          ▼
 Candidate Ranking
          │
          ▼
      SiQAD Export
```

---

## 🔬 Filter Overview

| Filter | Description |
|---------|-------------|
| F1 | Minimum Distance Pruning |
| F2 | Duplicate Layout Removal |
| F3 | Connectivity Check |
| F4 | Positive Charge Pruning |
| F5 | Charge Count Bound |
| F6 | Input Disturbance |
| F7 | Electrostatic Connectivity |
| F8 | Output Potential Bound |
| F9 | Output Pressure |
| F10 | Energy Bound |
| F11 | Physical Feasibility |
| F12 | I/O Stability |

---

## 📂 Repository Structure

```text
QuickCell-12/
│
├── filters/
├── exporters/
├── reports/
├── validation/
├── utils/
├── run_gate_report.py
├── export_siqad_validation.py
└── README.md
```

---

## 🚀 Usage

Run a single gate:

```bash
python run_gate_report.py --gate AND3
```

Run all gates:

```bash
python run_gate_report.py --gate ALL
```

Export layouts for SiQAD:

```bash
python export_siqad_validation.py --gate ALL
```

---

## ⚙ Supported Gates

### 2-Input Gates

- AND
- NAND
- OR
- NOR
- XOR
- XNOR
- LT
- GT
- LE
- GE
- CX
- HALF ADDER
- DOUBLE WIRE
- WIRE
- INV

### 3-Input Gates

- AND3
- XOR3
- MAJ
- ONEHOT
- ITE
- DOT
- GAMBLE
- XOR-AND
- OR-AND
- AND-XOR

---

## 📊 Design Philosophy

QuickCell-12 follows a **conservative pruning strategy**.

Each filter removes layouts that violate physical or electrostatic constraints while preserving potentially valid candidates for later validation.

This significantly reduces the search space and computational cost before SiQAD simulation.

---

## 📚 Citation

If you use this project in your research, please cite:

```bibtex
@misc{QuickCell12,
  title={QuickCell-12: Physics-Based Pruning Framework for Silicon Dangling Bond Logic Cell Discovery},
  year={2026}
}
```

---

## 📄 License

This project is released under the MIT License.

---

## ⭐ Acknowledgment

QuickCell-12 was developed for research in:

- Silicon Dangling Bond Computing
- Atomic-Scale Logic Design
- Nanoelectronics
- Physics-Aware Design Automation

---

<p align="center">
Made with ❤️ for Atomic-Scale Computing
</p>
