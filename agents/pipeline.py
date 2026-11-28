"""AyurSaarthi agents: M5 Dravya Kosha / question answering, M3 prescription explainer,
M1 department navigator. All share one retriever, one knowledge graph and the Suraksha layer.

Rule of the design: AyurParam explains; it never decides.
- Citations are attached by code from the retrieved verses, never written by the model.
- "No source" is decided by the retrieval gate, never by the model.
- Herb properties come from the reviewed dravya table, never from the model.
- Routing comes from the expert department map, never from the model.
"""
import csv
import re
import time
from pathlib import Path

from ingest.textnorm import phrase, tokens
from kg.graph import DravyaGraph
from retrieval.hybrid import HybridRetriever
from safety import suraksha as S

ROOT = Path(__file__).resolve().parents[1]
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
STOP = ["\n\n", "[", "Question:", "Passage", "Meaning:", "Sanskrit:"]

EXPLAIN_SYS = ("You are an Ayurveda teacher. Explain the classical passage in simple words in 2 or 3 "
               "short sentences, answering the user's question. Use only what the passage and the "
               "listed properties say. Do not mention verse numbers. Do not give doses. "
               "Do not promise cures.")


def _lang(text):
    return "hi" if DEVANAGARI.search(text) else "en"


class AyurSaarthi:
    def __init__(self, use_llm=True):
        self.graph = DravyaGraph()
        self.retriever = HybridRetriever(graph=self.graph)
        self.redflags = S.RedFlags()
        self.departments = list(csv.DictReader(open(ROOT / "data" / "departments.csv", encoding="utf-8")))
        self.glossary = list(csv.DictReader(open(ROOT / "data" / "glossary.csv", encoding="utf-8")))
        self.chunk_by_id = {c["id"]: c for c in self.retriever.chunks}
        self.use_llm = use_llm

    # ------------------------------------------------------------ helpers
    def _citation(self, vid):
        c = self.chunk_by_id.get(vid)
        if not c:
            return None
        return {"verse_id": vid, "source": c["source"], "section": c["sthana"], "verse": c["verse"],
                "sanskrit": c["sanskrit"], "iast": c["iast"], "meaning": c["meaning_en"],
                "edition": c["edition"], "review_status": c["review_status"]}

    def _profile_text(self, did):
        p = self.graph.profile(did)
        pr = p["properties"]
        def j(k):
            return ", ".join(pr.get(k, [])) or "-"
        return {"name": p["name"], "devanagari": p.get("devanagari", ""),
                "hindi": p.get("hindi_name", ""), "english": p.get("english_name", ""),
                "botanical": p.get("botanical_name", ""),
                "rasa": j("HAS_RASA"), "guna": j("HAS_GUNA"), "virya": j("HAS_VIRYA"),
                "vipaka": j("HAS_VIPAKA"), "karma": j("HAS_KARMA"),
                "pacifies": j("PACIFIES"), "aggravates": j("AGGRAVATES"),
                "avoid_in": j("CONTRAINDICATED_IN"), "caution": p.get("caution_notes", ""),
                "verse_ids": p.get("verse_ids", [])}

    def _explain(self, question, passage, facts=""):
        if not self.use_llm:
            return passage["meaning_en"], {"llm": False}
        from llm.client import chat
        lang = "Answer in Hindi." if _lang(question) == "hi" else "Answer in English."
        user = (f"Sanskrit: {passage['sanskrit']}\nMeaning: {passage['meaning_en']}\n"
                + (f"Properties from the reviewed table: {facts}\n" if facts else "")
                + f"\nUser question: {question}\n{lang}")
        try:
            text, stats = chat([{"role": "system", "content": EXPLAIN_SYS},
                                {"role": "user", "content": user}],
                               max_tokens=160, temperature=0.1, stop=STOP)
            return text.strip(), stats
        except Exception as e:  # model down -> fall back to the reviewed meaning
            return passage["meaning_en"], {"llm_error": str(e)}

    def _glossary_lookup(self, text):
        f = " " + phrase(text) + " "
        for g in self.glossary:
            names = [g["term"], g["devanagari"]] + [x for x in g["synonyms"].split(";") if x]
            if any(n and f" {phrase(n)} " in f for n in names):
                return g
        return None

    def _cite_hits(self, hits, dravyas):
        """Cite the top passage; add the second only if it is the herb's own verse or a strong keyword hit."""
        own = {v for d in dravyas for v in self.graph.g.nodes[d].get("verse_ids", [])}
        out = hits[:1]
        for h in hits[1:3]:
            s = h.get("signals", {})
            if h["id"] in own or s.get("bm25", {}).get("score", 0) >= S.BM25_MIN:
                out.append(h)
        return out[:2]

    @staticmethod
    def _clean_extraction(x):
        """The model's JSON is untrusted: accept any shape, keep only short strings."""
        def to_str(v):
            if isinstance(v, str):
                return v
            if isinstance(v, dict):
                return " ".join(to_str(i) for i in v.values())
            if isinstance(v, (list, tuple)):
                return " ".join(to_str(i) for i in v)
            return "" if v is None else str(v)
        if not isinstance(x, dict):
            x = {}
        sym = x.get("symptoms", [])
        sym = sym if isinstance(sym, list) else [sym]
        return {"symptoms": [to_str(v)[:80] for v in sym if to_str(v).strip()][:10],
                "site": to_str(x.get("site", ""))[:80], "duration": to_str(x.get("duration", ""))[:40]}

    def _finish(self, resp, t0):
        resp["disclaimer"] = S.DISCLAIMER
        resp["latency_s"] = round(time.time() - t0, 2)
        return resp

    def _pre_checks(self, text):
        rf = self.redflags.check(text)
        if rf:
            return {"status": "emergency", "answer": rf["message"], "red_flag": rf, "citations": []}
        sg = S.scope_guard(text)
        if sg:
            return {"status": "refused", "answer": sg["message"], "scope": sg["rule"], "citations": []}
        return None

    # ------------------------------------------------------------ M5: ask
    VERSE_REF = re.compile(r"(sutra\s*sthana|sutrasthana|sutra|su\.?)\s*(\d{1,3})\s*[.:/]\s*(\d{1,3})", re.I)
    GRAPH_Q = re.compile(r"\b(which|what) (herbs?|dravyas?|plants?)\b|\bherbs? (for|that|which)\b|"
                         r"कौन (सी|से) (जड़ी|औषधि)", re.I)
    DOSHA = {"vata": "Vata", "vayu": "Vata", "pitta": "Pitta", "kapha": "Kapha", "kafa": "Kapha",
             "वात": "Vata", "पित्त": "Pitta", "कफ": "Kapha"}

    def ask(self, question: str) -> dict:
        t0 = time.time()
        pre = self._pre_checks(question)
        if pre:
            return self._finish(pre, t0)
        ctx = S.patient_context(question)
        dravyas = self.graph.find_dravyas(question)

        # Explicit verse reference ("Charaka Sutrasthana 1.44"): answer only if it is in our index
        ref = self.VERSE_REF.search(question)
        if ref:
            vid = f"CS.Su.{int(ref.group(2))}.{int(ref.group(3))}"
            c = self._citation(vid)
            if not c:
                return self._finish({"status": "no_source", "gate": "verse_not_indexed",
                                     "answer": f"{vid} is not in AyurSaarthi's verified verse index, so I "
                                               "can't quote it.", "citations": []}, t0)
            return self._finish({"status": "answered", "mode": "verse_lookup", "answer": c["meaning"],
                                 "citations": [c], "warnings": []}, t0)

        # Graph questions ("which herbs pacify Pitta?") are answered from the table, not the model
        if self.GRAPH_Q.search(question) and not dravyas:
            dosha = next((v for k, v in self.DOSHA.items() if k in question.lower()), None)
            if dosha:
                names = self.graph.query("PACIFIES", dosha)
                cites = []
                for n in names[:8]:
                    did = self.graph.find_dravyas(n)
                    vids = self.graph.g.nodes[did[0]].get("verse_ids", []) if did else []
                    if vids and self._citation(vids[0]):
                        cites.append(self._citation(vids[0]))
                return self._finish({"status": "answered", "mode": "graph",
                                     "answer": f"Herbs in our reviewed table that pacify {dosha}: "
                                               + ", ".join(names) + ".",
                                     "citations": cites, "warnings": []}, t0)

        hits = self.retriever.search(question, k=3)
        if dravyas:  # put the herb's own verse first
            own = [v for d in dravyas for v in self.graph.g.nodes[d].get("verse_ids", [])]
            hits = sorted(hits, key=lambda h: 0 if h["id"] in own else 1)
            for v in own:
                if v not in [h["id"] for h in hits] and v in self.chunk_by_id:
                    hits.insert(0, dict(self.chunk_by_id[v]))
        ok, why = S.retrieval_gate(hits, dravyas, question)
        if not ok:
            g = self._glossary_lookup(question)
            if g:
                return self._finish({"status": "answered", "mode": "glossary",
                                     "answer": f"{g['term']}: {g['plain_en']}",
                                     "citations": [c for c in [self._citation(g["verse_id"])] if c],
                                     "warnings": [], "note": "Plain-language glossary entry (team-written)."}, t0)
            return self._finish({"status": "no_source", "answer": S.NO_SOURCE_MSG,
                                 "gate": why, "citations": []}, t0)

        top = hits[0]
        profiles = [self._profile_text(d) for d in dravyas[:2]]
        facts = "; ".join(f"{p['name']}: rasa {p['rasa']}, guna {p['guna']}, virya {p['virya']}, "
                          f"vipaka {p['vipaka']}, pacifies {p['pacifies']}" for p in profiles)
        raw, stats = self._explain(question, top, facts)
        allowed = {h["id"] for h in hits}
        answer, removed = S.verify_answer(raw, self.graph, dravyas, allowed)
        ok_g, ratio = S.grounded_enough(answer, top, facts, question) if _lang(question) == "en" else (True, None)
        if not ok_g:  # model drifted away from the passage -> show the reviewed meaning instead
            removed.append({"sentence": answer, "reason": f"not grounded in passage (overlap {ratio})"})
            answer = ""
        if not answer:  # everything failed verification -> use the reviewed meaning
            answer = top["meaning_en"]
        answer, policy = S.output_policy(answer)
        warnings = S.contraindication_warnings(self.graph, dravyas, ctx)
        return self._finish({"status": "answered", "mode": "grounded", "answer": answer,
                             "dravya_profiles": profiles,
                             "citations": [c for c in (self._citation(h["id"]) for h in self._cite_hits(hits, dravyas)) if c],
                             "warnings": warnings, "removed_by_verifier": removed,
                             "policy_flags": policy, "gate": why, "llm": stats}, t0)

    # ------------------------------------------------------------ M3: explain prescription
    def explain_prescription(self, text: str) -> dict:
        t0 = time.time()
        rf = self.redflags.check(text)
        if rf:
            return self._finish({"status": "emergency", "answer": rf["message"], "citations": []}, t0)
        sg = S.scope_guard(text)
        if sg and sg["rule"] in ("stop_medicine", "injection"):
            return self._finish({"status": "refused", "answer": sg["message"], "citations": []}, t0)
        ctx = S.patient_context(text)
        f = " " + phrase(text) + " "
        terms = []
        for g in self.glossary:
            names = [g["term"], g["devanagari"]] + [x for x in g["synonyms"].split(";") if x]
            if any(n and f" {phrase(n)} " in f for n in names):
                terms.append({"term": g["term"], "meaning": g["plain_en"],
                              "citation": self._citation(g["verse_id"]) if g["verse_id"] else None})
        herbs = []
        for did in self.graph.find_dravyas(text):
            p = self._profile_text(did)
            p["citation"] = self._citation(p["verse_ids"][0]) if p["verse_ids"] else None
            herbs.append(p)
        warnings = S.contraindication_warnings(self.graph, [h for h in self.graph.find_dravyas(text)], ctx)
        if not terms and not herbs:
            return self._finish({"status": "no_source", "answer":
                                 "I couldn't recognise any Ayurvedic terms or herbs in this prescription. "
                                 "Please check the spelling or ask your Vaidya.", "citations": []}, t0)
        summary = ("Here is what the terms in your prescription mean. Keep taking it exactly as your "
                   "Vaidya wrote it: same medicine, amount, timing and duration.")
        return self._finish({"status": "answered", "answer": summary, "terms": terms, "herbs": herbs,
                             "citations": [h["citation"] for h in herbs if h["citation"]],
                             "warnings": warnings}, t0)

    # ------------------------------------------------------------ M1: route
    def route(self, complaint: str) -> dict:
        t0 = time.time()
        rf = self.redflags.check(complaint)
        if rf:
            return self._finish({"status": "emergency", "answer": rf["message"], "citations": []}, t0)
        extracted = {}
        if self.use_llm:
            try:
                import json
                from llm.client import chat
                txt, _ = chat([{"role": "user", "content":
                                "Extract from this patient complaint. Return JSON with keys symptoms "
                                f"(list of short English phrases), site, duration. Complaint: {complaint}"}],
                              max_tokens=120, json_mode=True)
                extracted = json.loads(txt)
            except Exception:
                extracted = {}
        extracted = self._clean_extraction(extracted)
        sym_text = " ".join(extracted["symptoms"])
        words = " " + phrase(complaint + " " + sym_text) + " "
        toks = set(tokens(complaint + " " + sym_text))
        scored = []
        for d in self.departments:
            kws = [k.strip() for k in d["complaint_keywords"].split(";") if k.strip()]
            score = sum(2 if f" {phrase(k)} " in words else
                        (1 if set(tokens(k)) and set(tokens(k)) <= toks else 0) for k in kws)
            if score:
                scored.append((score, d))
        if "Bala" in S.patient_context(complaint)["populations"]:
            scored = [(s + 10 if "Kaumarabhritya" in d["department"] else s, d) for s, d in scored]
            if not any("Kaumarabhritya" in d["department"] for _, d in scored):
                scored += [(10, d) for d in self.departments if "Kaumarabhritya" in d["department"]]
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return self._finish({"status": "no_match", "answer":
                                 "I couldn't match this to a department. A general physician "
                                 "(Kayachikitsa) is the right first step.", "extracted": extracted,
                                 "citations": []}, t0)
        top = [{"department": d["department"], "reason": d["reason_en"], "score": s}
               for s, d in scored[:2]]
        return self._finish({"status": "answered", "mode": "expert_map",
                             "answer": f"Suggested department: {top[0]['department']}. {top[0]['reason']}.",
                             "suggestions": top, "extracted": extracted, "citations": []}, t0)
