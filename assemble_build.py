"""Assemble the seven ordered builder fragments, failing closed on missing parts."""
from pathlib import Path

root = Path(__file__).resolve().parent
parts_dir = root / "build_parts"
expected = [parts_dir / f"part{i:02d}.txt" for i in range(1, 8)]
actual = sorted(parts_dir.glob("part*.txt"))
if actual != expected:
    missing = [p.name for p in expected if p not in actual]
    unexpected = [p.name for p in actual if p not in expected]
    raise SystemExit(f"Incomplete build_parts: missing={missing}, unexpected={unexpected}")
content = "".join(p.read_text(encoding="utf-8") for p in expected)
if not content.strip():
    raise SystemExit("Refusing to generate an empty builder")
(root / "build.py").write_text(content, encoding="utf-8")
print(f"Assembled build.py from {len(expected)} parts")
