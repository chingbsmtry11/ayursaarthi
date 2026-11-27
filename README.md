# AyurSaarthi

A source-grounded Ayurvedic care-journey assistant built on **AyurParam** (BharatGen).
"Cite or abstain": every answer cites a verse from an expert-approved classical source, or the system declines to answer.

> Educational information from classical Ayurvedic texts. Not a diagnosis or prescription. In an emergency call 108 / 112.

## Status: Day 1 (data pipeline, knowledge graph, hybrid retrieval, model serving)

```
data/verses.csv       verse-level corpus (Dr. Manash fills; review_status gate)
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
```

## Licences
Code: Apache-2.0. AyurParam: CC-BY-4.0, © BharatGen (see MODEL_CARD.md). Sources: see SOURCES.md.
