"""
Parameter Sweep Utilities for Traffic Simulation Optimization

Supports:
- Grid search over parameter space
- Random search with distributions
- Result analysis and visualization
- Best parameter identification
"""

import itertools
import random
from typing import Dict, List, Any, Tuple, Optional, Callable
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scenarios.batch_runner import run_single_simulation


class ParameterSweep:
    """
    Automated parameter sweep utilities for optimization.
    """
    
    def __init__(self, base_config: Dict[str, Any], metric: str = 'avg_speed'):
        """
        Initialize parameter sweep.
        
        Args:
            base_config: Base configuration dictionary
            metric: Metric to optimize ('avg_speed', 'avg_active', 'total_throughput')
        """
        self.base_config = base_config
        self.metric = metric
        self.results = []
    
    def grid_search(
        self,
        param_ranges: Dict[str, List[Any]],
        num_workers: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Grid search over parameter space.
        
        Args:
            param_ranges: Dictionary mapping parameter names to lists of values
                Example: {
                    'spawn_rate': [0.3, 0.5, 0.7, 1.0],
                    'grid_size': [3, 5, 7],
                    'control_mode': ['fixed', 'adaptive']
                }
            num_workers: Number of parallel workers
        
        Returns:
            List of result dictionaries sorted by metric
        """
        # Generate all combinations
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        combinations = list(itertools.product(*param_values))
        
        print(f"\n🔍 Grid Search: {len(combinations)} configurations")
        print(f"Parameters: {param_names}")
        
        # Create configurations
        configs = []
        for i, combo in enumerate(combinations):
            config = self.base_config.copy()
            config['name'] = f"grid_search_{i}"
            config['output_dir'] = f"results/grid_search/run_{i}"
            
            for param_name, param_value in zip(param_names, combo):
                config[param_name] = param_value
            
            configs.append(config)
        
        # Run simulations
        from scenarios.batch_runner import run_batch_parallel
        results = run_batch_parallel(configs, num_workers=num_workers)
        
        # Sort by metric
        successful = [r for r in results if r.get('success', False)]
        successful.sort(key=lambda x: x.get(self.metric, 0), reverse=True)
        
        self.results = successful
        return successful
    
    def random_search(
        self,
        param_distributions: Dict[str, Tuple[str, Any, Any]],
        n_iterations: int = 100,
        num_workers: int = 4,
        seed: int = 42
    ) -> List[Dict[str, Any]]:
        """
        Random search with specified distributions.
        
        Args:
            param_distributions: Dictionary mapping parameter names to distributions
                Format: {
                    'spawn_rate': ('uniform', 0.1, 2.0),
                    'grid_size': ('choice', [3, 5, 7, 10]),
                    'lane_length': ('normal', 100.0, 20.0),  # mean, std
                }
            n_iterations: Number of random samples
            num_workers: Number of parallel workers
            seed: Random seed
        
        Returns:
            List of result dictionaries sorted by metric
        """
        rng = random.Random(seed)
        
        print(f"\n🎲 Random Search: {n_iterations} configurations")
        print(f"Parameters: {list(param_distributions.keys())}")
        
        # Generate random configurations
        configs = []
        for i in range(n_iterations):
            config = self.base_config.copy()
            config['name'] = f"random_search_{i}"
            config['output_dir'] = f"results/random_search/run_{i}"
            config['seed'] = seed + i  # Different seed for each run
            
            for param_name, (dist_type, *dist_params) in param_distributions.items():
                if dist_type == 'uniform':
                    value = rng.uniform(dist_params[0], dist_params[1])
                elif dist_type == 'choice':
                    value = rng.choice(dist_params[0])
                elif dist_type == 'normal':
                    import numpy as np
                    value = np.random.normal(dist_params[0], dist_params[1])
                elif dist_type == 'int_uniform':
                    value = rng.randint(dist_params[0], dist_params[1])
                else:
                    raise ValueError(f"Unknown distribution type: {dist_type}")
                
                config[param_name] = value
            
            configs.append(config)
        
        # Run simulations
        from scenarios.batch_runner import run_batch_parallel
        results = run_batch_parallel(configs, num_workers=num_workers)
        
        # Sort by metric
        successful = [r for r in results if r.get('success', False)]
        successful.sort(key=lambda x: x.get(self.metric, 0), reverse=True)
        
        self.results = successful
        return successful
    
    def get_best_params(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Get best parameter configurations.
        
        Args:
            top_n: Number of top configurations to return
        
        Returns:
            List of top configurations with their metrics
        """
        if not self.results:
            print("No results available. Run grid_search or random_search first.")
            return []
        
        top_results = self.results[:top_n]
        
        print(f"\n🏆 Top {top_n} Configurations (by {self.metric}):")
        print(f"{'=' * 70}")
        
        for i, result in enumerate(top_results):
            print(f"\n#{i+1}: {result['config']['name']}")
            print(f"  {self.metric}: {result[self.metric]:.3f}")
            print(f"  Parameters:")
            for key, value in result['config'].items():
                if key not in ['name', 'output_dir', 'mode', 'duration']:
                    print(f"    {key}: {value}")
        
        print(f"{'=' * 70}\n")
        
        return top_results
    
    def save_results(self, output_file: str = 'parameter_sweep_results.json'):
        """
        Save sweep results to JSON file.
        
        Args:
            output_file: Output JSON file path
        """
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"📊 Results saved to: {output_file}")
    
    def plot_results(self, param_name: str, output_file: str = 'sweep_plot.png'):
        """
        Plot metric vs parameter.
        
        Args:
            param_name: Parameter name to plot
            output_file: Output plot file
        """
        try:
            import matplotlib.pyplot as plt
            
            # Extract data
            param_values = [r['config'][param_name] for r in self.results]
            metric_values = [r[self.metric] for r in self.results]
            
            # Create plot
            plt.figure(figsize=(10, 6))
            plt.scatter(param_values, metric_values, alpha=0.6)
            plt.xlabel(param_name)
            plt.ylabel(self.metric)
            plt.title(f'{self.metric} vs {param_name}')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_file, dpi=150)
            plt.close()
            
            print(f"📈 Plot saved to: {output_file}")
        
        except ImportError:
            print("matplotlib not available. Install with: pip install matplotlib")


# Example usage
if __name__ == "__main__":
    # Base configuration
    base_config = {
        'mode': 'grid',
        'duration': 1800,  # 30 minutes
        'variation': 0.5,
    }
    
    # Example 1: Grid search
    print("\n" + "=" * 70)
    print("EXAMPLE 1: GRID SEARCH")
    print("=" * 70)
    
    sweep = ParameterSweep(base_config, metric='avg_speed')
    
    param_ranges = {
        'spawn_rate': [0.3, 0.5, 0.7, 1.0],
        'grid_size': [3, 5],
        'control_mode': ['fixed', 'adaptive']
    }
    
    results = sweep.grid_search(param_ranges, num_workers=4)
    sweep.get_best_params(top_n=3)
    sweep.save_results('grid_search_results.json')
    
    # Example 2: Random search
    print("\n" + "=" * 70)
    print("EXAMPLE 2: RANDOM SEARCH")
    print("=" * 70)
    
    sweep2 = ParameterSweep(base_config, metric='total_throughput')
    
    param_distributions = {
        'spawn_rate': ('uniform', 0.1, 2.0),
        'grid_size': ('choice', [3, 5, 7, 10]),
        'lane_length': ('uniform', 80.0, 120.0),
    }
    
    results2 = sweep2.random_search(param_distributions, n_iterations=50, num_workers=4)
    sweep2.get_best_params(top_n=5)
    sweep2.save_results('random_search_results.json')
