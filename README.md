# AyurSaarthi

**Live demo:** https://aayu.svasthaayu.in · **API docs:** https://aayu.svasthaayu.in/api/docs

A source-grounded Ayurvedic care-journey assistant built on **AyurParam** (BharatGen).
"Cite or abstain": every answer cites a verse from an expert-approved classical source, or the system declines to answer.

> Educational information from classical Ayurvedic texts. Not a diagnosis or prescription. In an emergency call 108 / 112.

## Status: Day 2 (safety layer, grounded answers, 3 modules, API, web demo)

How an answer is made ("AyurParam explains; it never decides"):
1. **L1 red-flag triage** - emergencies get 108/112 guidance and never reach the model
2. **L2 scope guard** - dose, prescribing, stopping medicines, prompt injection -> polite refusal
3. **Hybrid retrieval** (BM25 + multilingual-e5 + knowledge graph) over verse-level chunks
4. **L3 retrieval gate** - weak evidence -> "no verified source" (the model never decides this)
5. **AyurParam** explains the top passage in 2-3 sentences (stop sequences, 160 tokens)
6. **L5 verifier** - drops sentences with invented citations or that contradict the dravya table
7. **L4 contraindications** from the graph (pregnancy, children, breastfeeding, elderly, drug-herb)
8. **L6 output policy** - no dose numbers, no cure claims, disclaimer on every answer
9. Citations are attached by code from the retrieved verses, never written by the model.

Modules: **M5** Dravya Kosha / Q&A (`/ask`), **M3** prescription explainer (`/explain`),
**M1** department finder (`/route`, from the expert map).

```
data/verses.csv       43 verse-level chunks (Bhavaprakasha Nighantu, Charaka Su.1)
data/red_flags.csv    emergency terms (en/hi; as to add)
data/departments.csv  complaint -> department map (expert-reviewed)
data/glossary.csv     prescription terms (anupana, aushadha kala, dosage forms)
data/eval.csv         50 test questions incl. safety and adversarial cases
safety/               Suraksha layer L1-L6
agents/               pipeline: ask (M5), explain_prescription (M3), route (M1)
api/  app/            FastAPI service and Gradio web demo
data/dravya.csv       herb records -> knowledge graph
ingest/               normalisation (Devanagari/IAST/romanised) + chunking
kg/                   graph builder (kg.json) + networkx query helpers
retrieval/            BM25 + multilingual-e5-small + graph, fused with RRF
llm/                  AyurParam client (Ollama)
scripts/              VPS setup, model test, smoke test
```

## Quick start
```bash
bash scripts/setup_vps.sh        # once, on the server
source .venv/bin/activate
make model                       # AyurParam works? how fast?
make smoke                       # build data + test retrieval
make smoke LLM=1                 # + grounded answers from AyurParam
make test                        # all eval questions -> eval/day2_results.csv
make ui                          # web demo on :7860
make api                         # REST API on :8000
```

## Licences
Code: Apache-2.0. AyurParam: CC-BY-4.0, © BharatGen (see MODEL_CARD.md). Sources: see SOURCES.md.
