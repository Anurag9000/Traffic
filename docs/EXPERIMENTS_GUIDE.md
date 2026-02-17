# Running Traffic Simulation Experiments

This guide details how to run the various simulation experiments and configurations using the integrated runners.

## 1. Comparison Tests (Proper Scientific Tests)

These scripts run specific scientific comparisons and output statistical results directly to the terminal/CSV.

### **Biased Flow Comparison (Fixed vs Dynamic)**
Runs a single intersection simulation with heavy N-S traffic and light E-W traffic, comparing constant-time signals against adaptive signals.
```bash
python tests/compare_biased_flow.py
```
**Expected Output:** Terminal output showing progress for both modes (in parallel) and a final percentage improvement summary.

### **Velocity Threshold Experiment**
Tests how maximum speed limits affect network throughput and travel times.
```bash
python traffic_grid/experiments/speed_threshold_fixed.py
```

---

## 2. Running YAML Configurations

All YAML configurations in `configs/experiments/` are now fully integrated with the runners.

### **Grid Simulations (10x10 Network)**

**Fixed Signal Control:**
```bash
python -m traffic_grid.python_sim.main --mode grid --config configs/experiments/grid_fixed.yaml
```

**Dynamic Signal Control:**
```bash
python -m traffic_grid.python_sim.main --mode grid --config configs/experiments/grid_dynamic.yaml
```

**Targeted (Vehicles heading to center):**
```bash
python -m traffic_grid.python_sim.main --mode grid --config configs/experiments/grid_target.yaml
```

### **Intersection Simulations (Single Node)**

**Baseline (Adaptive):**
```bash
python traffic_intersection/python_sim/runner.py --config configs/experiments/intersection_baseline.yaml
```

**Targeted/Biased Flow:**
```bash
python traffic_intersection/python_sim/runner.py --config configs/experiments/intersection_targeted.yaml
```
*(Note: This uses the newly integrated `control_mode` and `lane_biases` support in the intersection runner)*

### **Real Map Simulations (Delhi)**

**Untargeted (General Flow):**
```bash
python traffic_real/runner.py --run-config configs/experiments/real_delhi_untargeted.yaml
```

**Targeted (Connaught Place):**
```bash
python traffic_real/runner.py --run-config configs/experiments/real_delhi_targeted.yaml
```

**Fixed Signal Control:**
```bash
python traffic_real/runner.py --run-config configs/experiments/real_delhi_fixed.yaml
```

---

## 3. Command Line Arguments

You can override YAML settings using CLI arguments:

**Grid Runner (`traffic_grid.python_sim.main`):**
- `--mode`: `grid`, `dynamic`, `constant`
- `--spawn-rate`: Vehicles per second
- `--speedup`: Visualization speedup (e.g., 10.0)
- `--config`: Path to YAML config

**Intersection Runner (`traffic_intersection.python_sim.runner`):**
- `--duration`: Simulation seconds
- `--spawn-rate`: Vehicles per second
- `--config`: Path to YAML config
- `--output-dir`: Where to save CSVs

**Real Runner (`traffic_real.runner`):**
- `--run-config`: Path to YAML config
- `--map-filter`: `backbone` or `all`
- `--api-key`: TomTom API key (optional)
