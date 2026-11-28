"""AyurSaarthi web demo (Gradio). Three tabs: Dravya Kosha / Ask, Prescription Explainer,
Department Finder. Every answer shows its classical citation, warnings and the disclaimer.

Run: python -m app.ui      (serves on 127.0.0.1:7860; put Caddy in front for HTTPS)
"""
import os

import gradio as gr

from agents.pipeline import AyurSaarthi
from safety.suraksha import DISCLAIMER

E = AyurSaarthi(use_llm=os.getenv("USE_LLM", "1") == "1")
STATUS = {"answered": "", "emergency": "🚨 **Emergency**", "refused": "⚠️ **Outside my scope**",
          "no_source": "📚 **No verified source**", "no_match": "ℹ️"}


def fmt_citations(cites):
    if not cites:
        return ""
    out = ["\n\n---\n### 📜 Classical sources"]
    for c in cites:
        tag = " *(draft, pending expert review)*" if c.get("review_status") != "approved" else ""
        out.append(f"<details><summary><b>{c['verse_id']}</b>: {c['source']}, {c['section']} "
                   f"{c['verse']}{tag}</summary>\n\n**{c['sanskrit']}**\n\n*{c['iast']}*\n\n"
                   f"**Meaning:** {c['meaning']}\n\n<small>Edition: {c['edition']}</small></details>")
    return "\n".join(out)


def fmt_warnings(ws):
    if not ws:
        return ""
    icon = {"stop": "⛔", "caution": "⚠️", "info": "ℹ️"}
    return "\n\n" + "\n".join(f"> {icon.get(w['level'], '⚠️')} {w['text']}" for w in ws)


def fmt_profile(profiles):
    out = []
    for p in profiles or []:
        out.append(f"\n\n**{p['name']}** ({p['devanagari']}, {p['hindi']}, *{p['botanical']}*)\n\n"
                   f"| Rasa | Guna | Virya | Vipaka | Pacifies |\n|---|---|---|---|---|\n"
                   f"| {p['rasa']} | {p['guna']} | {p['virya']} | {p['vipaka']} | {p['pacifies']} |")
    return "".join(out)


def ui_ask(q):
    r = E.ask(q)
    md = f"{STATUS.get(r['status'], '')} {r['answer']}"
    md += fmt_profile(r.get("dravya_profiles")) + fmt_warnings(r.get("warnings")) + fmt_citations(r.get("citations"))
    return md + f"\n\n<small>⏱ {r.get('latency_s')} s · {DISCLAIMER}</small>"


def ui_explain(text):
    r = E.explain_prescription(text)
    md = f"{STATUS.get(r['status'], '')} {r['answer']}"
    for t in r.get("terms", []):
        md += f"\n- **{t['term']}**: {t['meaning']}"
    md += fmt_profile(r.get("herbs")) + fmt_warnings(r.get("warnings")) + fmt_citations(r.get("citations"))
    return md + f"\n\n<small>{DISCLAIMER}</small>"


def ui_route(text):
    r = E.route(text)
    md = f"{STATUS.get(r['status'], '')} {r['answer']}"
    for s in r.get("suggestions", [])[1:]:
        md += f"\n\nAlso consider: **{s['department']}**: {s['reason']}"
    return md + f"\n\n<small>The department is chosen from an expert-reviewed map, not by AI. {DISCLAIMER}</small>"


with gr.Blocks(title="AyurSaarthi") as demo:
    gr.Markdown("# 🌿 AyurSaarthi\nSource-grounded Ayurveda assistant built on **AyurParam** (BharatGen). "
                "Every answer cites a classical verse, or says it has none.")
    with gr.Tab("Dravya Kosha / Ask"):
        q = gr.Textbox(label="Ask about a herb or concept (English / हिन्दी / Hinglish)",
                       placeholder="What is the virya of Amalaki?  ·  गिलोय के गुण क्या हैं  ·  neem ke fayde")
        gr.Examples(["What is the virya of Amalaki?", "गिलोय के गुण क्या हैं", "Which herbs pacify Pitta?",
                     "What are the qualities of Vata?", "I am pregnant, can I take Haritaki?"], q)
        out = gr.Markdown()
        q.submit(ui_ask, q, out)
        gr.Button("Ask", variant="primary").click(ui_ask, q, out)
    with gr.Tab("Prescription Explainer"):
        p = gr.Textbox(lines=4, label="Paste your Vaidya's prescription",
                       placeholder="Ashwagandha churna with warm water at bedtime; Triphala after food")
        pout = gr.Markdown()
        gr.Button("Explain", variant="primary").click(ui_explain, p, pout)
    with gr.Tab("Department Finder"):
        c = gr.Textbox(label="Describe the problem", placeholder="Knee pain and stiffness for 3 months")
        cout = gr.Markdown()
        gr.Button("Find department", variant="primary").click(ui_route, c, cout)
    gr.Markdown(f"<small>{DISCLAIMER}<br>AyurParam © BharatGen, CC-BY-4.0. Code Apache-2.0.</small>")

if __name__ == "__main__":
    demo.launch(server_name=os.getenv("HOST", "127.0.0.1"), server_port=int(os.getenv("PORT", "7860")),
                theme=gr.themes.Soft())
