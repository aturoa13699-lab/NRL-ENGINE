AGENT.md — Operating Guide for LLM Agents

Purpose: This file teaches a code/terminal agent how to work in this repository without breaking CI or production, and how to deliver clean, reviewable PRs that pass the gates.

⸻

1) Ground Truth & Scope
	•	Project: NRL results scraper + data pipeline (RLP primary; NRL.com optional).
	•	Competition scope: NRL Premiership (1998–2025), regular season + finals.
Exclude trials, State of Origin, All Stars, World Club Challenge, NRLW (for now).
	•	Primary sink: PostgreSQL 15 (Railway). Parquet exports to data/exports/.
	•	Python: 3.12 (tests) and 3.13 (lint/health jobs).
	•	URL canonical: https://www.rugbyleagueproject.org/seasons/nrl-<YEAR>/results.html (note /seasons/).
	•	Export function compatibility: Keep both nrlscraper.export.to_parquet and export_to_parquet callable (aliases OK).
main.py tries to_parquet then export_to_parquet.

⸻

2) Repository Map (key files)

.
├── main.py                        # Railway worker entrypoint (MODE=season|historical)
├── health.py                      # Optional always-on FastAPI health server
├── Procfile                       # Railway start commands
├── nrlscraper/
│   ├── scraper.py                 # Core RLP scraping
│   ├── normalize.py               # Team/venue normalization
│   ├── models.py                  # Pydantic v2 schemas
│   ├── db.py                      # psycopg3 engine + upsert
│   ├── export.py                  # Parquet export (expose to_parquet + export_to_parquet)
│   ├── season.py                  # python -m nrlscraper.season <year>
│   └── historical.py              # python -m nrlscraper.historical <start> <end>
├── tools/
│   ├── scraper_check.py           # Quick scrape probe
│   └── validate_aggregate.py      # Assertions (e.g., 2024 = 213 matches)
├── scripts/
│   └── bootstrap_db.sql           # DDL for Postgres
├── tests/
│   └── test_scraper.py            # pytest suite
├── docs/
│   ├── maintainers.md             # Branch protection & required checks
│   └── ops.md                     # Ops cheat sheet / Railway runbook
├── .github/workflows/
│   ├── ci.yml                     # Lint, tests, summaries, artifacts, Codecov
│   ├── release.yml                # Release Drafter, bundle, SQL attach
│   ├── semantic-pr.yml            # Conventional PR title enforcement
│   ├── codeql.yml                 # CodeQL scanning
│   ├── labeler.yml                # Auto-label PRs by path
│   └── sync-labels.yml            # Sync canonical labels
├── .pre-commit-config.yaml        # ruff, format, pyupgrade, mypy, whitespace
├── pyproject.toml                 # ruff, pytest, Commitizen config
├── requirements.txt               # runtime deps (httpx, tenacity, etc.)
├── requirements-dev.txt           # dev deps (pytest, ruff, mypy, commitizen…)
├── .codecov.yml                   # coverage settings
├── Makefile                       # local dev helpers
├── README.md                      # badges + Quick Links
└── .env.example                   # sample envs


⸻

3) Conventions & Quality Gates
	•	Commits: Conventional Commits (enforced on PR titles):
	•	feat: …, fix: …, chore: …, docs: …, refactor: …, perf: …, test: …
	•	Branch names: <type>/<scope>-<short-desc> (e.g., feat/rlp-parser-bump).
	•	Style: ruff (lint) + ruff-format. mypy runs (non-blocking in CI, but keep clean).
	•	Tests: pytest must pass. Use tools/validate_aggregate.py for season assertions.
	•	Secrets: Never hardcode. Use env or GitHub Secrets. Prefer read-only DB where possible.
	•	CI required checks on main: ci (+/or test job) and semantic-pr.

⸻

4) Agent Pre-Flight Checklist
	1.	Detect repo slug:

git remote get-url origin


	2.	Create a feature branch:

git checkout -b feat/<scope>-<desc>


	3.	Local setup:

python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
make lint && make test || true


	4.	Keep edits minimal and scoped. Maintain backward compatibility (e.g., export function aliases).
	5.	Run fast checks before committing:

ruff check . && ruff format --check && pytest -q



⸻

5) Safe Ops Defaults (for Agents)
	•	Never write to prod DB by default.
Use env gating; only set WRITE_DB=1 when explicitly asked and DATABASE_URL is provided.
	•	Network expectations: CI has network for scraping. Tests should avoid flaky live calls in unit scope; prefer integration tools in tools/.
	•	Idempotency: Any script/patch should be safe to re-run (no duplicate inserts; guards in DB upsert).

⸻

6) Local Run Recipes (Agent)
	•	Lint/format/test:

make lint && make format && make test


	•	Single season scrape (no DB writes):

python -m nrlscraper.season 2024
python tools/validate_aggregate.py --season 2024 --expected-total 213 --expected-regular 204


	•	Historical read-only run:

python -m nrlscraper.historical 1998 2025


	•	Railway worker locally (no writes):

MODE=season SEASON=2024 INCLUDE_FINALS=1 WRITE_DB=0 python main.py



⸻

7) Common Tasks — Action Recipes

A) Fix/extend RLP parsing
	1.	Edit nrlscraper/scraper.py (keep /seasons/ URL).
	2.	Update nrlscraper/models.py if schema fields change.
	3.	Ensure normalization coverage in normalize.py.
	4.	Add/adjust tests in tests/test_scraper.py.
	5.	Run:

ruff check . && pytest -q
python tools/validate_aggregate.py --season 2024 --expected-total 213 --expected-regular 204


	6.	Commit with fix: or feat:.

