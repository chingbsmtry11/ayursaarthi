"""Check AyurParam is served correctly and measure speed on this VPS.

Usage: python -m scripts.test_model
Pass criteria: sensible Ayurveda answers (not gibberish / not repeating the prompt),
Hindi answer in Devanagari, JSON mode returns valid JSON, tokens/sec printed.
"""
import json

from llm.client import MODEL, chat

TESTS = [
    ("english", "What are the three doshas in Ayurveda? Answer in 3 short sentences.", False),
    ("hindi", "आयुर्वेद में त्रिदोष क्या हैं? तीन वाक्यों में उत्तर दें।", False),
    ("json", 'Extract symptoms from: "knee pain and stiffness for 3 months, worse in winter". '
             'Return JSON with keys symptoms (list), site, duration, season.', True),
]

print("model:", MODEL)
speeds = []
for name, q, js in TESTS:
    text, st = chat([{"role": "user", "content": q}], max_tokens=200, json_mode=js)
    print(f"\n--- {name} --- {st}\n{text.strip()}")
    speeds.append(st["tokens_per_sec"])
    if js:
        try:
            json.loads(text)
            print("JSON: valid")
        except Exception:
            print("JSON: INVALID - extraction tasks need a retry/repair step")
avg = sum(speeds) / len(speeds)
print(f"\nAverage speed: {avg:.1f} tokens/sec -> 250-token answer ~ {250 / max(avg, 0.1):.0f} s")
if avg < 5:
    print("SLOW: set max_tokens ~150, keep_alive model in RAM, consider a bigger VPS plan.")
