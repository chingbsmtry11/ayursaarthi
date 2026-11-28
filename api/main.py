"""AyurSaarthi REST API.

Run:  uvicorn api.main:app --host 127.0.0.1 --port 8000
Docs: http://127.0.0.1:8000/docs
"""
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agents.pipeline import AyurSaarthi

app = FastAPI(title="AyurSaarthi API",
              description="Source-grounded Ayurveda assistant built on AyurParam (BharatGen). "
                          "Educational use only; not a diagnosis or prescription.",
              version="0.2.0")
_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = AyurSaarthi(use_llm=os.getenv("USE_LLM", "1") == "1")
    return _engine


class Query(BaseModel):
    text: str = Field(..., min_length=2, max_length=1000, examples=["What is the virya of Amalaki?"])


@app.get("/health")
def health():
    e = engine()
    return {"status": "ok", "verses": len(e.retriever.chunks), "retrieval_mode": e.retriever.mode,
            "dravyas": sum(1 for _, d in e.graph.g.nodes(data=True) if d.get("type") == "Dravya")}


@app.post("/ask", summary="M5 Dravya Kosha and classical Q&A")
def ask(q: Query):
    return engine().ask(q.text)


@app.post("/explain", summary="M3 Explain a Vaidya's prescription")
def explain(q: Query):
    return engine().explain_prescription(q.text)


@app.post("/route", summary="M1 Suggest an Ayurvedic department")
def route(q: Query):
    return engine().route(q.text)


@app.get("/dravya/{name}", summary="Herb profile from the reviewed table")
def dravya(name: str):
    e = engine()
    ids = e.graph.find_dravyas(name)
    if not ids:
        return {"status": "not_found"}
    p = e._profile_text(ids[0])
    p["citations"] = [c for c in (e._citation(v) for v in p["verse_ids"]) if c]
    return p
