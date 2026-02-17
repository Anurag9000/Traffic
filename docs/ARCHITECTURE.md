# Traffic Simulator - Architecture Documentation

## 🏗️ System Overview

The Traffic Simulator is a **vectorized, GPU-accelerated traffic simulation system** with **NEMA Dual-Ring 8-Phase signal control**. It supports grid, intersection, and real-world map simulations with multiple spawning strategies and signal control modes.

---

## 📁 Repository Structure

```
D:\TrafficSim/
├── core/                  # Core simulation engine (21 files)
│   ├── gpu.py            # GPU acceleration layer
│   ├── physics.py        # IDM vehicle physics
│   ├── engine.py         # Main traffic engine
│   ├── signals.py        # NEMA signal controller
│   ├── spawning.py       # Vehicle spawning
│   ├── lanes.py          # Lane representation
│   ├── grid_adapter.py   # Grid topology
│   ├── graph.py          # OSMnx conversion
│   ├── grid_network.py   # Grid simulation
│   ├── intersection.py   # Intersection simulation
│   ├── real_network.py   # Real map simulation
│   ├── adaptive.py       # Adaptive control
│   ├── dynamic.py        # Dynamic control
│   ├── fixed.py          # Fixed control
│   ├── stats.py          # Statistics
│   ├── config.py         # Config loader
│   ├── paths.py          # Path utilities
│   ├── base_visualizer.py
│   ├── grid_visualizer.py
│   ├── real_map_visualizer.py
│   └── __init__.py
├── scenarios/            # Experiment runners (8 files)
│   ├── cli.py           # Unified CLI
│   ├── grid_targeted.py
│   ├── real_map_runner.py
│   ├── intersection_directional.py
│   ├── batch_runner.py
│   ├── experiment_speed_threshold.py
│   ├── experiment_velocity_invariant.py
│   └── __init__.py
├── tests/               # Test suite (6 files)
│   ├── test_gpu.py
│   ├── test_nema.py
│   ├── test_intersection.py
│   ├── test_biased_flow.py
│   ├── test_comparison.py
│   └── test_spawning.py
├── configs/             # Configuration files
│   ├── default.yaml     # Unified config
│   ├── physics.yaml
│   └── aggressive.yaml
├── docs/                # Documentation
│   ├── USAGE_GUIDE.md
│   ├── ARCHITECTURE.md  # This file
│   ├── SCENARIOS_GUIDE.md
│   ├── EXPERIMENTS_GUIDE.md
│   └── NEMA_MANDATORY.txt
└── README.md
```

---

## 🔧 Module Hierarchy

### Layer 1: Foundation
```
gpu.py (GPU abstraction)
  ↓
physics.py (IDM physics)
```

### Layer 2: Core Components
```
lanes.py (LaneMap)
  ↓
signals.py (NEMA Controller)
  ↓
spawning.py (Vehicle Spawner)
  ↓
engine.py (TrafficEngine) ← Uses all above
```

### Layer 3: Topology Adapters
```
grid_adapter.py → LaneMap
graph.py → LaneMap (from OSMnx)
```

### Layer 4: Simulation Classes
```
grid_network.py → TrafficEngine + GridAdapter
intersection.py → TrafficEngine + LaneMap
real_network.py → TrafficEngine + TrafficGraph
```

### Layer 5: Runners & CLI
```
cli.py → grid_network.py | intersection.py | real_network.py
scenarios/*.py → Simulation classes
```

---

## 🔄 Execution Workflows

### Workflow 1: Grid Simulation

**Command**: `python -m scenarios.cli grid --size 5 --rate 0.2 --adaptive`

