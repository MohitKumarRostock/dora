import json, re
from pathlib import Path
import yaml

def parse_ref(legal_ref: str):
    # "Art. 28(3)(a)" -> (28,3,'a') or (28,3,None)
    m = re.match(r"Art\.\s*(\d+)\((\d+)\)(?:\(([a-z])\))?$", legal_ref.strip())
    if not m:
        return None
    art, para, point = int(m.group(1)), int(m.group(2)), m.group(3)
    return art, para, point

def evidence_map(instrument_code: str, legal_ref: str):
    # first-pass mapping rules (you will refine later)
    parsed = parse_ref(legal_ref)
    art = parsed[0] if parsed else None

    primary, supporting = [], []

    if instrument_code == "EU_2024_2956":
        primary = ["REGISTER_INVENTORY"]
        supporting = ["PROCEDURE_RUNBOOK"]
    elif instrument_code in ("EU_2025_301", "EU_2025_302"):
        primary = ["PROCEDURE_RUNBOOK", "INCIDENT_RECORD"]
        supporting = ["MONITORING_REVIEW", "POSTMORTEM"]
    elif instrument_code == "EU_2024_1772":
        primary = ["POLICY", "PROCEDURE_RUNBOOK"]
        supporting = ["INCIDENT_RECORD", "TRAINING_ATTESTATION"]
    elif art == 30:
        primary = ["CONTRACT_CLAUSE"]
        supporting = ["MONITORING_REVIEW", "RISK_ASSESSMENT"]
    elif art in (28, 29):
        primary = ["REGISTER_INVENTORY", "POLICY"]
        supporting = ["RISK_ASSESSMENT", "DUE_DILIGENCE", "MONITORING_REVIEW", "EXIT_BCP_DR"]
    elif art in (17, 18, 19, 20):
        primary = ["PROCEDURE_RUNBOOK", "INCIDENT_RECORD"]
        supporting = ["POLICY", "POSTMORTEM", "TEST_EVIDENCE", "TRAINING_ATTESTATION"]
    else:
        primary = ["POLICY"]
        supporting = ["PROCEDURE_RUNBOOK"]

    return primary, supporting

def topic_tags(instrument_code: str, legal_ref: str):
    parsed = parse_ref(legal_ref)
    art = parsed[0] if parsed else None
    tags = ["DORA"]
    if instrument_code == "EU_2024_2956" or art in (28, 29, 30):
        tags += ["TPRM", "RoI"]
    if instrument_code in ("EU_2024_1772","EU_2025_301","EU_2025_302") or art in (17,18,19,20):
        tags += ["INCIDENT"]
    return sorted(set(tags))

def simple_keywords(text: str, lang: str):
    # minimal seed keywords; improve later
    base = []
    t = text.lower()
    if lang == "de":
        if "informationsregister" in t or "register" in t: base += ["Informationsregister", "Register", "aktualisieren"]
        if "vorfall" in t or "zwischenfall" in t: base += ["IKT-Vorfall", "Klassifikation", "Meldung"]
        if "vertrag" in t: base += ["Vertrag", "Klausel", "Prüfrechte"]
    else:
        if "register" in t: base += ["register of information", "update", "maintain"]
        if "incident" in t: base += ["incident", "classification", "reporting"]
        if "contract" in t: base += ["contract", "clause", "audit rights"]
    return sorted(set(base))

def main():
    inp = Path("requirements/extracted/bilingual_segments.jsonl")
    out_jsonl = Path("requirements/library/requirements__v0_1.jsonl")
    out_csv = Path("requirements/library/requirements__v0_1.csv")
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    reqs = []
    for line in inp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        seg = json.loads(line)
        instrument_code = seg["instrument_code"]
        legal_ref = seg["legal_ref"]
        ref = parse_ref(legal_ref)
        if not ref:
            continue

        art, para, point = ref
        req_id = f"{instrument_code}|{art}|{para}|{point or '-'}|001"  # v0: 1 per segment
        primary, supporting = evidence_map(instrument_code, legal_ref)

        rec = {
            "req_id": req_id,
            "instrument_code": instrument_code,
            "legal_ref": legal_ref,
            "text_en": seg["text_en"],
            "text_de": seg["text_de"],
            "topic_tags": topic_tags(instrument_code, legal_ref),
            "primary_evidence_types": primary,
            "supporting_evidence_types": supporting,
            "keywords_en": simple_keywords(seg["text_en"], "en"),
            "keywords_de": simple_keywords(seg["text_de"], "de"),
            "source_sha256_en": seg["source_sha256_en"],
            "source_sha256_de": seg["source_sha256_de"],
        }
        reqs.append(rec)

    # write JSONL
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in reqs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # write CSV
    import csv
    cols = list(reqs[0].keys()) if reqs else []
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in reqs:
            r2 = r.copy()
            # lists -> pipe-joined for CSV
            for k in ["topic_tags","primary_evidence_types","supporting_evidence_types","keywords_en","keywords_de"]:
                r2[k] = "|".join(r2[k])
            w.writerow(r2)

    print(f"Wrote {len(reqs)} requirements: {out_jsonl} and {out_csv}")

if __name__ == "__main__":
    main()
