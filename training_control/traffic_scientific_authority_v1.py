#!/usr/bin/env python3
"""Source-derived scientific authority for the Traffic repository.

Traffic is a deterministic simulation repository rather than an optimizer-training
codebase. The authority therefore does not invent fake training jobs. It:

* discovers every authored ``configs/*.yaml`` simulation;
* proves every retained standalone scenario runner is represented by the unified
  config surface (or fails closed when a new unmapped runner appears);
* emits one independently OPF-scheduled, output-isolated restart-exact transaction
  per authored config; and
* performs a retained-source census so a future ML/optimizer surface cannot be
  silently hidden behind the current ``no trainable surface`` classification.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Iterator

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
SCENARIO_DIR = ROOT / "scenarios"
EXCLUDED_SCENARIO_FILES = {"__init__.py", "cli.py", "batch_runner.py"}
# The refactored repository documents the unified YAML runner as feature-parity
# authority. These mappings make legacy execution aliases explicit instead of
# silently ignoring them or running nested/duplicate campaigns.
SCENARIO_ALIAS_CONFIGS: dict[str, tuple[str, ...]] = {
    "experiment_speed_threshold.py": ("configs/experiment_speed_threshold.yaml",),
    "experiment_velocity_invariant.py": (
        "configs/experiment_velocity_30.yaml",
        "configs/experiment_velocity_40.yaml",
    ),
    "grid_targeted.py": ("configs/grid_targeted.yaml",),
    "intersection_directional.py": ("configs/intersection_directional.yaml",),
    "parameter_sweep.py": (
        "configs/experiment_speed_threshold.yaml",
        "configs/experiment_velocity_30.yaml",
        "configs/experiment_velocity_40.yaml",
    ),
    "real_map_runner.py": (
        "configs/delhi_baseline.yaml",
        "configs/delhi_fixed.yaml",
        "configs/delhi_targeted.yaml",
        "configs/real_loose.yaml",
        "configs/real_strict.yaml",
    ),
}
TRAINING_FRAMEWORK_ROOTS = {
    "torch", "tensorflow", "keras", "sklearn", "xgboost", "lightgbm", "catboost",
    "jax", "flax", "optax", "stable_baselines3", "transformers",
}
TRAINING_CALL_NAMES = {
    "fit", "partial_fit", "fit_transform", "backward", "train_step",
    "gradient", "grad", "minimize", "optimizer_step",
}


@dataclass(frozen=True, slots=True)
class TrainableSurfaceFinding:
    path: str
    line: int
    kind: str
    symbol: str


@dataclass(frozen=True, slots=True)
class TrafficAuthorityAudit:
    configs: tuple[str, ...]
    scenario_scripts: tuple[str, ...]
    scenario_aliases: dict[str, tuple[str, ...]]
    trainable_findings: tuple[TrainableSurfaceFinding, ...]

    @property
    def no_trainable_surface(self) -> bool:
        return not self.trainable_findings

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "repository": "Anurag9000/Traffic",
            "configs": list(self.configs),
            "scenario_scripts": list(self.scenario_scripts),
            "scenario_aliases": {key: list(value) for key, value in self.scenario_aliases.items()},
            "trainable_findings": [asdict(row) for row in self.trainable_findings],
            "no_trainable_surface": self.no_trainable_surface,
            "unified_config_surface_is_execution_authority": True,
            "legacy_scenario_scripts_are_explicit_aliases": True,
            "source_configuration_only": True,
            "execution_claim_emitted": False,
            "training_claim_emitted": False,
        }


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def discover_configs() -> tuple[Path, ...]:
    return tuple(sorted(path for path in CONFIG_DIR.glob("*.yaml") if path.is_file()))


def discover_scenario_scripts() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in SCENARIO_DIR.glob("*.py")
            if path.is_file() and path.name not in EXCLUDED_SCENARIO_FILES
        )
    )


def _call_name(node: ast.Call) -> str | None:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def census_trainable_surface() -> tuple[TrainableSurfaceFinding, ...]:
    findings: list[TrainableSurfaceFinding] = []
    for path in sorted(ROOT.rglob("*.py")):
        relative = _relative(path)
        if relative.startswith(("tests/", ".training_control/", "training_control/")):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise RuntimeError(f"cannot AST-audit retained source {relative}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    root = name.split(".", 1)[0]
                    if name in TRAINING_FRAMEWORK_ROOTS or root in TRAINING_FRAMEWORK_ROOTS:
                        findings.append(TrainableSurfaceFinding(relative, node.lineno, "import", name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                name = node.module
                root = name.split(".", 1)[0]
                if name in TRAINING_FRAMEWORK_ROOTS or root in TRAINING_FRAMEWORK_ROOTS:
                    findings.append(TrainableSurfaceFinding(relative, node.lineno, "import", name))
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if name in TRAINING_CALL_NAMES:
                    findings.append(TrainableSurfaceFinding(relative, node.lineno, "call", str(name)))
    return tuple(findings)


def audit_authority() -> TrafficAuthorityAudit:
    configs = discover_configs()
    scenarios = discover_scenario_scripts()
    if not configs:
        raise RuntimeError("Traffic scientific authority found no authored YAML configs")
    config_names = {_relative(path) for path in configs}
    for path in configs:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Traffic config must contain a YAML object: {_relative(path)}")
        mode = str(payload.get("mode", "grid"))
        if mode not in {"grid", "intersection", "real"}:
            raise ValueError(f"unknown Traffic mode {mode!r} in {_relative(path)}")
        simulation = payload.get("simulation", {}) or {}
        if not isinstance(simulation, dict):
            raise ValueError(f"simulation must be a mapping in {_relative(path)}")
        duration = float(simulation.get("duration", 3600.0))
        dt = float(simulation.get("dt", 0.1))
        if duration <= 0 or dt <= 0:
            raise ValueError(f"non-positive duration/dt in {_relative(path)}")

    scenario_names = {_relative(path) for path in scenarios}
    expected_names = {f"scenarios/{name}" for name in SCENARIO_ALIAS_CONFIGS}
    unmapped = sorted(scenario_names - expected_names)
    stale_aliases = sorted(expected_names - scenario_names)
    if unmapped or stale_aliases:
        raise RuntimeError(
            "Traffic legacy-scenario alias closure drifted: "
            f"unmapped={unmapped} stale_aliases={stale_aliases}"
        )
    for script_name, aliases in SCENARIO_ALIAS_CONFIGS.items():
        missing = [value for value in aliases if value not in config_names]
        if missing:
            raise RuntimeError(f"scenario alias {script_name} references missing configs {missing}")

    return TrafficAuthorityAudit(
        configs=tuple(sorted(config_names)),
        scenario_scripts=tuple(sorted(scenario_names)),
        scenario_aliases=dict(SCENARIO_ALIAS_CONFIGS),
        trainable_findings=census_trainable_surface(),
    )


def _restart_contract() -> dict[str, object]:
    return {
        "exact_resume": True,
        "deterministic": True,
        "idempotent": True,
        "atomic_outputs": True,
    }


def iter_jobs() -> Iterator[dict[str, object]]:
    audit = audit_authority()
    if not audit.no_trainable_surface:
        rendered = ", ".join(
            f"{row.path}:{row.line}:{row.symbol}" for row in audit.trainable_findings
        )
        raise RuntimeError(
            "Traffic gained a trainable/optimizer surface; it must be explicitly wired "
            f"before launch: {rendered}"
        )

    for relative in audit.configs:
        stem = Path(relative).stem
        yield {
            "id": f"simulate-config:{stem}",
            "command": [
                sys.executable,
                "training_control/run_traffic_config_v1.py",
                "--config",
                relative,
            ],
            "phase": "simulation",
            "family": "traffic-config",
            "device_capable": True,
            "is_training_job": False,
            "depends_on": ["audit-traffic-authority"],
            "resume_strategy": "restart_exact",
            "checkpoint_contract": _restart_contract(),
            "deterministic": True,
            "idempotent": True,
            "atomic_outputs": True,
            "early_stopping_applicable": False,
            "early_stopping_exception_reason": "finite deterministic simulation, not optimizer training",
            "completion_artifacts": [f"artifacts/central_runs/configs/{stem}/COMPLETE.json"],
            "source_config": relative,
            "gpu_acceleration_capable": True,
            "cpu_fallback_capable": True,
        }
