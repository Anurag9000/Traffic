#!/usr/bin/env python3
"""One-command exhaustive Traffic simulation/scientific controller.

Traffic has no retained optimizer-training surface on the live source tree. The
repository-owned v1 authority proves that classification with an AST census and
then exposes every authored YAML simulation as an independent, output-isolated,
restart-exact OPF transaction. Legacy scenario runners are exact audited aliases of
the unified config surface; newly added unmapped scenarios or ML/training imports
fail closed instead of silently escaping orchestration.

The simulation engine remains GPU-accelerated through its native CuPy layer with
CPU fallback. Resource admission, maximal safe concurrency, CPU/GPU placement,
RAM/VRAM pressure handling, pause/relaunch, retry and process control remain
exclusively in the literal byte-pinned OPF_ADP runtime loaded through canonical
controller v37.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Anurag9000/Traffic"
CONTROLLER_COMMIT = "fd34a95d18892df7fb14d1efbb99076a7810fb91"
CONTROLLER_BLOB = "05ef472b29933f18e956c69dfb7e543921ddaff5"
CONTROLLER_URL = (
    f"https://raw.githubusercontent.com/Anurag9000/RigorousRAG/{CONTROLLER_COMMIT}/"
    "tools/universal_training_controller_entry.py"
)
RESTART_EXACT = {
    "exact_resume": True,
    "deterministic": True,
    "idempotent": True,
    "atomic_outputs": True,
}


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _audit_job() -> dict:
    return {
        "id": "audit-traffic-authority",
        "command": [sys.executable, "scripts/audit_traffic_scientific_authority_v1.py"],
        "phase": "audit",
        "family": "scientific-authority",
        "device_capable": False,
        "depends_on": [],
        "is_training_job": False,
        "resume_strategy": "restart_exact",
        "checkpoint_contract": dict(RESTART_EXACT),
        "deterministic": True,
        "idempotent": True,
        "atomic_outputs": True,
        "early_stopping_applicable": False,
        "early_stopping_exception_reason": "source/configuration audit node",
        "completion_artifacts": [
            "artifacts/training_control/traffic_scientific_authority_v1.json"
        ],
        "source_configuration_only": True,
        "execution_claim_emitted": False,
    }


PROFILE = {
    "repository": REPOSITORY,
    "scientific_authority": "training_control/traffic_scientific_authority_v1.py",
    "jobs": [_audit_job()],
    "job_catalog": {
        "path": "training_control/traffic_scientific_authority_v1.py",
        "function": "iter_jobs",
        "args": [],
        "kwargs": {},
    },
    "preferred_training_entrypoints": [],
    "preferred_dataset_entrypoints": [],
    "dynamic_registry_covers": [
        "core/**/*.py",
        "scenarios/**/*.py",
        "configs/*.yaml",
        "run.py",
        "training_control/traffic_scientific_authority_v1.py",
        "training_control/run_traffic_config_v1.py",
    ],
    "ignore_entrypoints": [
        "run_all_training.py",
        "scripts/audit_traffic_scientific_authority_v1.py",
        "training_control/traffic_scientific_authority_v1.py",
        "training_control/run_traffic_config_v1.py",
        "scenarios/cli.py",
        "scenarios/batch_runner.py",
    ],
    "strict_coverage": True,
    "require_native_resume": True,
    "require_exact_resume": True,
    "require_training_exact_resume": True,
    "require_training_early_stopping": True,
    "require_well_formed_training_exemptions": True,
    "require_dag_enforcement": True,
    "require_model_surface_accounting": True,
    "require_workload_surface_accounting": True,
    "require_literal_opf_mechanism_parity": True,
    "require_registry_member_accounting": True,
    "require_dynamic_registry_accounting": True,
    "require_scientific_component_config_accounting": True,
    "require_declared_combination_accounting": True,
    "require_scientific_ontology_accounting": True,
    "require_declarative_scientific_source_accounting": True,
    "require_extended_scientific_component_accounting": True,
    "require_full_scientific_choice_accounting": True,
    "require_role_paradigm_protocol_accounting": True,
    "require_existing_job_targets": True,
    "require_source_proven_training_exact_resume": True,
    "require_source_proven_training_early_stopping": True,
    "require_all_retained_trainable_source_reachability": True,
    "auto_console_training_jobs": False,
    "auto_console_subcommand_jobs": False,
}


def main() -> int:
    cache = ROOT / ".training_control" / "universal_training_controller_entry.py"
    if not cache.is_file() or _blob(cache.read_bytes()) != CONTROLLER_BLOB:
        payload = urllib.request.urlopen(CONTROLLER_URL, timeout=60).read()
        actual = _blob(payload)
        if actual != CONTROLLER_BLOB:
            raise RuntimeError(
                f"Pinned controller checksum mismatch: {actual} != {CONTROLLER_BLOB}"
            )
        _atomic(cache, payload)

    profile_path = ROOT / ".training_control" / "traffic_scientific_v1_v37.json"
    _atomic(
        profile_path,
        (json.dumps(PROFILE, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    env = os.environ.copy()
    env.pop("TRAINING_CONTROL_PROFILE", None)
    env["TRAINING_CONTROL_PROFILE_FILE"] = str(profile_path)
    env["TRAINING_CONTROL_REPO_ROOT"] = str(ROOT)
    env.setdefault("TRAINING_CONTROL_TERMINATION_GRACE_SEC", "30")
    return subprocess.call([sys.executable, str(cache), *sys.argv[1:]], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
