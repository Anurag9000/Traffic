# 🏁 Traffic Simulator: Scenarios Execution Guide

This document provides exhaustive instructions on how to run various simulation scenarios, from directional rush-hour models to targeted real-world navigation.

---

## 🚦 1. Directional "Rush Hour" Mode
Simulates asymmetric demand (e.g., morning/evening peaks) at a single intersection.

### Standard Rush Hour (N-S Heavy)
- **Description**: North and South approaches have 4.0x base flow; West approach has a 5.0x bias for Right turns.
- **Config**: `configs/rush_hour.json`
- **Command**:
  ```bash
  python run_directional.py --config configs/rush_hour.json
  ```
- **What it does**: Runs a comparison between **FIXED** and **DYNAMIC** (Adaptive) control modes and prints the efficiency improvement.

---

## 🎯 2. Targeted Navigation Modes
Vehicles are assigned a specific (x, y) destination and use smart routing to reach it, vanishing upon arrival.

### A. Real-World Target (Delhi Map)
- **Description**: Navigates vehicles through the Delhi (Connaught Place) map toward a specific Lat/Lon.
- **Config**: `configs/delhi_targeted.json`
- **Command**:
  ```bash
  python run_real_targeted.py --config configs/delhi_targeted.json
  ```
- **CLI Overrides**:
  ```bash
  python run_real_targeted.py --rate 0.5 --duration 3600
  ```

### B. Synthetic Grid Target
- **Description**: 10x10 Grid where 80% of cars target the center intersection.
- **Config**: `configs/grid_targeted.json`
- **Command**:
  ```bash
  python run_grid_targeted.py --config configs/grid_targeted.json
  ```

---

## 🗺️ 3. Map-Wide Baseline Simulations
Standard uniform spawning across boundaries for general capacity testing.

### Real Delhi Baseline
- **Run**: `python traffic_real_simulation.py`
- **Options**:
  - `--spawn 0.2`: Sets arrival rate per entry lane.
  - `--duration 1800`: Half-hour simulation.

### Grid Baseline
- **Run**: `python traffic_grid_simulation.py`
- **Note**: Currently defaults to a 5x5 grid with uniform boundary spawning.

---

## 🧪 4. Advanced Experiments (YAML)
The `configs/experiments` directory contains complex physics and behavioral sweeps.

### Physics Tuning (Aggressive vs. Standard)
- **Description**: Compares different IDM/Kinematic settings.
- **Configs**: `configs/physics/aggressive.yaml`, `configs/physics/standard.yaml`
- **Usage**: (Dependent on specific experiment runners like `speed_threshold.py`)

### Speed Sweep
- **Config**: `configs/experiments/speed_sweep_plan.yaml`
- **Run**: `python traffic_grid/experiments/speed_threshold.py` (Verify internal paths before running).

---

## 🛠️ Configuration Quick-Reference

### JSON Schema for Directional
```json
{
  "spawn_rate": 0.1,
  "flow_biases": { "north_incoming": 4.0 }, 
  "turn_biases": {
    "overrides": { "west_incoming": { "right": 5.0 } }
  }
}
```

### JSON Schema for Targeted
```json
{
  "target": { "lat": 28.63, "lon": 77.21 },
  "target_ratio": 0.8,
  "spawn_rate": 0.5
}
```

---

> [!TIP]
> **Check the Results**: All results (CSV/Logs) are saved in the `results/` directory, categorized by mode (e.g., `results/directional/`, `results/targeted/`).
