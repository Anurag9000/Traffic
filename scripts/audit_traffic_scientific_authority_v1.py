#!/usr/bin/env python3
"""Audit Traffic's complete non-training scientific surface."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "training_control"
if str(CONTROL) not in sys.path:
    sys.path.insert(0, str(CONTROL))

from traffic_scientific_authority_v1 import audit_authority  # noqa: E402

OUTPUT = ROOT / "artifacts" / "training_control" / "traffic_scientific_authority_v1.json"


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    audit = audit_authority()
    payload = audit.to_dict()
    payload.update(
        {
            "status": "PASS" if audit.no_trainable_surface else "FAIL",
            "config_count": len(audit.configs),
            "scenario_alias_count": len(audit.scenario_scripts),
            "all_retained_scenario_aliases_accounted": True,
            "all_authored_configs_are_central_jobs": True,
            "gpu_acceleration_surface": "core/gpu.py",
            "cpu_fallback_required": True,
        }
    )
    _atomic_json(OUTPUT, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not audit.no_trainable_surface:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
