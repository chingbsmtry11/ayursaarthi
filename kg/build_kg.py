"""Build the Dravya knowledge graph from dravya.csv -> data/processed/kg.json.

Lightweight stand-in for Neo4j in Phase 2: nodes + typed edges, every edge
carries the verse IDs that support it. Loaded with networkx at query time.

Usage: python -m kg.build_kg [--include-draft]
"""
import argparse
import csv
import json
from pathlib import Path

from ingest.textnorm import phrase

ROOT = Path(__file__).resolve().parents[1]

# column -> edge type
EDGE_COLS = {
    "rasa": "HAS_RASA", "guna": "HAS_GUNA", "virya": "HAS_VIRYA",
    "vipaka": "HAS_VIPAKA", "prabhava": "HAS_PRABHAVA", "karma": "HAS_KARMA",
    "dosha_pacifies": "PACIFIES", "dosha_aggravates": "AGGRAVATES",
    "contraindicated_in": "CONTRAINDICATED_IN", "part_used": "PART_USED",
}
NODE_TYPE = {
    "HAS_RASA": "Rasa", "HAS_GUNA": "Guna", "HAS_VIRYA": "Virya", "HAS_VIPAKA": "Vipaka",
    "HAS_PRABHAVA": "Prabhava", "HAS_KARMA": "Karma", "PACIFIES": "Dosha",
    "AGGRAVATES": "Dosha", "CONTRAINDICATED_IN": "Population", "PART_USED": "Part",
}


def split_list(v):
    return [x.strip() for x in (v or "").split(";") if x.strip() and not x.strip().startswith("[")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dravya", default=ROOT / "data" / "dravya.csv")
    ap.add_argument("--out", default=ROOT / "data" / "processed" / "kg.json")
    ap.add_argument("--include-draft", action="store_true")
    a = ap.parse_args()
    allowed = {"approved"} | ({"draft", "reviewed"} if a.include_draft else set())

    nodes, edges, aliases = {}, [], {}
    with open(a.dravya, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("review_status", "").strip() not in allowed:
                continue
            did = row["dravya_id"].strip()
            name = row["sanskrit_name"].strip()
            verses = split_list(row.get("verse_ids"))
            nodes[did] = {
                "id": did, "type": "Dravya", "name": name,
                "devanagari": row.get("devanagari", "").strip(),
                "hindi_name": row.get("hindi_name", "").strip(),
                "assamese_name": row.get("assamese_name", "").strip(),
                "english_name": row.get("english_name", "").strip(),
                "botanical_name": row.get("botanical_name", "").strip(),
                "caution_notes": row.get("caution_notes", "").strip(),
                "verse_ids": verses,
            }
            # every name a user might type -> dravya id
            names = [name, row.get("devanagari", ""), row.get("hindi_name", ""),
                     row.get("assamese_name", "").split("[")[0], row.get("english_name", ""),
                     row.get("botanical_name", "")] + split_list(row.get("synonyms"))
            for n in names:
                if n and n.strip():
                    aliases[phrase(n.strip())] = did
            for col, etype in EDGE_COLS.items():
                for val in split_list(row.get(col)):
                    tid = f"{NODE_TYPE[etype]}:{val}"
                    nodes.setdefault(tid, {"id": tid, "type": NODE_TYPE[etype], "name": val})
                    edges.append({"src": did, "type": etype, "dst": tid, "verse_ids": verses})

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"nodes": list(nodes.values()), "edges": edges, "aliases": aliases},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_d = sum(1 for n in nodes.values() if n["type"] == "Dravya")
    print(f"KG: {n_d} dravyas, {len(nodes)} nodes, {len(edges)} edges -> {a.out}")


if __name__ == "__main__":
    main()
