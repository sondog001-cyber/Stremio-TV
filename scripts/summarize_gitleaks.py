"""Print safe Gitleaks finding metadata only; never print findings or snippets."""
from __future__ import annotations
import collections
import json
import sys
from pathlib import Path


def summarize(records):
    by_rule = collections.Counter(str(x.get("RuleID", "unknown")) for x in records)
    by_file = collections.Counter(str(x.get("File", "unknown")) for x in records)
    return len(records), by_rule, by_file


def main(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    count, by_rule, by_file = summarize(records)
    print(f"Gitleaks findings: {count} (metadata only; no secrets or matches printed)")
    for rule, number in sorted(by_rule.items()):
        print(f"Rule: {rule} | occurrences: {number}")
    for file, number in sorted(by_file.items()):
        # Only print a file path if it contains no control characters.
        if file.isprintable() and len(file) < 200:
            print(f"File: {file} | occurrences: {number}")
    for row in records:
        commit = str(row.get("Commit", "unknown"))
        line = row.get("StartLine", "unknown")
        rule = str(row.get("RuleID", "unknown"))
        file = str(row.get("File", "unknown"))
        print(f"Finding: rule={rule} file={file} commit={commit} line={line}")
    return 1 if count else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
