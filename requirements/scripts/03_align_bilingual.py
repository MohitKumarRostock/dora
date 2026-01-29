import json
from pathlib import Path

def load_jsonl(p: Path):
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out

def main():
    en = load_jsonl(Path("requirements/extracted/segments__EN.jsonl"))
    de = load_jsonl(Path("requirements/extracted/segments__DE.jsonl"))

    key_en = {(r["instrument_code"], r["legal_ref"]): r for r in en}
    key_de = {(r["instrument_code"], r["legal_ref"]): r for r in de}

    # INNER JOIN: keep only bilingual keys
    common_keys = set(key_en.keys()) & set(key_de.keys())
    keys = sorted(common_keys)

    only_en = sorted(set(key_en.keys()) - set(key_de.keys()))
    only_de = sorted(set(key_de.keys()) - set(key_en.keys()))

    out = Path("requirements/extracted/bilingual_segments.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        for k in keys:
            r_en = key_en[k]
            r_de = key_de[k]
            rec = {
                "instrument_code": k[0],
                "legal_ref": k[1],
                "text_en": r_en["text"],
                "text_de": r_de["text"],
                "source_sha256_en": r_en["source_sha256"],
                "source_sha256_de": r_de["source_sha256"],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report = Path("requirements/extracted/bilingual_alignment_report.json")
    report.write_text(json.dumps({
        "en_keys": len(key_en),
        "de_keys": len(key_de),
        "common_keys": len(common_keys),
        "only_en": len(only_en),
        "only_de": len(only_de),
        "only_en_examples": only_en[:20],
        "only_de_examples": only_de[:20],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out} with {len(keys)} bilingual segments")
    print(f"Wrote alignment report: {report}")

if __name__ == "__main__":
    main()
