"""Generate credential-safe failure issue text without incorporating build output."""
from __future__ import annotations
import re


def issue_body(run_url: str) -> str:
    # Do not include logs, environment variables, playlist URLs, or exceptions.
    if not re.fullmatch(r"https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+", run_url):
        return "A deployment failed. Inspect the Actions page for this repository."
    return ("A deployment failed. Review the GitHub Actions run: " + run_url
            + ". This issue intentionally excludes build logs and credentials.")
