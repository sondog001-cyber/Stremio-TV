"""Run the existing static-site builder without changing its behavior."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m stremio_tv")
    parser.add_argument("command", choices=["build"])
    args, extra = parser.parse_known_args()
    if args.command == "build":
        result = subprocess.run([sys.executable, str(ROOT / "assemble_build.py")], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
        return subprocess.run([sys.executable, str(ROOT / "build.py"), *extra], cwd=ROOT, check=False).returncode
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
