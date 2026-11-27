"""Ingest verses.csv -> data/processed/chunks.jsonl (one chunk per verse).

Usage:
    python -m ingest.ingest                 # only review_status == approved
    python -m ingest.ingest --include-draft # also draft/reviewed (development only)
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from ingest.textnorm import to_iast

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["verse_id", "source", "sanskrit", "meaning_en", "licence", "review_status"]


def split_list(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verses", default=ROOT / "data" / "verses.csv")
    ap.add_argument("--out", default=ROOT / "data" / "processed" / "chunks.jsonl")
    ap.add_argument("--include-draft", action="store_true")
    a = ap.parse_args()

    allowed = {"approved"} | ({"draft", "reviewed"} if a.include_draft else set())
    seen, chunks, errors = set(), [], []

    with open(a.verses, encoding="utf-8") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            missing = [k for k in REQUIRED if not (row.get(k) or "").strip()]
            vid = (row.get("verse_id") or "").strip()
            if missing:
                errors.append(f"line {n} ({vid or '?'}): missing {missing}")
                continue
            if vid in seen:
                errors.append(f"line {n}: duplicate verse_id {vid}")
                continue
            seen.add(vid)
            if row["review_status"].strip() not in allowed:
                continue
            iast = row.get("iast", "").strip()
            if not iast or iast.startswith("["):
                iast = to_iast(row["sanskrit"])
            chunk = {
                "id": vid,
                "source": row["source"].strip(),
                "sthana": row.get("sthana", "").strip(),
                "chapter": row.get("chapter", "").strip(),
                "verse": row.get("verse", "").strip(),
                "sanskrit": row["sanskrit"].strip(),
                "iast": iast,
                "meaning_en": row["meaning_en"].strip(),
                "meaning_hi": row.get("meaning_hi", "").strip(),
                "topics": split_list(row.get("topics")),
                "dravya": split_list(row.get("dravya")),
                "dosha": split_list(row.get("dosha")),
                "roga": split_list(row.get("roga")),
                "population": split_list(row.get("population")),
                "edition": row.get("edition", "").strip(),
                "page": row.get("page", "").strip(),
                "translator": row.get("translator", "").strip(),
                "licence": row["licence"].strip(),
                "review_status": row["review_status"].strip(),
            }
            # text used for retrieval (meaning + tags + transliteration)
            chunk["search_text"] = " ".join([
                chunk["meaning_en"], chunk["meaning_hi"], chunk["iast"],
                " ".join(chunk["topics"] + chunk["dravya"] + chunk["dosha"] + chunk["roga"]),
                chunk["source"], chunk["sthana"],
            ])
            chunks.append(chunk)

    for e in errors:
        print("WARN", e, file=sys.stderr)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {len(chunks)} chunks -> {a.out} ({len(errors)} warnings)")


if __name__ == "__main__":
    main()
