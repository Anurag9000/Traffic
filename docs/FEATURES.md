🚦 SIMULATION MODES
Grid Network - Synthetic NxN grid of intersections (configurable 5x5, 10x10, etc.)
Single Intersection - Standalone 4-way intersection simulation
Real Map - Delhi Connaught Place from OpenStreetMap data
🎲 SPAWNING STRATEGIES
Uniform Poisson - Standard probabilistic spawning across all entry lanes
Targeted Navigation - Vehicles assigned (x,y) destinations with smart routing
Directional/Biased - Asymmetric demand for rush hour simulation (N-S heavy, turn biases)
🚥 SIGNAL CONTROL MODES
Fixed-Time - Constant phase durations (IRC:93-1985 compliant)
Adaptive (Smart MA) - 5-cycle Moving Average with dynamic phase splits
Gap-Out - Traditional actuated control with demand extensions
🏗️ NEMA DUAL-RING 8-PHASE
2 Rings - Ring 1 (N/S), Ring 2 (E/W)
8 Phases - Phases 1-4 (N/S movements), Phases 5-8 (E/W movements)
Barrier Synchronization - Both rings must reach barrier before crossing
Free Left Turns - LHT (Left-Hand Traffic) compliant
Signalized Right Turns - IRC:93-1985 4-stage compliance
🚗 VEHICLE TYPES
Car - Standard passenger vehicle
Bike - Two-wheeler
Truck/Bus - Heavy vehicle
(All use identical IDM physics - equal priority)
⚡ PHYSICS ENGINE
IDM (Intelligent Driver Model) - Vectorized implementation
500x speedup over OOP version
20,000+ vehicles capacity at 3ms/step (280+ FPS)
Configurable parameters - v_max, a_max, b_comfort, delta, s0, T
🎮 GPU ACCELERATION
CuPy support - Automatic GPU detection
NumPy fallback - Seamless CPU mode if no GPU
Single xp abstraction - No code changes needed to switch backends
📊 STATISTICS & METRICS
Real-time tracking - Vehicle counts, delays, throughput
Trip logging - Entry/exit times, travel times, acceleration/cruise times
CSV export - Summary and detailed vehicle data
Live export - Real-time data streaming during simulation
🗺️ REAL MAP FEATURES
OSM Integration - OpenStreetMap GraphML loading
Speed limit enforcement - Road-specific speed limits
Lane count enforcement - Actual lane configurations
One-way enforcement - Directional restrictions
Map filtering - Backbone roads vs all roads
Time-varying profiles - Morning/evening rush patterns
Live traffic data - TomTom API integration
Historical replay - CSV-based traffic data playback
🧪 EXPERIMENTS
Grid Baseline - Standard uniform spawning
Grid Fixed - Fixed signal control
Grid Dynamic - Adaptive signal control
Grid Targeted - 80% vehicles to center
Intersection Baseline - Standard adaptive
Intersection Dynamic - Biased flow comparison
Intersection Targeted - Turn bias experiments
Delhi Baseline - Standard real map
Delhi Fixed - Fixed signals on real map
Delhi Dynamic - Adaptive signals on real map
Delhi Targeted - Navigation to specific coordinates
Delhi Live - Real-time TomTom data
Delhi History - Historical data replay
Speed Threshold - Max speed vs throughput analysis
Velocity Invariance - 30 vs 40 kmph comparison
Physics Tuning - Aggressive vs standard IDM parameters
🔧 CONFIGURATION OPTIONS
Simulation - duration, spawn_rate, inflow_noise, seed, dt, stats_interval
Grid - size, lane_length, subgrid_sizes, subgrid_regions, lambda_decay
Spawning - target_coord, target_fraction, flow_biases, turn_biases, lane_biases
Signals - control_mode, cycle_time, min_green, max_green, yellow_time, all_red_time
Real Map - map_filter, enforce_speed_limit, enforce_lanes, enforce_oneway, start_time, profile, api_key
Physics - v_max, a_max, b_comfort, delta, s0, T
Output - output_dir, live_export, speedup
📁 OUTPUT FORMATS
CSV files - Summary metrics and detailed vehicle data
Real-time export - Live data streaming
Comparative reports - Fixed vs Adaptive benchmarks
Phase diagrams - Signal timing visualizations
🎯 EXECUTION METHODS
Simple entry points - 
traffic_grid_simulation.py
, 
traffic_real_simulation.py
Full CLI runners - With extensive argument parsing
Module entry points - python -m traffic_grid.python_sim.main
YAML configurations - 21 config files for different scenarios
Specialized runners - 
run_directional.py
, 
run_grid_targeted.py
, 
run_real_targeted.py
Experiment scripts - Speed threshold, velocity invariant, batch sweeps
Comparison tests - Fixed vs Dynamic benchmarking
🛠️ ADVANCED FEATURES
Subgrid support - Different signal timings for grid regions
Lambda decay - Time-varying spawn rates
Parallel batch execution - Multi-process simulation runs
Parameter sweeps - Automated parameter optimization
Visualization - Real-time matplotlib rendering
Headless mode - No-GUI for batch processing
Reproducible seeds - Deterministic simulation runs
📈 PERFORMANCE BENCHMARKS
Adaptive vs Fixed - 1-7% delay reduction
Vectorized speedup - 500x faster than OOP
Capacity - 20,000+ vehicles
Step time - ~3ms per timestep
Frame rate - 280+ FPS
🌐 INDIAN LHT STANDARDS
IRC:93-1985 - 4-stage signal cycle compliance
Left-hand traffic - Free left turns
Right turn signaling - Mandatory signal control
TOTAL: 50+ distinct features across 3 simulation modes, 3 spawning strategies, 3 signal controls, 15+ experiments, 7 execution methods, and extensive configuration options.