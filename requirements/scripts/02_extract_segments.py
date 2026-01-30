import re, json, yaml
from pathlib import Path
import pdfplumber
import pandas as pd
from bs4 import BeautifulSoup

import csv

def load_manifest_by_path(path: str):
    m = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m[row["file_path"]] = row["sha256"]
    return m



def normalize_text(s: str) -> str:
    s = s.replace("\u00ad", "")              # soft hyphen
    s = re.sub(r"-\n", "", s)                # de-hyphenate line breaks
    s = re.sub(r"\n+", "\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

# MVP: nur die Artikel, die du wirklich brauchst (reduziert Alignment-Probleme massiv)
INCLUDE_ARTICLES = {
    "DORA_2022_2554": set(list(range(17, 21)) + list(range(28, 31))),  # 17-20, 28-30
    # Wenn du willst, kannst du später erweitern
}

# Safety: alles > 99 ist fast sicher NICHT Teil der Instrument-Artikel (z.B. "Article 114 thereof")
MAX_ARTICLE_NO = 99


ARTICLE_PAT = {
    # Heading form: "Article 19" or "Article 19 Title..." (line start).
    # Require start-of-line to avoid "Article 114 thereof" in running text.
    "en": re.compile(r"(?im)^\s*article\s+(\d+)\b[^\n]*$"),
    "de": re.compile(r"(?im)^\s*artikel\s+(\d+)\b[^\n]*$"),
}

ARTICLE_PAT_FALLBACK_EN = re.compile(r"(?i)(?:^|\n)\s*article\s+(\d+)\b")






POINT_PAT = re.compile(r"(?m)^\s*\(\s*([a-z])\s*\)\s+")

PARA_PAT = re.compile(r"(?m)^\s*(?:\(\s*(\d+)\s*\)|(\d+)\.)\s+")

def extract_html_text(html_path: Path) -> str:
    raw = html_path.read_text(encoding="utf-8", errors="ignore")

    # EUR-Lex often serves XHTML (XML). Detect and parse accordingly.
    if raw.lstrip().startswith("<?xml") or "<xhtml" in raw[:2000].lower():
        soup = BeautifulSoup(raw, "lxml-xml")   # XML parser
    else:
        soup = BeautifulSoup(raw, "lxml")       # HTML parser

    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    text = soup.get_text("\n")
    return normalize_text(text)


def extract_pdf_text(pdf_path: Path) -> str:
    parts = []
    with pdfplumber.open(str(pdf_path)) as p:
        for page in p.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
    return normalize_text("\n".join(parts))

def extract_source_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    if path.suffix.lower() in (".html", ".htm"):
        return extract_html_text(path)
    raise ValueError(f"Unsupported source type: {path}")




def split_articles(text: str, lang: str):
    pat = ARTICLE_PAT[lang]
    matches = list(pat.finditer(text))

    # fallback for EN if too few matches
    if lang == "en" and len(matches) < 10:
        matches = list(ARTICLE_PAT_FALLBACK_EN.finditer(text))

    if not matches:
        return []
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        art_no = m.group(1)
        art_block = text[start:end].strip()
        out.append((art_no, art_block))
    return out


def split_by_blank_lines(body: str):
    # Split on empty lines (most reliable separator when numbering is missing)
    parts = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
    # If PDF has no empty lines, fallback to “hard line breaks” that look like new paragraphs
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r"\n(?=[A-ZÄÖÜ])", body) if p.strip()]
    return parts



EXPECTED_MIN_PARAS = {
    19: 2,  # we at least need (1) and (2)
    30: 3,  # we at least need (1)(2)(3)
}

