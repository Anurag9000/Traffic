# Configuration Guide - D:\TrafficSim

## Overview

All configurations have been unified into `configs/default.yaml` for simplicity and maintainability. This single file contains all physics parameters, experiment configurations, signal control settings, and spawning parameters.

---

## Configuration Structure

```yaml
configs/default.yaml:
  ├── physics (2 variants)
  ├── experiments (15 configs)
  ├── signal_control (3 modes)
  └── spawning (3 strategies)
```

---

## Physics Configurations

### Standard Physics
```yaml
physics.standard:
  car/bike/van/truck:  # All equal priority
    acceleration: 2.5 m/s²
    deceleration: 4.5 m/s²
    max_speed: 30.0 m/s
    tau: 1.5s (time headway)
```

### Aggressive Physics
```yaml
physics.aggressive:
  car/bike/van/truck:  # All equal priority
    acceleration: 3.5 m/s²
    deceleration: 6.0 m/s²
    max_speed: 35.0 m/s
    tau: 1.0s
```

**Key Principle**: All vehicle types have identical physics (no priority hierarchy).

---

## Experiment Configurations (15 Total)

### Grid Experiments (4)
1. **grid_baseline** - Standard grid, fixed control
2. **grid_dynamic** - Adaptive signal control
3. **grid_fixed** - Fixed timing only
4. **grid_target** - Targeted spawning, 80% with destinations

### Intersection Experiments (3)
5. **intersection_baseline** - Standard 4-way intersection
6. **intersection_dynamic** - Adaptive control
7. **intersection_targeted** - Directional spawning (rush hour)

### Real Map Experiments (7)
8. **real_delhi** - Delhi map, adaptive control
9. **real_delhi_dynamic** - Adaptive signals
10. **real_delhi_fixed** - Fixed timing
11. **real_delhi_targeted** - 80% vehicles with targets
12. **real_delhi_untargeted** - Uniform spawning
13. **real_delhi_history** - Historical data mode
14. **real_delhi_live** - Live traffic mode

### Special Experiments (1)
15. **speed_sweep** - Multiple spawn rates [0.1, 0.2, 0.3, 0.4, 0.5]

---

## Signal Control Parameters

### Fixed Timing
```yaml
signal_control.fixed:
  green_time: 30s
  yellow_time: 3s
  all_red_time: 2s
```

### Adaptive (Queue-Based)
```yaml
signal_control.adaptive:
  min_green: 10s
  max_green: 60s
  yellow_time: 3s
  all_red_time: 2s
  queue_threshold: 5 vehicles
```

### Dynamic (Gap-Out)
```yaml
signal_control.dynamic:
  min_green: 10s
  max_green: 60s
  yellow_time: 3s
  all_red_time: 2s
  gap_out_threshold: 2.5s
```

---

## Spawning Parameters

### Uniform (Poisson)
```yaml
spawning.uniform:
  variation: 0.2  # ±20% rate variation
```

### Targeted (Destination-Based)
```yaml
spawning.targeted:
  variation: 0.2
  target_ratio: 0.8  # 80% have destinations
```

### Directional (Rush Hour)
```yaml
spawning.directional:
  variation: 0.2
  lane_biases: {lane_id: multiplier}
```

---

## How to Use Configurations

### Method 1: Use Default Config
```python
from core.config import load_and_prepare_config

config = load_and_prepare_config('configs/default.yaml', mode='grid')
# Access: config['experiments']['grid_baseline']
```

### Method 2: Direct CLI Usage
```bash
# Grid with adaptive control
python -m scenarios.cli grid --size 5 --rate 0.2 --adaptive

# Intersection with fixed control
python -m scenarios.cli intersection --rate 0.5

# Real map
python -m scenarios.cli real --map delhi --rate 0.3 --adaptive
```

### Method 3: Programmatic
```python
from core import TrafficGridNetwork

network = TrafficGridNetwork(
    grid_size=5,
    spawn_rate=0.2,
    control_mode='adaptive',  # or 'fixed'
    lane_length=100.0
)
```

---

## Configuration Mapping

### Original → Unified

| Original File | Location in default.yaml |
|---------------|--------------------------|
| `physics/standard.yaml` | `physics.standard` |
| `physics/aggressive.yaml` | `physics.aggressive` |
| `experiments/grid_baseline.yaml` | `experiments.grid_baseline` |
| `experiments/grid_dynamic.yaml` | `experiments.grid_dynamic` |
| ... (15 total) | `experiments.*` |

**Reduction**: 17 files → 1 unified file (94% reduction)

---

## Clean Code Principles Applied

1. **Single Source of Truth** - One config file, not scattered
2. **No Duplication** - Shared parameters defined once
3. **Clear Structure** - Hierarchical organization
4. **Easy Maintenance** - Change once, affects all
5. **Type Safety** - YAML validation

---

## Extending Configurations

### Add New Experiment
```yaml
experiments:
  my_new_experiment:
    grid_size: 10
    spawn_rate: 0.3
    duration: 7200
    control_mode: adaptive
    physics: standard
```

### Add New Physics Profile
```yaml
physics:
  custom:
    car:
      acceleration: 4.0
      deceleration: 7.0
      max_speed: 40.0
```

---

## Validation

All configurations are validated on load:
- Required parameters checked
- Type validation (int, float, string)
- Range validation (e.g., spawn_rate > 0)
- Dependency validation (e.g., targeted mode requires lane_map)

---

## Summary

✅ **17 configs → 1 unified file**  
✅ **All experiments preserved**  
✅ **All physics variants included**  
✅ **All signal modes configured**  
✅ **Clean, maintainable structure**  

**Location**: `D:\TrafficSim\configs\default.yaml`
