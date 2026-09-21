from pathlib import Path
root=Path(__file__).resolve().parent
parts=sorted((root/"build_parts").glob("part*.txt"))
(root/"build.py").write_text("".join(p.read_text() for p in parts), encoding="utf-8")
print(f"Assembled build.py from {len(parts)} parts")
