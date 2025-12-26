.PHONY: venv install lint format test season historical validate clean
PY?=python
PIP?=pip
SEASON?=2024
START?=1998
END?=2025
FINALS?=1
venv: ; $(PY) -m venv .venv
install: ; . .venv/bin/activate && $(PIP) install -U pip && $(PIP) install -r requirements-dev.txt
lint: ; . .venv/bin/activate && ruff check .
format: ; . .venv/bin/activate && ruff format .
test: ; . .venv/bin/activate && pytest -q
season: ; . .venv/bin/activate && $(PY) -m nrlscraper.season $(SEASON) $(if $(filter 0,$(FINALS)),--no-finals,)
historical: ; . .venv/bin/activate && $(PY) -m nrlscraper.historical $(START) $(END)
validate: ; . .venv/bin/activate && $(PY) tools/validate_aggregate.py --season $(SEASON) --expected-total 213 --expected-regular 204
clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache htmlcov .coverage
	find . -name "*.pyc" -delete
