"""
YAML Configuration Loader for Traffic Simulations

Loads experiment YAML configs and converts them to runner parameters.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_experiment_config(config_path: str) -> Dict[str, Any]:
    """
    Load and parse a YAML experiment configuration file.
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Dictionary of configuration parameters
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if config is None:
        config = {}
    
    return config


def apply_config_defaults(config: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    Apply default values for missing config parameters.
    
    Args:
        config: Configuration dictionary
        mode: Simulation mode (grid, intersection, real)
        
    Returns:
        Configuration with defaults applied
    """
    defaults = {
        'duration': 3600.0,
        'interval': 60.0,
        'spawn_rate': 0.4,
        'seed': 42,
        'speedup': 1.0,
    }
    
    if mode == 'grid':
        defaults.update({
            'size': 10,
            'subgrid': [4, 5],
            'target_fraction': 0.0,
        })
    elif mode == 'intersection':
        defaults.update({
            'lane_length': 400.0,
        })
    elif mode == 'real':
        defaults.update({
            'map_name': 'delhi_cp.graphml',
            'radius_km': 2.0,
            'target_ratio': 0.0,
        })
    
    # Apply defaults for missing keys
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
    
    return config


def get_control_mode_from_config(config: Dict[str, Any]) -> str:
    """
    Extract control mode from config.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Control mode string: 'fixed', 'adaptive', or 'dynamic'
    """
    control_mode = config.get('control_mode', 'adaptive')
    
    # Normalize synonyms
    if control_mode in ['constant', 'fixed']:
        return 'fixed'
    elif control_mode in ['adaptive', 'dynamic']:
        return 'adaptive'
    
    return control_mode


def parse_flow_biases(config: Dict[str, Any]) -> Optional[Dict[int, float]]:
    """
    Parse flow biases from config into lane-based biases.
    
    For intersection simulations with directional flow biases.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary mapping lane IDs to bias multipliers, or None
    """
    flow_biases = config.get('flow_biases')
    if not flow_biases:
        return None
    
    # Convert directional biases to lane biases
    # Lane mapping: 0-2=South, 3-5=West, 6-8=North, 9-11=East
    lane_biases = {}
    
    if 'south_incoming' in flow_biases:
        bias = flow_biases['south_incoming']
        lane_biases.update({0: bias, 1: bias, 2: bias})
    
    if 'west_incoming' in flow_biases:
        bias = flow_biases['west_incoming']
        lane_biases.update({3: bias, 4: bias, 5: bias})
    
    if 'north_incoming' in flow_biases:
        bias = flow_biases['north_incoming']
        lane_biases.update({6: bias, 7: bias, 8: bias})
    
    if 'east_incoming' in flow_biases:
        bias = flow_biases['east_incoming']
        lane_biases.update({9: bias, 10: bias, 11: bias})
    
    return lane_biases if lane_biases else None


def load_and_prepare_config(config_path: str, mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Load YAML config and prepare it for use by runners.
    
    Args:
        config_path: Path to YAML config file
        mode: Override simulation mode (if None, uses mode from config)
        
    Returns:
        Prepared configuration dictionary
    """
    config = load_experiment_config(config_path)
    
    # Determine mode
    if mode is None:
        mode = config.get('mode', 'grid')
    
    # Apply defaults
    config = apply_config_defaults(config, mode)
    
    # Add derived parameters
    config['control_mode_str'] = get_control_mode_from_config(config)
    config['lane_biases'] = parse_flow_biases(config)
    
    return config
