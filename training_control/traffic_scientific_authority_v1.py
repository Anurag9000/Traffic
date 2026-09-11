#!/usr/bin/env python3
"""Source-derived scientific authority for the Traffic repository.

Traffic is a deterministic simulation repository rather than an optimizer-training
codebase.  The authority therefore does not invent fake training jobs.  It:

* discovers every authored ``configs/*.yaml`` simulation;
* discovers every standalone scientific scenario script while excluding package,
  CLI and batch-runner aliases that would create nested scheduling;
* emits one OPF-visible restart-exact transaction per retained workload; and
* provides a fail-closed source census used by the audit CLI to prove that no
  retained ML/optimizer surface is being silently omitted.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
SCENARIO_DIR = ROOT / "scenarios"
EXCLUDED_SCENARIO_FILES = {"__init__.py", "cli.py", "batch_runner.py"}
TRAINING_FRAMEWORK_ROOTS = {
    "torch", "tensorflow", "keras", "sklearn", "xgboost", "lightgbm", "catboost",
    "jax", "flax", "optax", "stable_baselines3", "ray.rllib", "transformers",
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
    trainable_findings: tuple[TrainableSurfaceFinding, ...]

    @property
    def no_trainable_surface(self) -> bool:
        return not self.trainable_findings

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "repository": "Anurag9000/Traffic",
            "configs": list(self.configs),
            "scenario_scripts": list(self.scenario_scripts),
            "trainable_findings": [asdict(row) for row in self.trainable_findings],
            "no_trainable_surface": self.no_trainable_surface,
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
    if not scenarios:
        raise RuntimeError("Traffic scientific authority found no standalone scenario scripts")
    return TrafficAuthorityAudit(
        configs=tuple(_relative(path) for path in configs),
        scenario_scripts=tuple(_relative(path) for path in scenarios),
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
            "Traffic gained a trainable/optimizer surface; do not classify it as a pure "
            f"restart-exact simulation repository until explicitly wired: {rendered}"
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
            "device_capable": False,
            "is_training_job": False,
            "depends_on": ["audit-traffic-authority"],
            "resume_strategy": "restart_exact",
            "checkpoint_contract": _restart_contract(),
            "deterministic": True,
            "idempotent": True,
            "atomic_outputs": True,
            "early_stopping_applicable": False,
            "early_stopping_exception_reason": "deterministic finite simulation, not optimizer training",
            "completion_artifacts": [f"artifacts/central_runs/configs/{stem}/COMPLETE.json"],
            "source_config": relative,
        }

    previous: str | None = None
    for relative in audit.scenario_scripts:
        stem = Path(relative).stem
        job_id = f"simulate-scenario:{stem}"
        deps = ["audit-traffic-authority"]
        # Legacy standalone scripts may use hard-coded result paths. Serialize only
        # this legacy subset to avoid file collisions; config jobs remain parallel.
        if previous is not None:
            deps.append(previous)
        yield {
            "id": job_id,
            "command": [sys.executable, relative],
            "phase": "simulation",
            "family": "traffic-legacy-scenario",
            "device_capable": False,
            "is_training_job": False,
            "depends_on": deps,
            "resume_strategy": "restart_exact",
            "checkpoint_contract": _restart_contract(),
            "deterministic": True,
            "idempotent": True,
            "atomic_outputs": False,
            "early_stopping_applicable": False,
            "early_stopping_exception_reason": "deterministic finite simulation, not optimizer training",
            "source_script": relative,
        }
        previous = job_id
