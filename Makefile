PYTHON ?= python3

.PHONY: install generate run eval degrade export test serve
install:
	$(PYTHON) -m pip install -r requirements.txt
generate:
	$(PYTHON) -m dayone.generate
run:
	$(PYTHON) -m dayone.pipeline --member SYN-007
eval:
	$(PYTHON) -m evaluation.run_eval
degrade:
	$(PYTHON) -m evaluation.degradation --output evaluation/degradation_results.json
export:
	$(PYTHON) export_site_data.py
test:
	$(PYTHON) -m pytest -q
serve:
	$(PYTHON) -m uvicorn api.server:app --host 127.0.0.1 --port 8000
