"""
Centralized path utilities for Traffic Simulator.
Provides project-relative paths for cross-platform compatibility.
"""

import os

# Project root directory (parent of utils/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_project_root() -> str:
    """
    Get the absolute path to the project root directory.
    
    Returns:
        str: Absolute path to project root
    """
    return PROJECT_ROOT

def get_results_dir(subdir: str = "") -> str:
    """
    Get results directory path, creating if needed.
    
    Args:
        subdir: Optional subdirectory within results/ (e.g., "directional", "targeted")
    
    Returns:
        str: Absolute path to results directory
    """
    if subdir:
        path = os.path.join(PROJECT_ROOT, "results", subdir)
    else:
        path = os.path.join(PROJECT_ROOT, "results")
    
    os.makedirs(path, exist_ok=True)
    return path

def get_config_path(filename: str) -> str:
    """
    Get absolute path to a config file.
    
    Args:
        filename: Config filename (can include subdirs, e.g., "physics/standard.yaml")
    
    Returns:
        str: Absolute path to config file
    """
    return os.path.join(PROJECT_ROOT, "configs", filename)

def get_output_dir(dirname: str) -> str:
    """
    Get output directory path (e.g., for diagrams, exports), creating if needed.
    
    Args:
        dirname: Directory name within project root
    
    Returns:
        str: Absolute path to output directory
    """
    path = os.path.join(PROJECT_ROOT, dirname)
    os.makedirs(path, exist_ok=True)
    return path