**Call Chain**:
```
1. scenarios/cli.py::main()
   ↓
2. scenarios/cli.py::run_grid(args)
   ↓
3. core/grid_network.py::TrafficGridNetwork.__init__()
   ├→ 4. core/grid_adapter.py::GridAdapter.build_grid()
   │    ├→ 5. core/lanes.py::LaneMap.__init__()
   │    └→ 6. core/lanes.py::LaneMap.set_lane() [for each lane]
   ├→ 7. core/signals.py::SignalControllerVector.__init__()
   │    └→ 8. core/signals.py::NEMADualRing8Phase.__init__() [for each node]
   ├→ 9. core/engine.py::TrafficEngine.__init__(lane_map, signals)
   └→ 10. core/spawning.py::Spawner.__init__(mode='uniform')
   ↓
11. core/stats.py::VectorStatsRecorder.__init__(engine)
   ↓
12. Loop: TrafficGridNetwork.step() [for duration/dt steps]
   ├→ 13. core/spawning.py::Spawner.spawn()
   │    └→ 14. core/engine.py::TrafficEngine.spawn_vehicles()
   ├→ 15. core/engine.py::TrafficEngine.step()
   │    ├→ 16. core/physics.py::calculate_idm_vectorized()
   │    ├→ 17. core/physics.py::update_kinematics()
   │    ├→ 18. core/signals.py::SignalControllerVector.update()
   │    │    └→ 19. core/signals.py::NEMADualRing8Phase.update()
   │    └→ 20. core/engine.py::_handle_boundaries()
   └→ 21. core/stats.py::VectorStatsRecorder.log_step()
   ↓
22. core/stats.py::VectorStatsRecorder.compute_summary()
```

**Detailed Step-by-Step**:

1. **CLI Entry** (`cli.py::main`)
   - Parses command-line arguments
   - Determines mode (grid/intersection/real)
   - Calls appropriate runner function

2. **Grid Runner** (`cli.py::run_grid`)
   - Creates `TrafficGridNetwork` instance
   - Sets up statistics recorder
   - Runs simulation loop

3. **Grid Network Init** (`grid_network.py::__init__`)
   - Calls `GridAdapter.build_grid()` to create topology
   - Creates signal controller for all intersections
   - Creates traffic engine with lane map
   - Creates spawner for vehicle generation

4. **Grid Adapter** (`grid_adapter.py::build_grid`)
   - Generates NxN grid of intersections
   - Creates lanes for each direction (N/S/E/W)
   - Sets up lane connectivity (adjacency)
   - Assigns signal phases to lanes
   - Returns `LaneMap`

5. **Lane Map** (`lanes.py::LaneMap`)
   - Stores lane geometry (length, speed limit)
   - Stores lane connectivity (next lanes)
   - Stores signal assignments (node, phase)
   - Provides vectorized lane queries

6. **Signal Controller** (`signals.py::SignalControllerVector`)
   - Creates NEMA controller for each intersection
   - Initializes dual-ring 8-phase logic
   - Sets up barrier groups and phase sequences

7. **Traffic Engine** (`engine.py::TrafficEngine`)
   - Allocates vehicle state arrays (GPU/CPU)
   - Stores lane map reference
   - Stores signal controller reference
   - Initializes metrics tracking

8. **Spawner** (`spawning.py::Spawner`)
   - Sets spawning mode (uniform/targeted/directional)
   - Configures spawn rate and variation
   - Initializes random number generator

9. **Simulation Loop** (`grid_network.py::step`)
   - **Step 9a**: Spawner generates new vehicles
     - Determines spawn count (Poisson distribution)
     - Selects spawn lanes (boundary lanes)
     - Creates vehicle IDs, positions, types
     - Calls `engine.spawn_vehicles()`
   
   - **Step 9b**: Engine updates all vehicles
     - **Sort**: Sorts vehicles by lane and position
     - **Leaders**: Identifies leader for each vehicle
     - **Gaps**: Calculates gap to leader
     - **IDM**: Computes acceleration (IDM model)
     - **Signals**: Applies signal compliance
       - Detects vehicles near signals
       - Checks signal state (RED/GREEN)
       - Applies braking if RED
     - **Kinematics**: Updates position and velocity
     - **Boundaries**: Handles lane transitions
       - Checks if vehicle crossed lane end
       - Routes to next lane (random or targeted)
       - Removes vehicles at dead ends
     - **Compact**: Removes inactive vehicles
   
   - **Step 9c**: Signals update
     - Counts vehicles in detector zones
     - Updates phase timers
     - Applies NEMA logic (barriers, gaps, max-out)
     - Transitions phases if needed
   
   - **Step 9d**: Stats recording
     - Logs active vehicle count
     - Records throughput
     - Tracks wait times

10. **Final Summary** (`stats.py::compute_summary`)
    - Aggregates all metrics
    - Computes averages
    - Exports to CSV
    - Returns summary dict

