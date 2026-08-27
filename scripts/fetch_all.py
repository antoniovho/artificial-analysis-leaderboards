#!/usr/bin/env python3
"""Run all collectors and succeed if at least one collector succeeds."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(script: str) -> int:
    root = Path(__file__).resolve().parent.parent
    path = root / "scripts" / script
    print(f"\n{'=' * 80}\nRunning {script}\n{'=' * 80}", flush=True)
    result = subprocess.run([sys.executable, str(path)], check=False)
    print(f"\n{script} exit code: {result.returncode}", flush=True)
    return result.returncode


def main() -> int:
    results = {
        "fetch_leaderboards.py": run("fetch_leaderboards.py"),
        "fetch_arena.py": run("fetch_arena.py"),
    }

    successful = sum(code == 0 for code in results.values())
    total = len(results)

    print(f"\nCollectors succeeded: {successful}/{total}", flush=True)

    # A collector returns 0 when at least one of its own endpoints succeeded.
    # Therefore the combined workflow is successful if at least one collector
    # produced useful data.
    if successful > 0:
        print("At least one collector succeeded. Continuing to commit.")
        return 0

    print("All collectors failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
