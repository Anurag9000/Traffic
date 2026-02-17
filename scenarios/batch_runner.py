
import yaml
import argparse
import sys
import os
import subprocess
from pathlib import Path
from copy import deepcopy

def deep_update(base, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key] = deep_update(base[key], value)
        else:
            base[key] = value
    return base

def set_nested(d, path, value):
    keys = path.split('.')
    current = d
    for k in keys[:-1]:
        current = current.setdefault(k, {})
    current[keys[-1]] = value

def main():
    parser = argparse.ArgumentParser(description="Run a parameter sweep.")
    parser.add_argument("plan", help="Path to sweep plan YAML")
    args = parser.parse_args()

    # FIX Bug #40: Validate file exists
    if not os.path.exists(args.plan):
        print(f"ERROR: Sweep plan file not found: {args.plan}")
        sys.exit(1)
    
    with open(args.plan) as f:
        plan = yaml.safe_load(f)

    # Support 'experiments' list or legacy 'base_config'
    experiment_configs = plan.get('experiments', [])
    if 'base_config' in plan:
        experiment_configs.append(plan['base_config'])
        
    if not experiment_configs:
        print("No experiments found in plan (experiments list or base_config).")
        sys.exit(1)

    # FIX Bug #41: Validate required fields exist
    if 'sweep' not in plan:
        print("ERROR: 'sweep' section missing from plan")
        sys.exit(1)
    
    sweep = plan['sweep']
    if 'parameter' not in sweep or 'values' not in sweep or 'labels' not in sweep:
        print("ERROR: sweep section must contain 'parameter', 'values', and 'labels'")
        sys.exit(1)
    
    sweep_param = sweep['parameter']
    values = sweep['values']
    labels = sweep['labels']
    
    # FIX Bug #42: Validate lengths match
    if len(values) != len(labels):
        print(f"ERROR: values ({len(values)}) and labels ({len(labels)}) must have same length")
        sys.exit(1)

    output_root = f"sweep_results_{Path(args.plan).stem}"
    os.makedirs(output_root, exist_ok=True)
    
    configs_dir = os.path.join(output_root, "_configs")
    os.makedirs(configs_dir, exist_ok=True)
    
    print(f"Starting sweep: {sweep_param} over {values}")

    for base_config_path in experiment_configs:
        print(f"=== Processing Experiment Base: {base_config_path} ===")
        
        if not os.path.exists(base_config_path):
            print(f"Experiment config not found: {base_config_path}")
            continue

        with open(base_config_path) as f:
            base_exp_config = yaml.safe_load(f)
            
        physics_config_path = base_exp_config.get('config')
        if not physics_config_path or not os.path.exists(physics_config_path):
            # Try resolving relative to experiment config?
            # Assuming paths are relative to repo root
            print(f"Physics config not found: {physics_config_path}")
            continue
            
        with open(physics_config_path) as f:
            base_physics_config = yaml.safe_load(f)

        exp_name = Path(base_config_path).stem

        for val, label in zip(values, labels):
            print(f"--- Running sweep: {exp_name} | {label} ({val}) ---")
            
            # 1. Create temp physics config
            current_physics = deepcopy(base_physics_config)
            set_nested(current_physics, sweep_param, val)
            
            phys_label = f"physics_{label}_{exp_name}"
            temp_phys_path = os.path.abspath(f"{configs_dir}/{phys_label}.yaml")
            with open(temp_phys_path, 'w') as f:
                yaml.dump(current_physics, f)
                
            # 2. Create temp experiment config
            current_exp = deepcopy(base_exp_config)
            current_exp['config'] = temp_phys_path
            
            exp_label = f"exp_{exp_name}_{label}"
            temp_exp_path = os.path.abspath(f"{configs_dir}/{exp_label}.yaml")
            with open(temp_exp_path, 'w') as f:
                yaml.dump(current_exp, f)
                
            # 3. Run Simulation
            mode = current_exp.get('mode', 'grid')
            module_name = None
            if mode == 'grid':
                module_name = "traffic_grid.python_sim.runner"
            elif mode == 'intersection':
                module_name = "traffic_intersection.python_sim.runner"
            elif mode == 'real':
                # Map to NEW real runner
                module_name = "traffic_real.runner"
            else:
                print(f"Unknown mode: {mode}")
                continue
                
            # Output specific to this variation
            run_output = f"{output_root}/{exp_name}/{label}"
            
            cmd = [sys.executable, "-m", module_name, "--run-config", temp_exp_path, "--output-dir", run_output]
            # Capture output to avoid spamming console? Or just run.
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"ERROR: Run failed for {exp_label}")
                print(f"  Command: {' '.join(cmd)}")
                print(f"  Return code: {e.returncode}")
                if e.stdout:
                    print(f"  Stdout: {e.stdout[:500]}")
                if e.stderr:
                    print(f"  Stderr: {e.stderr[:500]}")
                continue
            except Exception as e:
                print(f"ERROR: Unexpected error running {exp_label}: {e}")
                continue
                
    print(f"Sweep completed. Results in {output_root}")

if __name__ == "__main__":
    main()
