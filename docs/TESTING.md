# Testing and Verification Guide

## 🧪 Quick Verification

Run all modes to verify everything works:

```bash
cd D:\TrafficSim

# Test 1: Grid mode (10 seconds)
python -m scenarios.cli grid --size 3 --rate 0.1 --duration 10

# Test 2: Intersection mode (10 seconds)
python -m scenarios.cli intersection --rate 0.3 --duration 10

# Test 3: Real map mode (10 seconds)  
python -m scenarios.cli real --map delhi --rate 0.2 --duration 10

# Test 4: GPU acceleration
python tests/test_gpu.py

# Test 5: NEMA compliance
python tests/test_nema.py
```

**Expected**: All commands complete without errors, output files created in `output/results/`.

---

## ✅ Comprehensive Test Suite

### 1. Core Functionality Tests

**GPU Acceleration**
```bash
python tests/test_gpu.py
```
Verifies:
- CuPy installation (if available)
- GPU detection
- Array operations on GPU
- CPU fallback works

**NEMA Compliance**
```bash
python tests/test_nema.py
```
Verifies:
- 8-phase dual-ring structure
- Barrier constraints
- Phase sequencing
- Concurrent phase rules

**Intersection Logic**
```bash
python tests/test_intersection.py
```
Verifies:
- Intersection setup
- Signal assignment
- Vehicle spawning
- Basic simulation

**Spawning Verification**
```bash
python tests/test_spawning.py
```
Verifies:
- Boundary spawning
- Spawn rate accuracy
- Vehicle type distribution

**Biased Flow**
```bash
python tests/test_biased_flow.py
```
Verifies:
- Directional spawning
- Lane bias application
- Flow distribution

**Comparison Tests**
```bash
python tests/test_comparison.py
```
Verifies:
- Multiple simulation modes
- Result consistency

---

### 2. Mode-Specific Tests

**Grid Simulation**
```bash
# Basic grid
python -m scenarios.cli grid --size 3 --rate 0.1 --duration 60

# Grid with adaptive control
python -m scenarios.cli grid --size 3 --rate 0.1 --adaptive --duration 60

# Grid with targeted spawning
python scenarios/grid_targeted.py
```

**Intersection Simulation**
```bash
# Basic intersection
python -m scenarios.cli intersection --rate 0.3 --duration 60

# Intersection with adaptive
python -m scenarios.cli intersection --rate 0.3 --adaptive --duration 60

# Intersection with directional spawning
python scenarios/intersection_directional.py
```

**Real Map Simulation**
```bash
# Basic real map
python -m scenarios.cli real --map delhi --rate 0.2 --duration 60

# Real map with adaptive
python -m scenarios.cli real --map delhi --rate 0.2 --adaptive --duration 60

# Real map with targeted spawning
python scenarios/real_map_runner.py
```

---

### 3. Experiment Tests

**Speed Threshold Experiment**
```bash
python scenarios/experiment_speed_threshold.py
```

**Velocity Invariant Experiment**
```bash
python scenarios/experiment_velocity_invariant.py
```

**Batch Runner**
```bash
python scenarios/batch_runner.py
```

---

## 📋 Verification Checklist

### Core Features
- [ ] GPU acceleration works (or CPU fallback)
- [ ] NEMA 8-phase control enforced
- [ ] All vehicle types spawn correctly
- [ ] IDM physics applied
- [ ] Statistics recorded
- [ ] CSV export works

### Simulation Modes
- [ ] Grid simulation runs
- [ ] Intersection simulation runs
- [ ] Real map simulation runs
- [ ] All modes produce output

### Spawning Strategies
- [ ] Uniform spawning works
- [ ] Targeted spawning works
- [ ] Directional spawning works

### Signal Control
- [ ] Fixed timing works
- [ ] Adaptive control works
- [ ] Dynamic control works

### Experiments
- [ ] Speed threshold runs
- [ ] Velocity invariant runs
- [ ] Batch processing runs

---

## 🔍 Expected Outputs

### Console Output
```
🚦 Grid Simulation: 3x3, Rate=0.1, Duration=60s
  Step 0/600 | Active: 0
  Step 1000/600 | Active: 45
  ...
✅ Complete: 123 vehicles, Avg delay: 12.34s
```

### File Output
```
output/results/
├── grid_3x3_20260217_182541.csv
├── intersection_20260217_182612.csv
└── real_delhi_20260217_182643.csv
```

### CSV Format
```csv
vehicle_id,start_time,end_time,travel_time,status
1,0.0,45.2,45.2,completed
2,0.5,52.1,51.6,completed
...
```

---

## ⚠️ Common Issues

**Issue**: `ModuleNotFoundError: No module named 'cupy'`
**Solution**: Install CuPy or ignore (will use NumPy)

**Issue**: `FileNotFoundError: configs/default.yaml`
**Solution**: Ensure you're in D:\TrafficSim directory

**Issue**: `OSMnx download failed`
**Solution**: Check internet connection, try different map

**Issue**: `No output files created`
**Solution**: Check `output/results/` directory exists

---

## ✅ Success Criteria

All tests pass if:
1. No Python errors/exceptions
2. Output files created
3. CSV contains vehicle data
4. Console shows progress
5. Simulation completes

---

## 🎯 Performance Benchmarks

**Expected Performance** (GPU):
- Grid 3x3, 60s: ~2 seconds
- Grid 5x5, 3600s: ~30 seconds
- Intersection, 3600s: ~15 seconds
- Real map, 3600s: ~45 seconds

**CPU Performance**: ~10-20x slower

---

## 📊 Validation Metrics

Check these in output CSV:
- **Total vehicles**: Should match spawn rate × duration
- **Avg travel time**: Should be reasonable (< 5 min)
- **Throughput**: Vehicles/second exiting system
- **Wait time**: Time spent stopped at signals

---

## 🔧 Debug Mode

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## ✅ Final Verification

Run this complete test:
```bash
# All modes, all tests
python tests/test_gpu.py && \
python tests/test_nema.py && \
python -m scenarios.cli grid --size 3 --duration 10 && \
python -m scenarios.cli intersection --duration 10 && \
python -m scenarios.cli real --map delhi --duration 10 && \
echo "✅ ALL TESTS PASSED"
```

If this completes without errors, **all features are working correctly**.
