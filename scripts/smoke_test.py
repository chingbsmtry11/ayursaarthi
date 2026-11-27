"""Day 1 end-to-end check: question -> retrieved verses (-> optional AyurParam answer).

Usage:
  python -m scripts.smoke_test "What is the virya of Amalaki?"
  python -m scripts.smoke_test "giloy kis dosha ko shant karta hai" --llm
  python -m scripts.smoke_test --batch     # runs the built-in question list
"""
import argparse

from kg.graph import DravyaGraph
from retrieval.hybrid import HybridRetriever

BATCH = [
    "What is the virya of Amalaki?",
    "गुडूची के गुण क्या हैं",
    "giloy kis dosha ko shant karta hai",
    "Which herbs pacify Pitta?",
    "What does samanya and vishesha mean?",
    "What is the capital of France?",  # should retrieve nothing useful
]

PROMPT = """You are AyurSaarthi, an Ayurveda explainer. Answer ONLY from the passages below.
End every sentence with the verse ID in square brackets, e.g. [CS.Su.1.44].
If the passages do not answer the question, reply exactly: NO_SOURCE.
Do not give doses. Do not diagnose.

Passages:
{passages}

Question: {q}
Answer:"""


def show(r, g, q, use_llm):
    print("=" * 70, "\nQ:", q)
    print("   dravyas found:", [g.g.nodes[d]["name"] for d in g.find_dravyas(q)])
    hits = r.search(q, k=3)
    for h in hits:
        print(f"   {h['id']:<12} score={h['score']:.4f} {h['signals']}  | {h['meaning_en'][:70]}")
    if use_llm and hits:
        from llm.client import chat
        passages = "\n".join(f"[{h['id']}] {h['iast']}\nMeaning: {h['meaning_en']}" for h in hits)
        text, stats = chat([{"role": "user", "content": PROMPT.format(passages=passages, q=q)}])
        print("   ANSWER:", text.strip())
        print("   STATS :", stats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--batch", action="store_true")
    a = ap.parse_args()
    g = DravyaGraph()
    r = HybridRetriever(graph=g)
    print("retrieval mode:", r.mode, "| chunks:", len(r.chunks))
    print("Pitta-pacifying dravyas (graph):", g.query("PACIFIES", "Pitta"))
    for q in (BATCH if a.batch or not a.question else [a.question]):
        show(r, g, q, a.llm)


if __name__ == "__main__":
    main()