---

### Workflow 2: Intersection Simulation

**Command**: `python -m scenarios.cli intersection --rate 0.5 --adaptive`

**Call Chain**:
```
1. scenarios/cli.py::main()
   ↓
2. scenarios/cli.py::run_intersection(args)
   ↓
3. core/intersection.py::SingleIntersection.__init__()
   ├→ 4. core/lanes.py::LaneMap.__init__() [manual 4-way setup]
   ├→ 5. core/signals.py::SignalControllerVector.__init__()
   ├→ 6. core/engine.py::TrafficEngine.__init__()
   └→ 7. core/spawning.py::Spawner.__init__()
   ↓
8. Loop: SingleIntersection.step()
   [Same as Grid workflow steps 12-22]
```

**Key Differences from Grid**:
- Manual lane setup (4 approaches, 3 lanes each)
- Single signal controller (1 intersection)
- Simpler topology (no grid routing)

---

### Workflow 3: Real Map Simulation

**Command**: `python -m scenarios.cli real --map delhi --adaptive`

**Call Chain**:
```
1. scenarios/cli.py::main()
   ↓
2. scenarios/cli.py::run_real(args)
   ↓
3. core/real_network.py::RealTrafficNetwork.__init__()
   ├→ 4. OSMnx: Download map data
   ├→ 5. core/graph.py::TrafficGraph.from_networkx(G)
   │    ├→ 6. Map edges to lane IDs
   │    ├→ 7. core/lanes.py::LaneMap.__init__()
   │    └→ 8. core/lanes.py::LaneMap.set_lane() [for each edge]
   ├→ 9. core/signals.py::SignalControllerVector.__init__()
   ├→ 10. core/engine.py::TrafficEngine.__init__()
   └→ 11. core/spawning.py::Spawner.__init__(mode='targeted')
   ↓
12. Loop: RealTrafficNetwork.step()
   [Same as Grid workflow steps 12-22]
```

**Key Differences**:
- Uses OSMnx to download real map
- `TrafficGraph` converts NetworkX graph to LaneMap
- Lanes have real-world coordinates
- Targeted spawning (vehicles have destinations)

---

### Workflow 4: Targeted Spawning

**Command**: `python scenarios/grid_targeted.py`

**Key Changes**:
```
Spawner.__init__(mode='targeted', lane_map=lane_map)
  ↓
Spawner.spawn()
  ├→ Generate spawn count
  ├→ Select spawn lanes
  ├→ Generate random targets (x, y)
  └→ engine.spawn_vehicles(targets=targets)
     ↓
     engine: vehicles[IDX_TARGET_X] = targets[:, 0]
     engine: vehicles[IDX_TARGET_Y] = targets[:, 1]
  ↓
engine._handle_boundaries()
  ├→ Check if vehicle has target
  ├→ If yes: Manhattan distance routing
  │    ├→ Calculate distance to target
  │    ├→ Choose next lane that minimizes distance
  │    └→ Remove vehicle if within 50m of target
  └→ If no: Random walk routing
```

---

### Workflow 5: Directional Spawning (Rush Hour)

**Command**: `python scenarios/intersection_directional.py`

**Key Changes**:
```
lane_biases = {0: 2.0, 1: 0.5, 2: 1.0, 3: 1.5}
Spawner.__init__(mode='directional', lane_biases=lane_biases)
  ↓
Spawner.spawn()
  ├→ Generate base spawn count
  ├→ For each lane:
  │    └→ Multiply count by lane_biases[lane_id]
  └→ Spawn more vehicles on high-bias lanes
```

**Use Case**: Simulate rush hour where certain directions have more traffic.

---

### Workflow 6: Adaptive Signal Control

**Enabled with**: `--adaptive` flag

**Changes in Signal Update**:
```
SignalControllerVector.update(detector_counts)
  ↓
For each intersection:
  NEMADualRing8Phase.update()
    ├→ Read detector_counts for each phase
    ├→ If current phase has queue:
    │    └→ Extend green time (up to max_green)
    ├→ If current phase has no queue:
    │    └→ Terminate early (gap-out)
    ├→ If competing phase has larger queue:
    │    └→ Prioritize that phase
    └→ Apply NEMA barrier constraints
```

