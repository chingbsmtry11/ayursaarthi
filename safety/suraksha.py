"""Suraksha safety layer: six deterministic checks around AyurParam.

L1 red-flag triage      - before everything (emergencies never reach the model)
L2 scope guard          - dose / prescribe / stop-medicine / prompt-injection requests
L3 retrieval gate       - abstain if no strong classical source was retrieved
L4 contraindications    - patient context x dravya rules from the knowledge graph
L5 fact & citation check- drop model sentences that contradict the dravya table or invent citations
L6 output policy        - no dose numbers, no cure/guarantee words, disclaimer always present

None of these use the language model, so the model cannot talk its way past them.
"""
import csv
import os
import re
from pathlib import Path

from ingest.textnorm import phrase

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = ("AyurSaarthi provides educational information from classical Ayurvedic texts. "
              "It does not diagnose, prescribe or replace a consultation with a qualified "
              "Ayurvedic doctor. In an emergency, call 108 / 112.")
CONSULT = "Please consult your Vaidya (Svasthaayu consultation: https://svasthaayu.in)."

# --------------------------------------------------------------------- L1
EMERGENCY_MSG = {
    "default": "This may be an emergency. Please call 108 or 112, or go to the nearest hospital now. "
               "Do not wait for Ayurvedic treatment.",
    "mental_health": "You don't have to face this alone. Please call Tele-MANAS 14416 (free, 24x7) "
                     "or 112 right now, or talk to someone you trust nearby.",
    "pregnancy": "Bleeding or severe pain in pregnancy needs urgent care. Please call 108 or go to "
                 "the nearest hospital now.",
    "paediatric": "A baby or child with these signs needs a doctor urgently. Please go to the "
                  "nearest hospital or call 108 now.",
    "poisoning": "Possible poisoning: call 108 / 112 now and take the container with you to hospital.",
}


class RedFlags:
    def __init__(self, path=ROOT / "data" / "red_flags.csv"):
        self.terms = []  # (folded term, category, original)
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = (r.get("term") or "").strip()
                if t:  # safety rules are used even in draft: err on the side of caution
                    self.terms.append((phrase(t), r["category"].strip(), t))

    COMBOS = [  # (category, pattern A, pattern B): both must appear
        ("pregnancy", r"pregnan|garbh|गर्भ", r"bleed|blood|खून|रक्त|spotting|severe pain|तेज दर्द"),
        ("paediatric", r"\b(baby|infant|newborn|child|toddler)\b|बच्च|शिशु",
         r"high fever|तेज बुखार|not feeding|not drinking milk|दूध नहीं|very drowsy|सुस्त|fits|seizure|"
         r"दौरा|breathing fast|सांस"),
        ("cardiac", r"chest|सीने|छाती", r"pain|pressure|tight|दर्द|जकड़"),
        ("mental_health", r"suicid|end my life|kill myself|मर जाना|आत्महत्या|जीना नहीं", r"."),
    ]

    def check(self, text: str):
        t = text.lower()
        for cat, a, b in self.COMBOS:
            if re.search(a, t) and re.search(b, t):
                return {"category": cat, "matched": "combination rule",
                        "message": EMERGENCY_MSG.get(cat, EMERGENCY_MSG["default"])}
        f = " " + phrase(text) + " "
        for term, cat, orig in self.terms:
            if term and f" {term} " in f:
                return {"category": cat, "matched": orig,
                        "message": EMERGENCY_MSG.get(cat, EMERGENCY_MSG["default"])}
        return None


# --------------------------------------------------------------------- L2
SCOPE_RULES = [
    ("dose", r"\b(how much|how many (tablets?|times|spoons?|grams?|capsules?|drops)|dose|dosage|quantity|mg|grams?|spoons?|tablets? a day|"
             r"kitn[aie]|matra|khurak|kitni goli)\b|कितना|कितनी|मात्रा|खुराक"),
    ("stop_medicine", r"\b(stop|quit|leave|replace|instead of|substitute)\b.{0,40}\b(medicine|tablet|"
                      r"drug|insulin|bp|allopath|dawai|dava)\b|\b(dawai|dava)\b.{0,20}\b(band|chhod)|"
                      r"दवा.{0,15}(बंद|छोड़)"),
    ("diagnose", r"\b(do i have|diagnose|what disease do i|is it cancer|which disease)\b|"
                 r"क्या मुझे .{0,20} है"),
    ("prescribe", r"\b(prescribe|which medicine should i take|give me (a )?medicine|best medicine for)\b|"
                  r"कौन सी दवा"),
    ("cure_claim", r"\b(which|what|quote|show).{0,20}(verse|shloka|sloka|reference).{0,80}\b(cures?|heals?|"
                   r"treats?)\b|\b(cancer|tumou?r|hiv|aids)\b|कैंसर|\bcur(e|ed|able)\b.{0,40}\bpermanent|"
                   r"\bpermanent(ly)?\b.{0,30}\bcur(e|ed)|\b(cure|cured) (completely|forever)|"
                   r"जड़ से (खत्म|ठीक)|हमेशा के लिए ठीक"),
    ("injection", r"(ignore|forget|disregard|override).{0,30}(rules|instructions|previous|system)|"
                  r"you are now|jailbreak|developer mode|pretend to be"),
]
SCOPE_MSG = {
    "dose": "I can't suggest a dose. The right amount depends on your age, strength, digestion and "
            "condition, so only your Vaidya can decide it. " + CONSULT,
    "stop_medicine": "Please don't stop or change any medicine on your own. Talk to the doctor who "
                     "prescribed it before making any change. " + CONSULT,
    "diagnose": "I can't diagnose conditions. A Vaidya needs to examine you for that. " + CONSULT,
    "prescribe": "I can't prescribe medicines, but I can explain classical texts and a prescription "
                 "your Vaidya has given you. " + CONSULT,
    "cure_claim": "I can't confirm a cure claim. Classical texts describe properties and uses of "
                  "herbs, not guaranteed or permanent cures. Long-term and serious conditions need "
                  "treatment guided by a qualified doctor. " + CONSULT,
    "injection": "I can only answer from verified classical sources and within my safety rules.",
}


