import json, re
from pathlib import Path

VERSION = "v0_1"

def parse_ref(legal_ref: str):
    m = re.match(r"Art\.?\s*(\d+)\((\d+)\)(?:\(([a-z])\))?$", (legal_ref or "").strip())
    if not m:
        return None
    art, para, point = int(m.group(1)), int(m.group(2)), m.group(3)
    return art, para, point

def evidence_map(instrument_code: str, legal_ref: str):
    parsed = parse_ref(legal_ref)
    art = parsed[0] if parsed else None

    if instrument_code == "EU_2024_2956":
        return ["REGISTER_INVENTORY"], ["PROCEDURE_RUNBOOK"]
    if instrument_code in ("EU_2025_301", "EU_2025_302"):
        return ["PROCEDURE_RUNBOOK", "INCIDENT_RECORD"], ["MONITORING_REVIEW", "POSTMORTEM"]
    if instrument_code == "EU_2024_1772":
        return ["POLICY", "PROCEDURE_RUNBOOK"], ["INCIDENT_RECORD", "TRAINING_ATTESTATION"]
    if art == 30:
        return ["CONTRACT_CLAUSE"], ["MONITORING_REVIEW", "RISK_ASSESSMENT"]
    if art in (28, 29):
        return ["REGISTER_INVENTORY", "POLICY"], ["RISK_ASSESSMENT", "DUE_DILIGENCE", "MONITORING_REVIEW", "EXIT_BCP_DR"]
    if art in (17, 18, 19, 20):
        return ["PROCEDURE_RUNBOOK", "INCIDENT_RECORD"], ["POLICY", "POSTMORTEM", "TEST_EVIDENCE", "TRAINING_ATTESTATION"]
    return ["POLICY"], ["PROCEDURE_RUNBOOK"]

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
    base = []
    t = (text or "").lower()
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
    inp = Path(f"requirements/extracted/bilingual_segments__{VERSION}.jsonl")
    if not inp.exists():
        # fallback for older naming
        inp = Path("requirements/extracted/bilingual_segments.jsonl")

    out_jsonl = Path(f"requirements/library/requirements__{VERSION}.jsonl")
    out_csv = Path(f"requirements/library/requirements__{VERSION}.csv")
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    reqs = []
    for line in inp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        seg = json.loads(line)

        instrument_code = seg.get("instrument_code", "")
        legal_ref = seg.get("legal_ref", "")
        ref = parse_ref(legal_ref)
        if not ref:
            continue

        art, para, point = ref
        req_id = f"{instrument_code}|{art}|{para}|{point or '-'}|001"
        primary, supporting = evidence_map(instrument_code, legal_ref)

        text_en = (seg.get("text_en") or "").strip()
        text_de = (seg.get("text_de") or "").strip()

        rec = {
            "req_id": req_id,
            "instrument_code": instrument_code,
            "legal_ref": legal_ref,
            "text_en": text_en,
            "text_de": text_de,
            "has_de": bool(text_de),
            "topic_tags": topic_tags(instrument_code, legal_ref),
            "primary_evidence_types": primary,
            "supporting_evidence_types": supporting,
            "keywords_en": simple_keywords(text_en, "en"),
            "keywords_de": simple_keywords(text_de, "de"),
            "source_sha256_en": seg.get("source_sha256_en",""),
            "source_sha256_de": seg.get("source_sha256_de",""),
        }
        reqs.append(rec)

    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in reqs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    import csv
    cols = list(reqs[0].keys()) if reqs else []
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in reqs:
            r2 = r.copy()
            for k in ["topic_tags","primary_evidence_types","supporting_evidence_types","keywords_en","keywords_de"]:
                r2[k] = "|".join(r2[k])
            w.writerow(r2)

    print(f"Wrote {len(reqs)} requirements: {out_jsonl} and {out_csv}")

if __name__ == "__main__":
    main()
