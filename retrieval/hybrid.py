"""Hybrid retrieval: BM25 + dense (multilingual-e5-small) + graph boost, fused with RRF.

Dense search is optional: if sentence-transformers or the model is unavailable
the retriever runs BM25 + graph only and says so in `self.mode`.
"""
import json
import os
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from ingest.textnorm import tokens

ROOT = Path(__file__).resolve().parents[1]
DENSE_MODEL = os.getenv("DENSE_MODEL", "intfloat/multilingual-e5-small")
RRF_K = 60


class HybridRetriever:
    def __init__(self, chunks_path=ROOT / "data" / "processed" / "chunks.jsonl",
                 graph=None, use_dense=True):
        self.chunks = [json.loads(l) for l in open(chunks_path, encoding="utf-8") if l.strip()]
        self.ids = [c["id"] for c in self.chunks]
        self.bm25 = BM25Okapi([tokens(c["search_text"]) for c in self.chunks])
        self.graph = graph
        self.encoder, self.emb, self.mode = None, None, "bm25+graph"
        if use_dense and os.getenv("DISABLE_DENSE") != "1":
            try:
                from sentence_transformers import SentenceTransformer
                self.encoder = SentenceTransformer(DENSE_MODEL, device="cpu")
                texts = ["passage: " + c["search_text"] for c in self.chunks]
                self.emb = self.encoder.encode(texts, normalize_embeddings=True,
                                               batch_size=32, show_progress_bar=False)
                self.mode = "bm25+dense+graph"
            except Exception as e:  # model download blocked, no package, etc.
                print(f"[retrieval] dense disabled: {e.__class__.__name__}: {e}")

    def _bm25(self, q, k):
        s = self.bm25.get_scores(tokens(q))
        order = np.argsort(-s)[:k]
        return [(int(i), float(s[i])) for i in order if s[i] > 0]

    def _dense(self, q, k):
        if self.encoder is None:
            return []
        qv = self.encoder.encode(["query: " + q], normalize_embeddings=True)[0]
        s = self.emb @ qv
        order = np.argsort(-s)[:k]
        return [(int(i), float(s[i])) for i in order]

    def _graph(self, q):
        if self.graph is None:
            return []
        verse_ids = []
        for did in self.graph.find_dravyas(q):
            verse_ids += self.graph.g.nodes[did].get("verse_ids", [])
        return [(self.ids.index(v), 1.0) for v in verse_ids if v in self.ids]

    def search(self, query: str, k: int = 5, pool: int = 20) -> list[dict]:
        """Return top-k chunks with fused score and per-retriever ranks."""
        lists = {"bm25": self._bm25(query, pool), "dense": self._dense(query, pool),
                 "graph": self._graph(query)}
        fused, detail = {}, {}
        for name, lst in lists.items():
            for rank, (i, raw) in enumerate(lst):
                fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
                detail.setdefault(i, {})[name] = {"rank": rank + 1, "score": round(raw, 4)}
        top = sorted(fused, key=lambda i: -fused[i])[:k]
        out = []
        for i in top:
            c = dict(self.chunks[i])
            c.pop("search_text", None)
            c["score"] = round(fused[i], 5)
            c["signals"] = detail[i]
            out.append(c)
        return out

    def best_lexical_score(self, query: str) -> float:
        """Used later by the L3 retrieval gate (threshold tuned on the eval set)."""
        s = self.bm25.get_scores(tokens(query))
        return float(s.max()) if len(s) else 0.0
