PY ?= python3
.PHONY: install test data baseline train serve ui bench frontend-test demo report check
install: ; $(PY) -m pip install -r requirements.txt
test: ; $(PY) -m unittest discover -s tests -v
data: ; $(PY) scripts/make_data.py          # Phase 1
baseline: ; $(PY) scripts/run_baseline.py   # Phase 2
train: ; $(PY) scripts/train.py             # Phase 3
serve: ; uvicorn mulenet.api.app:app --reload   # Phase 4
ui: ; cd frontend && npm install && npm run dev   # dev server; backend: make serve
bench: ; $(PY) scripts/bench_latency.py
frontend-test: ; cd frontend && npm test
demo: ; $(PY) scripts/demo.py                # Phase 6: headless end-to-end demo (no FastAPI/npm needed)
report: ; $(PY) scripts/gen_report.py       # writes docs/EVALUATION.md
check: test frontend-test demo report
