# Traffic Simulator - Usage Guide

## 🚀 Quick Start

### Installation
```bash
cd D:\TrafficSim
pip install cupy-cuda12x  # For GPU acceleration (optional)
pip install numpy networkx pyyaml
```

### Basic Usage
```bash
# Grid simulation
python -m scenarios.cli grid --size 5 --rate 0.2 --duration 3600

# Intersection simulation
python -m scenarios.cli intersection --rate 0.5 --duration 3600

# Real map simulation
python -m scenarios.cli real --map delhi --rate 0.3 --duration 3600
```

---

## 📋 All Simulation Modes

### 1. Grid Simulation (NxN Intersections)

**Basic Grid**
```bash
python -m scenarios.cli grid --size 5 --rate 0.2 --duration 3600
```

**Grid with Adaptive Control**
```bash
python -m scenarios.cli grid --size 5 --rate 0.2 --adaptive --duration 3600
```

**Grid with Targeted Spawning**
```bash
python scenarios/grid_targeted.py
```

**Configuration**: Uses `configs/default.yaml` → `experiments.grid_baseline`

---

### 2. Single Intersection

**Basic Intersection**
```bash
python -m scenarios.cli intersection --rate 0.5 --duration 3600
```

**Intersection with Adaptive Control**
```bash
python -m scenarios.cli intersection --rate 0.5 --adaptive --duration 3600
```

**Intersection with Directional Spawning (Rush Hour)**
```bash
python scenarios/intersection_directional.py
```

**Configuration**: Uses `configs/default.yaml` → `experiments.intersection_baseline`

---

### 3. Real Map Simulation (OSMnx)

**Real Map (Delhi)**
```bash
python -m scenarios.cli real --map delhi --rate 0.3 --duration 3600
```

**Real Map with Adaptive Control**
```bash
python -m scenarios.cli real --map delhi --rate 0.3 --adaptive --duration 3600
```

**Real Map with Targeted Spawning**
```bash
python scenarios/real_map_runner.py
```

**Configuration**: Uses `configs/default.yaml` → `experiments.real_delhi`

---

## 🎛️ Spawning Strategies

### Uniform (Poisson)
Default spawning - random vehicle arrival times following Poisson distribution.

```python
from core import Spawner
spawner = Spawner(mode='uniform', mean_rate=0.5, variation=0.2)
```

### Targeted (Destination-Based)
Vehicles spawn with specific destination targets.

```python
from core import Spawner, LaneMap
spawner = Spawner(mode='targeted', lane_map=lane_map, mean_rate=0.5)
```

### Directional (Rush Hour)
Lane-specific spawn rates to simulate rush hour traffic.

```python
from core import Spawner
lane_biases = {0: 2.0, 1: 0.5}  # Lane 0 gets 2x, Lane 1 gets 0.5x
spawner = Spawner(mode='directional', mean_rate=0.5, lane_biases=lane_biases)
```

---

## 🚦 Signal Control Modes

### Fixed Timing
Pre-defined green/yellow/red times.

```python
from core import SignalControllerVector, MODE_FIXED
signals = SignalControllerVector(num_nodes=4, mode=MODE_FIXED)
```

**Config**: `configs/default.yaml` → `signal_control.fixed`

### Adaptive (Queue-Based)
Adjusts green time based on queue lengths.

```python
from core import SignalControllerVector, MODE_ADAPTIVE
signals = SignalControllerVector(num_nodes=4, mode=MODE_ADAPTIVE)
```

**Config**: `configs/default.yaml` → `signal_control.adaptive`

### Dynamic (Gap-Out)
Uses gap-out logic for phase termination.

```python
from core import dynamic
# Dynamic control implementation
```

**Config**: `configs/default.yaml` → `signal_control.dynamic`

---

## 🧪 Running Experiments

### Grid Experiments

**Speed Threshold Experiment**
```bash
python scenarios/experiment_speed_threshold.py
```

**Velocity Invariant Experiment**
```bash
python scenarios/experiment_velocity_invariant.py
```

### Batch Processing
Run multiple experiments with different parameters:

```bash
python scenarios/batch_runner.py
```

---

## ⚙️ Configuration

### Using Default Config
```python
from core import load_physics_config
config = load_physics_config('configs/default.yaml')
```

### Config Structure
```yaml
physics:
  standard: {...}
  aggressive: {...}

experiments:
  grid_baseline: {...}
  intersection_baseline: {...}
  real_delhi: {...}

signal_control:
  fixed: {...}
  adaptive: {...}
  dynamic: {...}
```

---

## 📊 Output and Results

All results saved to `output/results/`:
- CSV files with vehicle statistics
- Throughput metrics
- Wait time distributions
- Signal timing logs

---

## 🧪 Testing

### GPU Test
```bash
python tests/test_gpu.py
```

### NEMA Compliance Test
```bash
python tests/test_nema.py
```

### All Tests
```bash
python tests/test_intersection.py
python tests/test_biased_flow.py
python tests/test_comparison.py
python tests/test_spawning.py
```

---

## 🎯 Command Reference

### CLI Arguments

**Grid Mode**
- `--size N` - Grid size (NxN intersections)
- `--rate R` - Spawn rate (vehicles/second)
- `--duration D` - Simulation duration (seconds)
- `--adaptive` - Use adaptive signal control

**Intersection Mode**
- `--rate R` - Spawn rate
- `--duration D` - Duration
- `--adaptive` - Adaptive control

**Real Map Mode**
- `--map NAME` - Map name (delhi, mumbai, etc.)
- `--rate R` - Spawn rate
- `--duration D` - Duration
- `--adaptive` - Adaptive control

---

## 📝 Examples

### Example 1: Quick Test
```bash
python -m scenarios.cli grid --size 3 --rate 0.1 --duration 60
```

### Example 2: Production Run
```bash
python -m scenarios.cli grid --size 10 --rate 0.5 --adaptive --duration 7200
```

### Example 3: Real Map with Targets
```bash
python scenarios/real_map_runner.py
```

---

## 🔧 Troubleshooting

**GPU not detected?**
- Install CuPy: `pip install cupy-cuda12x`
- Check CUDA version compatibility

**Import errors?**
- Ensure you're in D:\TrafficSim directory
- Check Python path includes current directory

**Config not found?**
- Verify `configs/default.yaml` exists
- Check file paths are absolute

---

## ✅ Verification

To verify all modes work:
```bash
# Test each mode
python -m scenarios.cli grid --size 3 --duration 10
python -m scenarios.cli intersection --duration 10
python -m scenarios.cli real --map delhi --duration 10

# Run tests
python tests/test_gpu.py
python tests/test_nema.py
```

All modes should run without errors and produce output in `output/results/`.