**Benefit**: Reduces wait time by adapting to traffic demand.

---

## 🧩 Key Components Deep Dive

### TrafficEngine (engine.py)

**State Arrays** (GPU/CPU):
```python
vehicles[N, 12]:  # N vehicles, 12 attributes each
  [0] ID          # Unique vehicle ID
  [1] X           # X coordinate
  [2] Y           # Y coordinate
  [3] VEL         # Velocity (m/s)
  [4] ACC         # Acceleration (m/s²)
  [5] LANE_ID     # Current lane
  [6] POS_ON_LANE # Position on lane (m)
  [7] TYPE_ID     # Vehicle type (0=car, 1=bike, etc.)
  [8] STATUS      # Active (1.0) or inactive (0.0)
  [9] START_TIME  # Spawn time
  [10] TARGET_X   # Destination X (-1 if no target)
  [11] TARGET_Y   # Destination Y (-1 if no target)
```

**Main Loop** (`engine.step()`):
1. Sort vehicles by lane and position
2. Identify leader for each vehicle
3. Calculate gaps
4. Compute IDM acceleration
5. Apply signal compliance
6. Update kinematics
7. Handle lane transitions
8. Compact inactive vehicles

---

### NEMA Signal Controller (signals.py)

**Dual-Ring 8-Phase Structure**:
```
Ring 1: φ1 → φ2 → φ3 → φ4
Ring 2: φ5 → φ6 → φ7 → φ8

Barriers:
  Barrier A: Between (φ2,φ6) and (φ3,φ7)
  Barrier B: Between (φ4,φ8) and (φ1,φ5)

Concurrent Phases:
  φ1 + φ5, φ2 + φ6, φ3 + φ7, φ4 + φ8
```

**Phase Transition Logic**:
1. Check if current phase timer expired
2. Check if max green reached
3. Check if gap-out condition met
4. Check barrier constraints
5. Transition to next phase if allowed
6. Apply yellow and all-red clearance

---

### Spawner (spawning.py)

**Modes**:

1. **Uniform**: Poisson arrival, random lanes
2. **Targeted**: Poisson arrival, with destinations
3. **Directional**: Biased arrival rates per lane

**Spawn Process**:
```python
def spawn():
  count = poisson(mean_rate * dt)
  lanes = select_spawn_lanes(count)
  positions = [0.0] * count
  types = random_vehicle_types(count)
  targets = generate_targets(count) if targeted else None
  engine.spawn_vehicles(count, lanes, positions, types, targets)
```

---

## 📊 Data Flow Diagram

```
User Command
    ↓
CLI Parser
    ↓
Simulation Class (Grid/Intersection/Real)
    ├→ GridAdapter/Graph → LaneMap
    ├→ SignalController
    ├→ TrafficEngine
    └→ Spawner
    ↓
Simulation Loop
    ├→ Spawner.spawn() → Engine.spawn_vehicles()
    ├→ Engine.step()
    │   ├→ Physics (IDM)
    │   ├→ Signals (NEMA)
    │   └→ Routing
    └→ Stats.log_step()
    ↓
Stats.compute_summary()
    ↓
CSV Export
```

---

## 🎯 Design Principles

1. **Vectorization**: All operations on arrays, not individual vehicles
2. **GPU-First**: CuPy by default, NumPy fallback
3. **Modularity**: Each file has single responsibility
4. **NEMA Compliance**: Mandatory 8-phase dual-ring control
5. **Equal Priority**: All vehicle types have same physics
6. **Configurability**: All parameters in YAML configs

---

## 🔍 Performance Characteristics

- **Grid 5x5, 3600s**: ~10,000 vehicles, ~30 seconds (GPU)
- **Intersection, 3600s**: ~5,000 vehicles, ~15 seconds (GPU)
- **Real Map Delhi, 3600s**: ~8,000 vehicles, ~45 seconds (GPU)

**GPU Speedup**: ~10-20x over CPU for large simulations

---

## 📚 Further Reading

- `USAGE_GUIDE.md` - How to run simulations
- `SCENARIOS_GUIDE.md` - Experiment scenarios
- `EXPERIMENTS_GUIDE.md` - Running experiments
- `NEMA_MANDATORY.txt` - NEMA enforcement details
