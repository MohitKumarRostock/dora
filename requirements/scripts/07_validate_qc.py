import json, yaml
from pathlib import Path

def load_jsonl(p: Path):
    out=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip(): out.append(json.loads(line))
    return out

def main():
    ev = yaml.safe_load(Path("requirements/config/evidence_types.yml").read_text(encoding="utf-8"))
    allowed = {e["code"] for e in ev["evidence_types"]}

    reqs = load_jsonl(Path("requirements/library/requirements__v0_1.jsonl"))
    aqm  = load_jsonl(Path("requirements/library/audit_question_map__v0_1.jsonl"))

    errors = []
    ids = set()

    for r in reqs:
        if r["req_id"] in ids:
            errors.append(f"Duplicate req_id: {r['req_id']}")
        ids.add(r["req_id"])
        for t in r["primary_evidence_types"] + r["supporting_evidence_types"]:
            if t not in allowed:
                errors.append(f"Unknown evidence type {t} in {r['req_id']}")
        if not r.get("text_de"):
            errors.append(f"Missing text_de: {r['req_id']}")
        if not r.get("text_en"):
            errors.append(f"Missing text_en: {r['req_id']}")

    for q in aqm:
        if not q["related_req_ids"]:
            errors.append(f"Audit question unmapped: {q['question_id']}")

    report = {
        "requirements_count": len(reqs),
        "audit_questions_count": len(aqm),
        "errors_count": len(errors),
        "errors_preview": errors[:50],
    }
    out = Path("requirements/library/qc_report__v0_1.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
