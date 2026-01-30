import json, re
from pathlib import Path
from collections import defaultdict

WS_RE = re.compile(r"\s+")

def iter_jsonl(p: Path):
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def norm_legal_ref(s: str) -> str:
    """
    Defensive normalization so EN/DE keys keep matching even if formatting shifts.
    """
    s = (s or "").strip()
    s = s.replace("Artikel", "Art.").replace("Article", "Art.")
    s = WS_RE.sub(" ", s)
    s = s.replace("Art .", "Art.")
    s = s.replace(" (", "(").replace(") ", ")")
    return s

def index_segments(records):
    """
    key -> list[records] to avoid silent overwrites.
    """
    idx = defaultdict(list)
    for r in records:
        k = (r["instrument_code"], norm_legal_ref(r["legal_ref"]))
        idx[k].append(r)
    return idx

def pick_best(rs):
    """
    Choose one record deterministically if duplicates exist.
    Heuristic: prefer non-empty text, then longest text.
    """
    rs = [r for r in rs if (r.get("text") or "").strip()]
    if not rs:
        return None
    return max(rs, key=lambda r: (len(r.get("text", "")), r.get("source_sha256", "")))

def main():
    # join_mode:
    # - "left": EN is canonical (recommended for requirements library)
    # - "inner": only bilingual keys (useful for pure alignment datasets)
    join_mode = "left"   # <-- set to "inner" if you really want only bilingual rows

    en_idx = index_segments(iter_jsonl(Path("requirements/extracted/segments__EN.jsonl")))
    de_idx = index_segments(iter_jsonl(Path("requirements/extracted/segments__DE.jsonl")))

    en_keys = set(en_idx.keys())
    de_keys = set(de_idx.keys())

    if join_mode == "inner":
        keys = sorted(en_keys & de_keys)
    else:
        keys = sorted(en_keys)  # LEFT JOIN from EN

    # Diagnostics
    dup_en = sorted([k for k, rs in en_idx.items() if len(rs) > 1])
    dup_de = sorted([k for k, rs in de_idx.items() if len(rs) > 1])

    only_en = sorted(en_keys - de_keys)
    only_de = sorted(de_keys - en_keys)

    out = Path("requirements/extracted/bilingual_segments.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    n_has_de = 0
    with out.open("w", encoding="utf-8") as f:
        for k in keys:
            r_en = pick_best(en_idx.get(k, []))
            r_de = pick_best(de_idx.get(k, []))

            if r_en is None:
                # Should never happen in left join; keep as hard guard.
                continue

            if r_de is not None:
                n_has_de += 1

            rec = {
                "instrument_code": k[0],
                "legal_ref": k[1],
                "text_en": r_en["text"],
                "text_de": (r_de["text"] if r_de else ""),
                "source_sha256_en": r_en.get("source_sha256", ""),
                "source_sha256_de": (r_de.get("source_sha256", "") if r_de else ""),
                "has_de": bool(r_de),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report = Path("requirements/extracted/bilingual_alignment_report.json")
    report.write_text(json.dumps({
        "join_mode": join_mode,
        "en_keys": len(en_keys),
        "de_keys": len(de_keys),
        "output_rows": len(keys),
        "rows_with_de": n_has_de,
        "rows_missing_de": (len(keys) - n_has_de),
        "only_en": len(only_en),
        "only_de": len(only_de),
        "duplicates_en": len(dup_en),
        "duplicates_de": len(dup_de),
        "only_en_examples": only_en[:20],
        "only_de_examples": only_de[:20],
        "duplicates_en_examples": dup_en[:20],
        "duplicates_de_examples": dup_de[:20],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out} with {len(keys)} rows (join_mode={join_mode})")
    print(f"Wrote alignment report: {report}")

if __name__ == "__main__":
    main()
