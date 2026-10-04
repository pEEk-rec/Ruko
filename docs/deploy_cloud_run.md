# Deploying to Google Cloud Run (prepared, NOT done)

Nothing here has been run. Deploying needs a Google Cloud project with billing, your `gcloud`
login, and your explicit go (CLAUDE.md section 4.2). The image is built from the repository's
`Dockerfile` (it builds the web app, then the backend serves it), so there is one service and no
CORS to configure.

## What it costs

Cloud Run bills only while a request is being handled (scale to zero), with a monthly free tier.
Building the image uses Cloud Build and Artifact Registry (small free tier, then pennies per build).
Secret Manager has a small free tier. Calls to Sarvam (and Gemini, if you add a key) are billed by
those providers, not by Google Cloud. For a demo, expect rupees, not thousands, but check the
current pricing pages before you start and set a budget alert (step 1).

## Before you deploy

- [ ] `.venv/Scripts/python -m pytest -o addopts="" -m "not live"`, `ruff check .`, `ruff format --check .` pass.
- [ ] `cd frontend && npm test && npm run typecheck && npm run build && npm run check:size` pass.
- [ ] `.venv/Scripts/python scripts/smoke_test.py` and `... --prod` pass locally.
- [ ] You decided what a production demo shows (see "Facts in production" below).
- [ ] Keys live only in Secret Manager. Never put a key in a command line, the repo or `.env.example`.

## Steps (replace `PROJECT_ID`; region `asia-south1` is Mumbai)

```bash
# 0. One-time: log in and pick the project (the project must have billing enabled)
gcloud auth login
gcloud config set project PROJECT_ID
gcloud config set run/region asia-south1

# 1. Optional but recommended: a budget alert so a surprise cannot grow
#    (Console: Billing -> Budgets & alerts -> Create budget). There is no cost to create one.

# 2. Enable the services the deploy uses
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

# 3. Store the keys as secrets (paste the key when prompted; it is not echoed into history)
read -rs SARVAM_KEY && printf %s "$SARVAM_KEY" | gcloud secrets create ruko-sarvam-key --data-file=- ; unset SARVAM_KEY
# Optional, only if you have a paid Gemini key (the free tier returns 429; the lexicon fallback covers it):
# read -rs GEMINI_KEY && printf %s "$GEMINI_KEY" | gcloud secrets create ruko-gemini-key --data-file=- ; unset GEMINI_KEY

# 4. Let the service's identity read the secrets
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding ruko-sarvam-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# 5. Build and deploy from the repository root (uses ./Dockerfile and ./.gcloudignore)
gcloud run deploy ruko \
  --source . \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi --cpu 1 \
  --min-instances 0 --max-instances 1 \
  --concurrency 40 --timeout 60 \
  --set-env-vars "RUKO_ENVIRONMENT=prod,RUKO_SPEECH_PROVIDERS=sarvam" \
  --set-secrets "RUKO_SARVAM_API_KEY=ruko-sarvam-key:latest"
# With a Gemini key add: --set-env-vars "...,RUKO_LLM_PROVIDER=auto" and
#   --set-secrets "RUKO_SARVAM_API_KEY=ruko-sarvam-key:latest,RUKO_GEMINI_API_KEY=ruko-gemini-key:latest"

# 6. Smoke test the live URL (the command prints it; or: gcloud run services describe ruko --format='value(status.url)')
.venv/Scripts/python scripts/smoke_test.py --url https://ruko-XXXX-el.a.run.app --prod
```

Notes on the flags:

- `--max-instances 1` keeps the in-memory rate limiter meaningful (it is per process; open question 19).
  Raise it only after moving the limiter to a shared store.
- `--allow-unauthenticated` is what a public demo needs. The API takes no user accounts and stores
  nothing; the rate limit (60 requests a minute per client) and the body size cap are on.
- `PORT` is set by Cloud Run; the image reads it. `--port 8080` tells Cloud Run which port to probe.
- The first request after idle takes a few seconds (cold start); keep one warm before a demo with
  `--min-instances 1` (this costs money while it idles; set it back to 0 afterwards).

## Facts in production

`RUKO_ENVIRONMENT=prod` hides every fact whose `verified_by_human` is `false` (CLAUDE.md section 3,
open question 14). The group statistics, recovery routes (1930 and the portals), regulatory facts and
SEBI scam-guide pages are now verified and show. Still hidden: the **seven lessons** (the lesson text in
`data/learn/lessons.yaml` is not marked verified), the capital-gains tax card, and glossary pointers
that cite `sebi_investor_website` (both have open TODO_VERIFY items). Options:

1. **Verify the lessons and the two open facts (right answer for anything public).** Flip the flags,
   redeploy.
2. **Demo only:** add `RUKO_SHOW_UNVERIFIED_FACTS=true` to `--set-env-vars` for the demo, say so out
   loud, and remove it after. This shows unverified facts, so it is not for real users.

## Logging and privacy

Ruko's own logs hold only allow-listed fields (route template, status, timing, codes). Cloud Run
adds platform request logs that can include client network addresses. If that matters for a pilot
(`docs/pilot_protocol.md`), restrict them in Cloud Logging (a log exclusion filter) and say so in the
consent talk. The service never stores message text, audio or screenshots.

## Update, roll back, remove

```bash
# New release: run step 5 again (the same command builds and rolls out a new revision).
# Roll back to the previous revision:
gcloud run revisions list --service ruko
gcloud run services update-traffic ruko --to-revisions REVISION_NAME=100
# Remove everything (stops all billing for the service):
gcloud run services delete ruko
gcloud secrets delete ruko-sarvam-key
```

## Not tested here

The image was not built on this machine (Docker Desktop's engine was not running), and nothing
was deployed. The pieces were checked separately: `npm ci` and `npm run build` succeed, the backend
serves the built app (`tests/integration/test_static_serving.py`), and `scripts/smoke_test.py`
passes against the locally started app in both configurations. The first real build is the first
test of the `Dockerfile`; if it fails, the error will be in the Node stage or the `pip install` stage.
