.PHONY: data model smoke
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
