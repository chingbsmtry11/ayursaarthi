# Day 1 — Engineer checklist (model, data pipeline, retrieval)

Goal by tonight: on the VPS, `make smoke LLM=1` takes a question in English/Hindi/romanised Hindi,
finds the right verses, and AyurParam answers with `[verse_id]` citations.

## Block 1 — Server (09:00–11:00)
1. SSH in: `ssh root@<VPS_IP>`; create a user: `adduser ayur && usermod -aG sudo ayur && su - ayur`
2. Check resources: `free -h && nproc && df -h /` → need **≥ 8 GB RAM, ≥ 20 GB free disk**.
3. Create the GitHub repo `ayursaarthi` (Public, **Apache License 2.0** chosen in the "Add license" dropdown).
4. Unzip this starter, then:
   ```bash
   git clone https://github.com/<org>/ayursaarthi.git && cd ayursaarthi
   # copy starter files in, then
   git add . && git commit -m "Day 1: data pipeline, KG, hybrid retrieval, model client" && git push
   ```
5. CPU-only torch first (saves ~2 GB): `pip install torch --index-url https://download.pytorch.org/whl/cpu`
   then `bash scripts/setup_vps.sh` (installs Docker, Ollama, pulls AyurParam Q4_K_M ~1.7 GB, adds 4 GB swap, firewall).

## Block 2 — Model check (11:00–12:30)
```bash
source .venv/bin/activate
make model
```
Pass if: English + Hindi answers are sensible, JSON test is valid, speed printed.
- **Gibberish / prompt echoed / never stops** → chat template problem. Fix: run llama.cpp instead
  (`llama-server -m AyurParam-Q4_K_M.gguf --jinja -c 2048 --port 11434` won't match Ollama's API,
  so then switch `llm/client.py` to `/v1/chat/completions`). Tell the team before spending >1 h on this.
- **Speed < 5 tokens/sec** → keep `max_tokens` 150–200; note the number for the report.
- Record: tokens/sec, RAM used (`free -h` while generating). These go into the technical report.

## Block 3 — Data pipeline (12:30–15:30)
1. Read `data/verses.csv` and `data/dravya.csv` — the column layout is final; send both files to Dr. Manash today.
2. Rows marked `draft` are used only with `--include-draft` (development). The final demo uses `approved` only:
   `make data DRAFT=`.
3. As his rows arrive: `make data` → check WARN lines (missing fields, duplicate IDs) and send them back to him.
4. Add 10–20 rows yourself from his first batch if he sends text in Word/WhatsApp — keep `review_status=draft`
   until he marks them `approved`.

## Block 4 — Retrieval (15:30–18:00)
1. `make smoke` — check each question finds the right verse at rank 1.
   - Romanised Hindi ("giloy") and Devanagari ("गुडूची") must hit via the graph alias table — add missing
     names to the `synonyms` column, not to code.
2. Dense search: `pip install sentence-transformers` then rerun — mode should say `bm25+dense+graph`.
   If RAM is tight, set `DISABLE_DENSE=1` (BM25+graph is enough for 300 verses).
3. Write 20 quick test questions with the expected verse ID in `eval/dev_questions.csv`
   (`question,gold_verse_id`) — Day 3's evaluation script will use this file.

## Block 5 — Grounded answer (18:00–20:00)
1. `make smoke LLM=1` — AyurParam answers from the top 3 passages with `[verse_id]` tags.
2. Check: does it cite IDs that were in the passages? Does it reply `NO_SOURCE` for the France question?
   Note failures — Day 2's citation verifier (L5) will catch them, but tune the prompt now if it
   almost never cites.
3. Commit and push. Message the team: speed, what works, what Dr. Manash still owes.

## End-of-day checklist
- [ ] Repo public, Apache-2.0, README + MODEL_CARD + SOURCES pushed
- [ ] AyurParam running on the VPS; tokens/sec recorded
- [ ] `chunks.jsonl` + `kg.json` built from Dr. Manash's first batch
- [ ] Right verse at rank 1 for most dev questions (EN, HI, romanised)
- [ ] One grounded answer with a correct `[verse_id]` citation

## What Dr. Manash sends today (in priority order)
1. 30 dravyas in `dravya.csv` (start with the ones in common Dabur/classical formulations)
2. Their supporting verses in `verses.csv` — Sanskrit (Devanagari), his own English meaning, edition + page
3. Contraindication column filled (Garbhini, Bala, Vriddha, Stanya, Ritu) — needed for Day 2
4. Red-flag symptom list and complaint → department map (Day 2, `rules.yaml`)
