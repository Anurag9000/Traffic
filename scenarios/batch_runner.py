"""
Enhanced Batch Runner with Parallel Execution

Supports:
- Sequential batch execution
- Parallel multi-process execution
- Custom configuration per run
- Result aggregation and analysis
"""

import multiprocessing as mp
from typing import List, Dict, Any, Optional
import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.grid_network import TrafficGridNetwork
from core.real_network import RealTrafficNetwork
from core.stats import VectorStatsRecorder


def run_single_simulation(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a single simulation with given configuration.
    
    Args:
        config: Configuration dictionary with keys:
            - mode: 'grid' or 'real'
            - output_dir: Output directory
            - duration: Simulation duration (seconds)
            - ... other mode-specific parameters
    
    Returns:
        Result dictionary with metrics
    """
    mode = config.get('mode', 'grid')
    output_dir = config.get('output_dir', 'run_data')
    duration = config.get('duration', 3600.0)
    
    try:
        # Create network based on mode
        if mode == 'grid':
            network = TrafficGridNetwork(
                grid_size=config.get('grid_size', 5),
                spawn_rate=config.get('spawn_rate', 1.0),
                variation=config.get('variation', 0.5),
                seed=config.get('seed', 42),
                lane_length=config.get('lane_length', 100.0),
                control_mode=config.get('control_mode', 'fixed'),
                subgrid_regions=config.get('subgrid_regions', None),
            )
        elif mode == 'real':
            network = RealTrafficNetwork(
                graphml_path=config.get('graphml_path'),
                sim_duration=duration,
                spawn_rate=config.get('spawn_rate', 1.0),
                variation=config.get('variation', 0.5),
                seed=config.get('seed', 42),
                control_mode=config.get('control_mode', 1),  # MODE_ADAPTIVE
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        # Create stats recorder
        stats = VectorStatsRecorder(
            network.engine,
            output_dir=output_dir,
            prefix=config.get('prefix', ''),
            live_export=config.get('live_export', False)
        )
        
        # Run simulation
        print(f"Running simulation: {config.get('name', 'unnamed')}")
        steps = int(duration / network.dt)
        
        for step in range(steps):
            network.step()
            
            # Log stats every 60 seconds
            if step % 600 == 0:
                stats.log_step(network.time)
        
        # Final stats
        stats.log_step(network.time)
        if hasattr(stats, 'close'):
            stats.close()
        
        # Calculate summary metrics
        import pandas as pd
        metrics_df = pd.read_csv(stats.metrics_file)
        
        result = {
            'config': config,
            'success': True,
            'avg_speed': metrics_df['avg_speed_mps'].mean(),
            'avg_active': metrics_df['active_vehicles'].mean(),
            'total_throughput': metrics_df['throughput_vps'].sum(),
            'output_dir': output_dir,
        }
        
        print(f"✅ Completed: {config.get('name', 'unnamed')}")
        return result
    
    except Exception as e:
        print(f"❌ Failed: {config.get('name', 'unnamed')} - {e}")
        return {
            'config': config,
            'success': False,
            'error': str(e)
        }


def run_batch_sequential(configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run multiple simulations sequentially.
    
    Args:
        configs: List of configuration dictionaries
    
    Returns:
        List of result dictionaries
    """
    results = []
    for i, config in enumerate(configs):
        print(f"\n[{i+1}/{len(configs)}] Running configuration...")
        result = run_single_simulation(config)
        results.append(result)
    
    return results


def run_batch_parallel(
    configs: List[Dict[str, Any]],
    num_workers: int = 4,
) -> List[Dict[str, Any]]:
    """
    Run multiple simulations in parallel.
    
    Args:
        configs: List of configuration dictionaries
        num_workers: Number of parallel processes
    
    Returns:
        List of result dictionaries
    """
    print(f"\n🚀 Running {len(configs)} simulations with {num_workers} workers...")
    
    with mp.Pool(num_workers) as pool:
        results = pool.map(run_single_simulation, configs)
    
    return results


def save_batch_results(results: List[Dict[str, Any]], output_file: str = 'batch_results.json'):
    """
    Save batch results to JSON file.
    
    Args:
        results: List of result dictionaries
        output_file: Output JSON file path
    """
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Results saved to: {output_file}")


def analyze_batch_results(results: List[Dict[str, Any]]):
    """
    Analyze and print summary of batch results.
    
    Args:
        results: List of result dictionaries
    """
    successful = [r for r in results if r.get('success', False)]
    failed = [r for r in results if not r.get('success', True)]
    
    print(f"\n{'=' * 70}")
    print(f"BATCH EXECUTION SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total Runs: {len(results)}")
    print(f"Successful: {len(successful)} ({100 * len(successful) / len(results):.1f}%)")
    print(f"Failed: {len(failed)}")
    
    if successful:
        avg_speeds = [r['avg_speed'] for r in successful]
        avg_actives = [r['avg_active'] for r in successful]
        
        print(f"\nPerformance Metrics:")
        print(f"  Avg Speed: {sum(avg_speeds) / len(avg_speeds):.2f} m/s")
        print(f"  Avg Active Vehicles: {sum(avg_actives) / len(avg_actives):.1f}")
    
    if failed:
        print(f"\nFailed Runs:")
        for r in failed:
            print(f"  - {r['config'].get('name', 'unnamed')}: {r.get('error', 'unknown error')}")
    
    print(f"{'=' * 70}\n")


# Example usage
if __name__ == "__main__":
    # Example: Run grid simulations with different spawn rates
    configs = [
        {
            'name': 'grid_low_spawn',
            'mode': 'grid',
            'grid_size': 5,
            'spawn_rate': 0.3,
            'duration': 1800,
            'output_dir': 'results/batch/low_spawn',
            'seed': 42,
        },
        {
            'name': 'grid_medium_spawn',
            'mode': 'grid',
            'grid_size': 5,
            'spawn_rate': 0.7,
            'duration': 1800,
            'output_dir': 'results/batch/medium_spawn',
            'seed': 42,
        },
        {
            'name': 'grid_high_spawn',
            'mode': 'grid',
            'grid_size': 5,
            'spawn_rate': 1.2,
            'duration': 1800,
            'output_dir': 'results/batch/high_spawn',
            'seed': 42,
        },
    ]
    
    # Run in parallel
    results = run_batch_parallel(configs, num_workers=3)
    
    # Analyze and save
    analyze_batch_results(results)
    save_batch_results(results, 'batch_results.json')
