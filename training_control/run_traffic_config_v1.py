#!/usr/bin/env python3
"""Run one Traffic YAML in an isolated, restart-exact output transaction."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    return parser


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = _parser().parse_args()
    source = (ROOT / args.config).resolve()
    try:
        relative = source.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"config escapes repository root: {source}") from exc
    if not source.is_file() or source.suffix.lower() not in {".yaml", ".yml"}:
        raise FileNotFoundError(source)

    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Traffic config must contain a YAML object: {relative}")

    stem = source.stem
    final = ROOT / "artifacts" / "central_runs" / "configs" / stem
    work = final.with_name(f".{stem}.work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=False)

    effective = dict(payload)
    output = effective.get("output", {}) or {}
    if not isinstance(output, dict):
        raise ValueError(f"output must be a mapping in {relative}")
    output = dict(output)
    output_dir = work / "output"
    output["output_dir"] = str(output_dir)
    effective["output"] = output
    effective_path = work / "effective.yaml"
    effective_path.write_text(
        yaml.safe_dump(effective, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["TRAFFIC_CENTRAL_RUN_SOURCE_CONFIG"] = relative.as_posix()
    subprocess.run(
        [sys.executable, "run.py", str(effective_path)],
        cwd=ROOT,
        env=env,
        check=True,
    )

    if final.exists():
        shutil.rmtree(final)
    os.replace(work, final)
    _atomic_json(
        final / "COMPLETE.json",
        {
            "schema_version": 1,
            "status": "complete",
            "source_config": relative.as_posix(),
            "source_sha256": _sha256(source),
            "effective_config_sha256": _sha256(final / "effective.yaml"),
            "mode": str(payload.get("mode", "grid")),
            "seed": int((payload.get("simulation", {}) or {}).get("seed", 42)),
            "restart_exact": True,
            "fresh_work_directory_per_attempt": True,
            "isolated_output_directory": True,
            "training_claim_emitted": False,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