def scope_guard(text: str):
    t = text.lower()
    for name, pat in SCOPE_RULES:
        if re.search(pat, t):
            return {"rule": name, "message": SCOPE_MSG[name]}
    return None


# --------------------------------------------------------------------- L3
BM25_MIN = float(os.getenv("GATE_BM25_MIN", "1.0"))
DENSE_MIN = float(os.getenv("GATE_DENSE_MIN", "0.86"))


def _overlap(question, chunk):
    from ingest.textnorm import tokens
    q = {t for t in tokens(question) if len(t) > 3}
    c = set(tokens(" ".join([chunk.get("meaning_en", ""), chunk.get("iast", ""),
                             " ".join(chunk.get("topics", []))])))
    return len(q & c)


def retrieval_gate(hits, dravyas_found, question=""):
    """Pass only if the evidence is strong. Thresholds are tuned on eval/ (see report).
    Meaning-based (dense) similarity alone is never enough: the passage must also share
    at least one content word with the question."""
    if dravyas_found:
        return True, "graph"
    if not hits:
        return False, "no_hits"
    top = hits[0]
    s = top.get("signals", {})
    if s.get("bm25", {}).get("score", 0) >= BM25_MIN and _overlap(question, top) >= 1:
        return True, "bm25"
    if s.get("dense", {}).get("score", 0) >= DENSE_MIN and _overlap(question, top) >= 1:
        return True, "dense"
    return False, "weak"


def grounded_enough(answer, passage, facts, question, min_ratio=0.5):
    """NLI-lite: most content words of the model's answer must come from the passage,
    the dravya facts or the question. Otherwise the model is answering from memory."""
    from ingest.textnorm import tokens
    a = [t for t in tokens(answer) if len(t) > 3]
    if not a:
        return True, 1.0
    src = set(tokens(" ".join([passage.get("meaning_en", ""), passage.get("iast", ""),
                               " ".join(passage.get("topics", [])), facts, question])))
    ratio = sum(1 for t in a if t in src) / len(a)
    return ratio >= min_ratio, round(ratio, 2)


NO_SOURCE_MSG = ("No verified classical source was found for this question, so I won't answer it. "
                 "Please ask your Vaidya.")

# --------------------------------------------------------------------- L4
CONTEXT_PATTERNS = {
    "Garbhini": r"\bpregnan\w*|\bexpecting\b|garbh|गर्भ|pregnent",
    "Stanya": r"breast.?feed\w*|lactat\w*|nursing (mother|my baby)|stanpan|स्तनपान",
    "Bala": r"\b(child|kid|baby|infant|toddler|son|daughter|bachch?[aeiā]|shishu)\b|बच्च|शिशु|"
            r"\b([1-9]|1[01])\s*(year|yr|month|saal|mahine)s?\s*old\b",
    "Vriddha": r"\b(elderly|old age|senior|grand(father|mother)|[7-9]\d\s*(years|yrs) old)\b|बुजुर्ग",
}
DRUG_PATTERNS = {
    "anticoagulant": r"blood thinner|warfarin|aspirin|clopidogrel|anticoagul",
    "antidiabetic": r"diabet\w* (medicine|tablet)|metformin|insulin|glimepiride|sugar (tablet|medicine)",
    "antihypertensive": r"\bbp (medicine|tablet)|blood pressure (medicine|tablet)|amlodipine|telmisartan",
    "sedative": r"sleeping (pill|tablet)|sedative|alprazolam|clonazepam",
    "thyroid": r"thyroid|thyroxine|eltroxin",
}
DRUG_KEYWORDS = {"anticoagulant": "anticoagulant", "antidiabetic": "antidiabetic",
                 "antihypertensive": "blood-pressure", "sedative": "sedative", "thyroid": "thyroid"}
POP_LABEL = {"Garbhini": "pregnancy", "Stanya": "breastfeeding", "Bala": "children",
             "Vriddha": "elderly people"}


