# Model card: AyurParam inside AyurSaarthi

- **Model:** AyurParam-2.9B by BharatGen (`bharatgenai/AyurParam`), fine-tuned from Param-1-2.9B-Instruct.
- **Licence:** CC-BY-4.0. © BharatGen. Used with attribution; no changes to the base weights.
- **Build served in the demo:** 4-bit GGUF (Q4_K_M) community conversion `A-Aryam/AyurParam-GGUF`, served on CPU through Ollama.
- **Paper:** Nauman et al., "AyurParam: A State-of-the-Art Bilingual Language Model for Ayurveda", arXiv:2511.02374.
- **Role in AyurSaarthi:** query rewriting, symptom/term extraction (JSON) and grounded explanation of retrieved, expert-approved passages. The model never makes routing, safety or clinical decisions.
- **Settings:** temperature 0.1–0.2, context 2,048 tokens, max 250 output tokens.
- **Known limits:** about 40% on BhashaBench-Ayur (per the paper); 4-bit quantisation may reduce quality slightly. Every output passes the Suraksha safety layer and citation verifier.