def split_paragraphs(art_block: str, art_no: int):
    lines = art_block.splitlines()
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    # Drop title lines until paragraph marker appears (common in EU regs)
    body_lines = body.splitlines()
    while body_lines and not re.match(r"^\s*(?:\(\s*\d+\s*\)|\d+\.)\s+", body_lines[0]):
        body_lines = body_lines[1:]
    body = "\n".join(body_lines).strip()

    paras = list(PARA_PAT.finditer(body))

    # normal path: numbering detected
    if len(paras) >= 2:
        out = []
        for i, m in enumerate(paras):
            pno = m.group(1) or m.group(2)
            start = m.start()
            end = paras[i+1].start() if i+1 < len(paras) else len(body)
            out.append((pno, body[start:end].strip()))
        # If article is known to have more paragraphs but numbering is incomplete, fallback
        exp = EXPECTED_MIN_PARAS.get(art_no)
        if exp and len(out) < exp:
            parts = split_by_blank_lines(body)
            if len(parts) >= exp:
                return [(str(i+1), parts[i]) for i in range(len(parts))]
        return out

    # fallback path: numbering missing → split by blank lines / hard breaks
    parts = split_by_blank_lines(body)
    if len(parts) >= 2:
        return [(str(i+1), parts[i]) for i in range(len(parts))]

    return [("1", body)] if body else []


def split_points(paragraph_text: str):
    pts = list(POINT_PAT.finditer(paragraph_text))
    if not pts:
        return [(None, paragraph_text)]
    out = []
    for i, m in enumerate(pts):
        letter = m.group(1)
        start = m.start()
        end = pts[i+1].start() if i+1 < len(pts) else len(paragraph_text)
        txt = paragraph_text[start:end].strip()
        out.append((letter, txt))
    return out

def emit_segments(instrument_code: str, lang: str, text: str, source_sha256: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("a", encoding="utf-8") as f:
        for art_no, art_block in split_articles(text, lang):
            art_int = int(art_no)
            if art_int > MAX_ARTICLE_NO:
                continue
            allowed = INCLUDE_ARTICLES.get(instrument_code)
            if allowed is not None and art_int not in allowed:
                continue
            paras = split_paragraphs(art_block, int(art_no))
            for pno, ptxt in paras:
                legal_ref = f"Art. {art_no}({pno})"
                rec = {
                        "instrument_code": instrument_code,
                        "lang": lang,
                        "legal_ref": legal_ref,
                        "text": ptxt.strip(),   # enthält ggf. (a)(b)(c) inline
                        "source_sha256": source_sha256,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    return n

def get_sha(manifest: pd.DataFrame, instrument_code: str, lang: str) -> str:
    mask = (manifest["instrument_code"] == instrument_code) & (manifest["lang"] == lang)
    series = manifest.loc[mask, "sha256"]   # -> Series
    if series.empty:
        raise KeyError(f"No sha256 found for ({instrument_code}, {lang}). Check sources_manifest__v0_1.csv")
    if len(series) > 1:
        # optional: warn, but take first
        #  print(f"Warning: multiple sha256 rows for ({instrument_code}, {lang}). Taking first.")
        pass
    return str(series.iloc[0])

def main():
    cfg = yaml.safe_load(Path("requirements/config/instruments.yml").read_text(encoding="utf-8"))
    manifest_by_path = load_manifest_by_path("requirements/library/sources_manifest__v0_1.csv")

    out_en = Path("requirements/extracted/segments__EN.jsonl")
    out_de = Path("requirements/extracted/segments__DE.jsonl")
    # clear outputs
    out_en.write_text("", encoding="utf-8")
    out_de.write_text("", encoding="utf-8")

    for inst in cfg["instruments"]:
        for v in inst["versions"]:
            lang = v["lang"]
            pdf_path = Path(v["path"])
            src_path = Path(v["path"])
            sha = manifest_by_path.get(str(src_path))
            if not sha:
                raise KeyError(f"No sha256 for primary file_path={src_path} in sources_manifest__v0_1.csv")
            text = extract_source_text(pdf_path)
            out_path = out_en if lang == "en" else out_de
            count = emit_segments(inst["code"], lang, text, sha, out_path)
            print(f"{inst['code']} {lang}: {count} segments")

if __name__ == "__main__":
    main()