def patient_context(text: str) -> dict:
    t = text.lower()
    return {"populations": [p for p, pat in CONTEXT_PATTERNS.items() if re.search(pat, t)],
            "drugs": [d for d, pat in DRUG_PATTERNS.items() if re.search(pat, t)]}


def contraindication_warnings(graph, dravya_ids, ctx) -> list:
    """Hard warnings from the knowledge graph; never generated by the model."""
    out = []
    for did in dravya_ids:
        p = graph.profile(did)
        name = p["name"]
        contra = p["properties"].get("CONTRAINDICATED_IN", [])
        for pop in ctx["populations"]:
            if pop in contra:
                out.append({"level": "stop", "dravya": name,
                            "text": f"{name} is listed as unsuitable in {POP_LABEL[pop]}. "
                                    f"Do not take it without your Vaidya's advice."})
        caution = (p.get("caution_notes") or "").lower()
        for d in ctx["drugs"]:
            if DRUG_KEYWORDS[d] in caution:
                out.append({"level": "caution", "dravya": name,
                            "text": f"{name}: {p['caution_notes']}. Tell your doctor about all "
                                    f"medicines you take."})
        for pop in ctx["populations"]:
            if pop not in contra:
                out.append({"level": "caution", "dravya": name,
                            "text": f"For {POP_LABEL[pop]}, take {name} only if your Vaidya advises it."})
        if caution and not ctx["drugs"] and contra and not ctx["populations"]:
            pops = ", ".join(POP_LABEL.get(c, c) for c in contra)
            out.append({"level": "info", "dravya": name,
                        "text": f"{name} is classically avoided in: {pops}."})
    return out


# --------------------------------------------------------------------- L5
VIRYA_WORDS = {"Ushna": r"\b(ushna|hot|heating|warm(ing)? in potency)\b|उष्ण|गर्म",
               "Sheeta": r"\b(sheeta|shita|cold|cooling)\b|शीत|ठंड"}
CITE_PAT = re.compile(r"\[[^\]]{2,40}\]")
FAKE_CITE = re.compile(r"\b(CS|SS|AH|BPN)\.[A-Za-z]+\.[\d.\-]+|samhita\s+\w+\s+\d+[.:]\d+", re.I)


def verify_answer(text: str, graph, dravya_ids, allowed_ids) -> tuple:
    """Remove sentences that cite unknown verses or contradict the dravya table."""
    removed = []
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    keep = []
    viryas = {}
    for did in dravya_ids:
        v = graph.profile(did)["properties"].get("HAS_VIRYA", [])
        if v:
            viryas[graph.g.nodes[did]["name"]] = v[0]
    for s in sentences:
        bad = None
        for c in CITE_PAT.findall(s) + FAKE_CITE.findall(s):
            cid = c.strip("[]")
            if cid not in allowed_ids:
                bad = f"unknown citation {c}"
        if not bad and len(viryas) == 1:
            true_v = next(iter(viryas.values()))
            if true_v in VIRYA_WORDS:
                other = "Sheeta" if true_v == "Ushna" else "Ushna"
                if re.search(VIRYA_WORDS[other], s, re.I) and not re.search(VIRYA_WORDS[true_v], s, re.I):
                    bad = f"contradicts the dravya table (virya is {true_v})"
        if bad:
            removed.append({"sentence": s, "reason": bad})
        elif s:
            keep.append(CITE_PAT.sub("", s).strip())
    return " ".join(keep).strip(), removed


# --------------------------------------------------------------------- L6
DOSE_PAT = re.compile(r"\b\d+(\.\d+)?\s*(mg|g|gm|grams?|ml|tsp|teaspoons?|tablespoons?|spoons?|"
                      r"tablets?|capsules?|times a day|drops)\b|\d+\s*(ग्राम|चम्मच|गोली)", re.I)
CURE_PAT = re.compile(r"\b(can be |be |is |are )?(cur(e|es|ed|ing|able)|permanent(ly)?|guarantee[ds]?|"
                      r"100\s*%|miracle|completely heal(s|ed)?|root out|eliminate[ds]? completely)\b|"
                      r"जड़ से|इलाज की गारंटी|पूरी तरह ठीक", re.I)
CURE_SENTENCE_MSG = ("Classical texts describe how herbs and treatments may help manage a condition; "
                     "they do not promise a permanent cure. A qualified doctor should guide treatment.")


def output_policy(text: str) -> tuple:
    flags = []
    if DOSE_PAT.search(text):
        text = DOSE_PAT.sub("[amount as advised by your Vaidya]", text)
        flags.append("dose_removed")
    if CURE_PAT.search(text):  # drop the whole sentence: rewording a cure claim is not enough
        sents = re.split(r"(?<=[.!?।])\s+", text)
        kept = [x for x in sents if not CURE_PAT.search(x)]
        text = " ".join(kept + [CURE_SENTENCE_MSG])
        flags.append("cure_claim_removed")
    return text, flags
