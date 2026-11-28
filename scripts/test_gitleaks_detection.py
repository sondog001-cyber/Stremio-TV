"""Check scanner sensitivity in an isolated temporary git repository.

The synthetic marker is never committed to this project or printed.
"""
from __future__ import annotations
import os
from pathlib import Path
import secrets
import string
import subprocess
import tempfile


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode


def main():
    with tempfile.TemporaryDirectory(prefix="gitleaks-synthetic-") as temp:
        root = Path(temp)
        assert run(["git", "init", "-q"], root) == 0
        assert run(["git", "config", "user.name", "Synthetic Scan Test"], root) == 0
        assert run(["git", "config", "user.email", "scan-test@example.invalid"], root) == 0
        alphabet = string.ascii_uppercase + string.digits
        synthetic = "AKIA" + "".join(secrets.choice(alphabet) for _ in range(16))
        (root / "synthetic.txt").write_text("synthetic_access_key_id=" + synthetic + "\n")
        assert run(["git", "add", "synthetic.txt"], root) == 0
        assert run(["git", "commit", "-qm", "temporary synthetic marker"], root) == 0
        code = run(["docker", "run", "--rm", "-v", f"{root}:/repo:ro",
                    "ghcr.io/gitleaks/gitleaks:v8.24.3", "git", "/repo",
                    "--redact", "--exit-code", "1"], root)
        if code != 1:
            print("FAIL: synthetic credential was not detected or scanner errored")
            return 1
        print("PASS: Gitleaks rejected an isolated synthetic credential; no values printed or retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
