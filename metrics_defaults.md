# TrafficSim Metrics & Defaults

This document records the standardized metrics, units, and default values used throughout the `TrafficSim` codebase. All functions, classes, and configurations must align with these definitions.

## 1. Units of Measurement
- **Distance**: Meters (m)
- **Time**: Seconds (s)
- **Speed**: Meters per second (m/s). *Note: Multiply by 3.6 for km/h.*
- **Acceleration**: Meters per second squared (m/s²)
- **Rate (Flow)**: Vehicles per Lane per Second (veh/ln/s)

## 2. Global Simulation Constants
- **Time Step (`DT`)**: `0.1 s` (Core physics tick)
- **Lane Width**: `3.5 m` (Implicit in visualization, physics is 1D longitudinal)
- **Vehicle Length**: `5.0 m` (Standard car)
- **Clearance Buffer**: `2.0 m` (Min gap between cars)

## 3. Physics Parameters (`engine.py`)
- **Max Acceleration (`a_max`)**: `2.0 m/s²` (Default Car). *Varies by Vehicle Type.*
- **Comfortable Deceleration (`b_comfort`)**: `3.0 m/s²` (Default Car). *Varies by Vehicle Type.*
- **Safe Headway Time (`T`)**: `1.5 s`
- **Acceleration Exponent (`delta`)**: `4.0`
- **Reaction Time**: `0.0 s` (Instant/Superhuman) - *Known limitation*

## 4. Signal Timing (`signals.py`)
- **Cycle Time**: **TOTAL** time for one complete sequence of phases (Green + Yellow + Red Clearance).
- **Yellow Time**: `3.0 s`
- **Red Clearance**: `2.0 s`
- **Lost Time per Cycle**: `20.0 s` (4 stages × 5s). *Corrected from 40s.*
- **Default Cycle**: `120.0 s`
- **Split Logic**:
    - **Fixed Mode**: `Total Green / 4` (Uniform distribution)
    - **Adaptive Mode**: Proportional to valid demand (throughput).

## 5. Spawning (`spawning.py`)
- **Spawn Probability**: `prob = rate * dt` (Per Lane)
- **Backlog**: Blocked spawns are queued and retried. They do not evaporate.
- **Rate Definition**: A rate of `1.0` means **3600 vehicles per lane per hour** (Saturation Flow). 
    - *Typical values*: `0.1` (Low), `0.3` (Heavy), `0.5` (Oversaturated).

## 6. Grid & Network (`grid_network.py`)
- **Default Grid Size**: `10x10`
- **Lane Length**: `100.0 m` (Grid), `400.0 m` (Intersection)
- **Speed Limit**: `13.8 m/s` (~50 km/h) unless specified.

## 7. Vehicle Types (`engine.py`)
| Type ID | Name   | Length (m) | Max Speed (m/s) | Accel (m/s²) | Decel (m/s²) | Distribution |
|---------|--------|------------|-----------------|--------------|--------------|--------------|
| 0       | Car    | 5.0        | 30.0            | 2.5          | 4.0          | 70%          |
| 1       | Bike   | 2.0        | 20.0            | 3.5          | 5.0          | 10%          |
| 2       | Tempo  | 6.0        | 25.0            | 2.0          | 3.0          | 10%          |
| 3       | Truck  | 10.0       | 18.0            | 1.5          | 2.0          | 10%          |
