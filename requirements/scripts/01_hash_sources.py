import hashlib, csv, datetime, yaml
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def infer_format(p: Path) -> str:
    suf = p.suffix.lower()
    if suf in (".html", ".htm", ".xhtml"):
        return "html"
    if suf == ".pdf":
        return "pdf"
    return suf.lstrip(".") or "unknown"

cfg = yaml.safe_load(Path("requirements/config/instruments.yml").read_text(encoding="utf-8"))
rows = []
now = datetime.datetime.utcnow().isoformat()

for inst in cfg["instruments"]:
    for v in inst["versions"]:
        # Primary source (always hashed)
        primary_path = Path(v["path"])
        if not primary_path.exists():
            raise FileNotFoundError(f"Missing primary: {primary_path}")

        rows.append({
            "instrument_code": inst["code"],
            "title": inst.get("title",""),
            "lang": v["lang"],
            "artifact_role": "primary",
            "artifact_format": infer_format(primary_path),
            "file_path": str(primary_path),
            "sha256": sha256_file(primary_path),
            "source_url": v.get("source_url",""),
            "retrieved_at_utc": v.get("retrieved_at_utc","") or now,
        })

        # Optional extra artifacts (PDF copies etc.)
        for a in v.get("artifacts", []):
            ap = Path(a["path"])
            if not ap.exists():
                raise FileNotFoundError(f"Missing artifact: {ap}")

            rows.append({
                "instrument_code": inst["code"],
                "title": inst.get("title",""),
                "lang": v["lang"],
                "artifact_role": a.get("role", "secondary"),
                "artifact_format": a.get("format", infer_format(ap)),
                "file_path": str(ap),
                "sha256": sha256_file(ap),
                "source_url": a.get("source_url",""),
                "retrieved_at_utc": v.get("retrieved_at_utc","") or now,
            })

out = Path("requirements/library/sources_manifest__v0_1.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {out} ({len(rows)} rows)")