B) Add a new column to matches
	1.	Edit models & scraper extraction.
	2.	If DB persists it, alter DDL (add to scripts/bootstrap_db.sql) and ensure upsert handles new column.
	3.	Backfill logic must keep old rows valid (nullable or default).
	4.	Tests + tool assertions.

C) Expose export function safely
	•	Ensure both:

def to_parquet(...): ...
export_to_parquet = to_parquet  # alias


	•	main.py already tries both names.

D) Workflow tweaks
	•	Edit .github/workflows/ci.yml cautiously:
	•	Keep concurrency, schedules, artifact retention, Codecov upload, Job Summary links.
	•	Preserve the pre-commit.ci link step and optional RAILWAY_URL summary.

⸻

8) Git & PR Flow (Agent)
	1.	Stage & commit (small, logical increments):

git add -A
git commit -m "feat(parser): capture penalty counts from RLP results"


	2.	Push & open PR:

git push -u origin <branch>


	3.	PR Title must be Conventional (CI enforced).
PR body should summarize scope, risks, and checklist (below).

PR Checklist (copy into PR body):
	•	Conventional PR title
	•	CI green (lint/tests)
	•	tools/validate_aggregate.py passes (e.g., season 2024 = 213/204)
	•	Backward compatibility maintained (export alias)
	•	Docs updated (docs/ops.md or README badges/links if relevant)

Labels: auto-applied via paths; run “Sync Labels” if labels missing.

⸻

9) Releases
	•	Tag to release (Release Drafter generates notes, bundle attached):

git tag vX.Y.Z
git push origin vX.Y.Z



⸻

10) Secrets & Safety
	•	Never commit credentials or tokens.
	•	Use:
	•	GitHub Secrets/Variables (DATABASE_URL, RAILWAY_URL, CODECOV_TOKEN for private repos).
	•	Railway dashboard for runtime env vars.
	•	For Colab/EDA, prefer a read-only DB role.

⸻

11) Colab/Reports (optional)
	•	Notebooks under notebooks/; reports (HTML) under reports/.
	•	Convert and commit from Colab:

!jupyter nbconvert --to html --output-dir=reports --no-input notebooks/10_eda_baseline.ipynb
# then git add/commit/push (use PAT), preferably to a 'reports' branch


	•	Consider adding nbstripout to pre-commit if notebooks become noisy.

⸻

12) Agent Prompts (Templates)

A) Terminal Execution Prompt

Use when the agent can run shell commands.

You are a terminal assistant. Run EXACTLY these steps:

1) Create branch:
   git checkout -b feat/rlp-fix-url

2) Make changes:
   # edit nrlscraper/scraper.py to ensure /seasons/ path and improve parsing
   # keep export alias in nrlscraper/export.py: export_to_parquet = to_parquet

3) Install & test:
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   ruff check . && ruff format --check
   pytest -q
   python tools/validate_aggregate.py --season 2024 --expected-total 213 --expected-regular 204

4) Commit:
   git add -A
   git commit -m "fix(parser): correct RLP /seasons/ URL and parsing edge cases"

5) Push:
   git push -u origin feat/rlp-fix-url

B) File Edit Prompt

Use when the agent edits files directly without shell.

Task: Update RLP parser and keep export compatibility.
Constraints:
- Do not change CI schedules, concurrency, or Codecov configuration.
- Keep both to_parquet and export_to_parquet valid.

Files to touch:
- nrlscraper/scraper.py
- nrlscraper/export.py (ensure alias)
- tests/test_scraper.py (if behavior changes)

Acceptance:
- ruff check . passes
- pytest -q passes
- tools/validate_aggregate.py (2024) reports total=213, regular=204


⸻

13) Troubleshooting (Agent)
	•	Workflow YAML error (e.g., Python pasted into .github/workflows/*.yml):
	•	Replace with valid YAML; see ci.yml and examples in this repo.
	•	Import error export_to_parquet:
	•	Ensure nrlscraper/export.py exposes:

def to_parquet(...): ...
export_to_parquet = to_parquet


	•	Network flakiness: Re-run integration tools; keep unit tests isolated.

⸻

14) Quick Commands (Agent)

# Lint/format/test
ruff check . && ruff format --check && pytest -q

# Validate a season
python tools/validate_aggregate.py --season 2024 --expected-total 213 --expected-regular 204

# Run worker (no DB writes)
MODE=season SEASON=2024 WRITE_DB=0 python main.py

# Install pre-commit hooks locally (optional)
pip install -r requirements-dev.txt && pre-commit install


⸻

15) Do & Don’t (Agent)

Do
	•	Keep changes atomic and scoped.
	•	Follow Conventional Commits.
	•	Maintain backward-compatible APIs.
	•	Update tests and docs for visible changes.

Don’t
	•	Commit secrets.
	•	Disable CI checks or remove concurrency/retention settings.
	•	Break export compatibility or the 2024 match count checks.
	•	Write to production DB unless explicitly instructed with WRITE_DB=1 and a provided DATABASE_URL.

⸻

End of AGENT.md

## Codex PR Discipline (avoid conflicts)
Always:
1. `git fetch origin && git checkout main && git pull --ff-only origin main`
2. `git checkout -b "codex/<task-slug>"`
3. Make changes + commit.
4. Before push: `git fetch origin && git rebase origin/main || git merge --no-ff origin/main`
5. Push: `git push -u origin HEAD`
6. If rebasing: `git config --global rerere.enabled true && git config --global rerere.autoupdate true` (remembers conflict resolutions).
