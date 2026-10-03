# Ruko (backend)

Ruko is a decision-safety layer for Indian retail investors. It sits between
"I want to act" and "I acted": it shows what a decision means for the user's own
money, rules and exit plan, in their language, and routes them to the right help
if something has already gone wrong. It never gives investment advice.

Built for the SANGYAN Investor Resilience Hackathon (Track D, Financial Habits &
Behavioural Resilience).

> Status: under construction. See `BUILD_PLAN.md` for stages and `STATUS.md` for progress.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # on macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn ruko.main:app --reload
```

Then open http://127.0.0.1:8000/docs (interactive API docs) or
http://127.0.0.1:8000/health.

Configuration is read from environment variables prefixed with `RUKO_`, or from a
local `.env` file. Copy `.env.example` to `.env` and fill in keys. The service runs
without any keys: the LLM step falls back to deterministic lexicon extraction and
speech endpoints return a typed `SPEECH_UNAVAILABLE` error.

## Run with Docker

```bash
docker build -t ruko .
docker run --rm -p 8000:8000 --env-file .env ruko
```

## Test and lint

```bash
.venv/Scripts/python -m pytest          # main suite (offline, fake providers)
.venv/Scripts/python -m pytest -m live  # optional live-provider checks (needs keys)
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .
```

## Privacy

The server is stateless. It never stores or logs message text, audio, profiles or
results. Log lines are built from an allow-list of fields (request ID, route
template, status, timings, error and reason codes); a test proves bodies are not
logged.
