import hashlib, csv, datetime, yaml
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

cfg = yaml.safe_load(Path("requirements/config/instruments.yml").read_text(encoding="utf-8"))
rows = []
now = datetime.datetime.utcnow().isoformat()

for inst in cfg["instruments"]:
    for v in inst["versions"]:
        path = Path(v["path"])
        if not path.exists():
            raise FileNotFoundError(f"Missing: {path}")
        rows.append({
            "instrument_code": inst["code"],
            "title": inst.get("title",""),
            "lang": v["lang"],
            "file_path": str(path),
            "sha256": sha256_file(path),
            "source_url": v.get("source_url",""),
            "retrieved_at_utc": v.get("retrieved_at_utc","") or now,
        })

out = Path("requirements/library/sources_manifest__v0_1.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {out} ({len(rows)} rows)")
