.PHONY: data model smoke test api ui deploy status logs
PY=python
DRAFT?=--include-draft

data:            ## build chunks + knowledge graph from CSVs
	$(PY) -m ingest.ingest $(DRAFT)
	$(PY) -m kg.build_kg $(DRAFT)

model:           ## check AyurParam serving + speed
	$(PY) -m scripts.test_model

smoke: data      ## retrieval check (add LLM=1 to also generate answers)
	$(PY) -m scripts.smoke_test --batch $(if $(LLM),--llm,)

# For the final build use only approved rows:  make data DRAFT=

test: data       ## run all eval questions through the full pipeline (writes eval/day2_results.csv)
	$(PY) -m scripts.day2_test

api:             ## REST API on 127.0.0.1:8000 (docs at /docs)
	uvicorn api.main:app --host 127.0.0.1 --port 8000

ui:              ## web demo on 127.0.0.1:7860
	$(PY) -m app.ui

deploy:          ## Day 3: services + HTTPS at aayu.svasthaayu.in
	bash scripts/deploy.sh

status:          ## are all services running?
	systemctl --no-pager --lines=0 status ollama ayursaarthi-ui ayursaarthi-api caddy | grep -E "●|Active"

logs:            ## last lines of the web demo's log
	journalctl -u ayursaarthi-ui -n 40 --no-pager
