import json, yaml
from pathlib import Path

VERSION = "v0_1"  # bump when you regenerate outputs

# QC mode:
# - "bilingual_strict": requires both EN and DE (use with INNER JOIN)
# - "en_canonical": requires EN; DE optional (use with LEFT JOIN)
QC_MODE = "en_canonical"

def load_jsonl(p: Path):
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out

def main():
    ev = yaml.safe_load(Path("requirements/config/evidence_types.yml").read_text(encoding="utf-8"))
    allowed = {e["code"] for e in ev["evidence_types"]}

    reqs = load_jsonl(Path(f"requirements/library/requirements__{VERSION}.jsonl"))
    aqm  = load_jsonl(Path(f"requirements/library/audit_question_map__{VERSION}.jsonl"))

    errors = []
    warnings = []
    ids = set()

    for r in reqs:
        rid = r.get("req_id", "")
        if rid in ids:
            errors.append(f"Duplicate req_id: {rid}")
        ids.add(rid)

        for t in (r.get("primary_evidence_types", []) + r.get("supporting_evidence_types", [])):
            if t not in allowed:
                errors.append(f"Unknown evidence type {t} in {rid}")

        # EN is always required
        if not (r.get("text_en") or "").strip():
            errors.append(f"Missing text_en: {rid}")

        # DE depends on QC_MODE
        if not (r.get("text_de") or "").strip():
            if QC_MODE == "bilingual_strict":
                errors.append(f"Missing text_de: {rid}")
            else:
                warnings.append(f"Missing text_de: {rid}")

    for q in aqm:
        if not q.get("related_req_ids"):
            errors.append(f"Audit question unmapped: {q.get('question_id','<missing>')}")

    report = {
        "version": VERSION,
        "qc_mode": QC_MODE,
        "requirements_count": len(reqs),
        "audit_questions_count": len(aqm),
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors_preview": errors[:50],
        "warnings_preview": warnings[:50],
    }

    out = Path(f"requirements/library/qc_report__{VERSION}.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
