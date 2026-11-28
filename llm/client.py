"""Thin client for AyurParam served by Ollama (OpenAI-compatible chat endpoint).

Env:
  OLLAMA_URL   default http://localhost:11434
  AYUR_MODEL   default hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M
"""
import json
import os
import time

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("AYUR_MODEL", "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M")


def chat(messages, max_tokens=250, temperature=0.15, json_mode=False, timeout=180, stop=None):
    """Return (text, stats). Low temperature as in the proposal (0.1-0.2).

    MOCK_LLM=1 returns a canned reply (for tests without a model)."""
    if os.getenv("MOCK_LLM") == "1":
        return _mock(messages, json_mode), {"seconds": 0, "output_tokens": 0, "tokens_per_sec": 0,
                                            "prompt_tokens": 0, "mock": True}
    body = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "24h",  # keep model in RAM between requests
        "options": {"temperature": temperature, "num_predict": max_tokens,
                    "num_ctx": 2048, "repeat_penalty": 1.1,
                    **({"stop": stop} if stop else {})},
    }
    if json_mode:
        body["format"] = "json"
    t0 = time.time()
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    secs = time.time() - t0
    n = d.get("eval_count", 0)
    stats = {"seconds": round(secs, 2), "output_tokens": n,
             "tokens_per_sec": round(n / max(d.get("eval_duration", 1) / 1e9, 1e-6), 2),
             "prompt_tokens": d.get("prompt_eval_count", 0)}
    return d["message"]["content"], stats


def chat_stream(messages, max_tokens=250, temperature=0.15):
    """Yield text pieces as they are generated (for the UI on Day 3)."""
    body = {"model": MODEL, "messages": messages, "stream": True, "keep_alive": "24h",
            "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": 2048}}
    with requests.post(f"{OLLAMA_URL}/api/chat", json=body, stream=True, timeout=300) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                d = json.loads(line)
                yield d.get("message", {}).get("content", "")
                if d.get("done"):
                    break


def _mock(messages, json_mode):
    """Deterministic stand-in: echoes the passage meaning, or empty JSON."""
    if json_mode:
        return json.dumps({"symptoms": [], "site": "", "duration": ""})
    content = messages[-1]["content"]
    for line in content.splitlines():
        if line.startswith("Meaning:"):
            return line[len("Meaning:"):].strip()
    return "MOCK"
