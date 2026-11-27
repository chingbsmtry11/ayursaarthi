"""Query helpers over kg.json (networkx MultiDiGraph)."""
import json
from pathlib import Path

import networkx as nx

from ingest.textnorm import phrase

ROOT = Path(__file__).resolve().parents[1]


class DravyaGraph:
    def __init__(self, path=ROOT / "data" / "processed" / "kg.json"):
        data = json.load(open(path, encoding="utf-8"))
        self.aliases = data["aliases"]
        self.g = nx.MultiDiGraph()
        for n in data["nodes"]:
            self.g.add_node(n["id"], **n)
        for e in data["edges"]:
            self.g.add_edge(e["src"], e["dst"], type=e["type"], verse_ids=e["verse_ids"])

    def find_dravyas(self, text: str) -> list[str]:
        """Return dravya IDs whose any name (any script/spelling) appears in text."""
        f = " " + phrase(text) + " "
        hits = []
        for alias, did in self.aliases.items():
            if alias and f" {alias} " in f and did not in hits:
                hits.append(did)
        return hits

    def profile(self, did: str) -> dict:
        node = dict(self.g.nodes[did])
        props = {}
        for _, dst, d in self.g.out_edges(did, data=True):
            props.setdefault(d["type"], []).append(self.g.nodes[dst]["name"])
        node["properties"] = props
        return node

    def query(self, edge_type: str, value: str) -> list[str]:
        """e.g. query('PACIFIES', 'Pitta') -> dravya names."""
        tid = next((n for n in self.g.nodes if n.endswith(":" + value)), None)
        if not tid:
            return []
        return [self.g.nodes[s]["name"] for s, _, d in self.g.in_edges(tid, data=True)
                if d["type"] == edge_type]

    def contraindications(self, did: str) -> list[str]:
        return self.profile(did)["properties"].get("CONTRAINDICATED_IN", [])
