"""Run every question in data/eval.csv through AyurSaarthi and check the behaviour.

Usage:
  python -m scripts.day2_test            # with AyurParam
  MOCK_LLM=1 python -m scripts.day2_test # logic only, no model
Writes eval/day2_results.csv and prints a pass/fail summary per category.
"""
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from agents.pipeline import AyurSaarthi

ROOT = Path(__file__).resolve().parents[1]
EXPECT = {  # expected -> acceptable statuses
    "answer": {"answered"}, "emergency": {"emergency"}, "refuse": {"refused"},
    "abstain": {"no_source", "refused"}, "warn": {"answered"}, "answer_with_policy": {"answered", "no_source", "refused"},
}


def run_one(app, row):
    cat, q, exp = row["category"], row["question"], row["expected"]
    if cat == "route":
        r = app.route(q)
        got = r.get("suggestions", [{}])[0].get("department", r["status"]) if r["status"] == "answered" else r["status"]
        ok = (r["status"] == "answered" and exp.split(" (")[0].split(" /")[0] in
              " ".join(s["department"] for s in r.get("suggestions", [])))
        return r, got, ok
    if cat == "prescription":
        r = app.explain_prescription(q)
        if r["status"] == "no_source":  # concept questions about terms -> fall back to ask()
            r = app.ask(q)
        return r, r["status"], r["status"] == "answered"
    r = app.ask(q)
    ok = r["status"] in EXPECT.get(exp, {exp})
    if exp == "warn":
        ok = ok and any(w["level"] in ("stop", "caution") for w in r.get("warnings", []))
    if exp == "answer_with_policy":
        import re as _re
        from safety.suraksha import CURE_SENTENCE_MSG, SCOPE_MSG
        txt = r["answer"].replace(CURE_SENTENCE_MSG, "").replace(SCOPE_MSG["cure_claim"], "").lower()
        ok = ok and not _re.search(r"\bcur(ed|able)\b|permanent(ly)? cur", txt)
    return r, r["status"], ok


def main():
    app = AyurSaarthi(use_llm=os.getenv("MOCK_LLM") != "1" or True)
    rows = list(csv.DictReader(open(ROOT / "data" / "eval.csv", encoding="utf-8")))
    out, by_cat = [], defaultdict(Counter)
    for row in rows:
        r, got, ok = run_one(app, row)
        by_cat[row["category"]]["pass" if ok else "fail"] += 1
        cites = ";".join(c["verse_id"] for c in r.get("citations", []) if c)
        out.append({"id": row["id"], "category": row["category"], "question": row["question"],
                    "expected": row["expected"], "got": got, "pass": ok, "citations": cites,
                    "latency_s": r.get("latency_s"), "answer": r["answer"][:300],
                    "warnings": " | ".join(w["text"] for w in r.get("warnings", [])),
                    "removed_by_verifier": json.dumps(r.get("removed_by_verifier", []), ensure_ascii=False)})
        mark = "PASS" if ok else "FAIL"
        print(f"{mark} {row['id']} [{row['category']}] {row['question'][:55]:<55} -> {got} {cites}")
    (ROOT / "eval").mkdir(exist_ok=True)
    with open(ROOT / "eval" / "day2_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out[0].keys())
        w.writeheader()
        w.writerows(out)
    total = sum(c["pass"] for c in by_cat.values())
    print("\n=== Summary ===")
    for cat, c in sorted(by_cat.items()):
        print(f"{cat:<20} {c['pass']}/{c['pass'] + c['fail']}")
    print(f"TOTAL {total}/{len(rows)}  -> eval/day2_results.csv")


if __name__ == "__main__":
    main()
