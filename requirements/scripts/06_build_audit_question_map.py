import yaml, json
from pathlib import Path

def load_req(req_jsonl: Path):
    reqs = []
    for line in req_jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            reqs.append(json.loads(line))
    return reqs

def main():
    aq = yaml.safe_load(Path("requirements/config/audit_questions_de_en.yml").read_text(encoding="utf-8"))["audit_questions"]
    reqs = load_req(Path("requirements/library/requirements__v0_1.jsonl"))

    out = Path("requirements/library/audit_question_map__v0_1.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        for q in aq:
            wf = q["workflow"]
            # very simple mapping:
            if wf in ("ROI","TPRM"):
                related = [r["req_id"] for r in reqs if ("RoI" in r["topic_tags"] or "TPRM" in r["topic_tags"])]
            else:
                related = [r["req_id"] for r in reqs if "INCIDENT" in r["topic_tags"]]
            rec = {
                "question_id": q["id"],
                "workflow": wf,
                "text_de": q["text_de"],
                "text_en": q["text_en"],
                "required_evidence_types": q["required_evidence_types"],
                "related_req_ids": related[:80]  # cap for v0; refine later
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
