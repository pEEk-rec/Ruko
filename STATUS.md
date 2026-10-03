# STATUS: Ruko backend build

Working mode: the repo owner asked for autonomous progress through all stages. Each stage
still passes its gates (full test suite + lint green, `docs/decisions.md` updated, report
below) before the next starts. **No git commands are run.** Proposed commits are listed per
stage and await the owner's approval. Items that need a human (approvals, live keys,
deployment host) are listed under "Waiting on you" and were not guessed.

Proposed commit messages contain no AI attribution (CLAUDE.md section 5).

---

## Waiting on you (rolled up)

- [ ] **Docker:** Docker is not installed on this machine, so `docker build` was not run.
      Substitute check done: non-editable `pip install .` into a clean venv + uvicorn served
      `/health` correctly. Please run `docker build -t ruko . && docker run -p 8000:8000 ruko`.

- [ ] **Stage 1 approval:** BUILD_PLAN asks you to explicitly approve `docs/journey_map.md`
      and `docs/observability_matrix.md`. In autonomous mode I continued with them marked
      "draft, awaiting approval"; later stages follow them, so changes there may ripple.

- [ ] **Native-speaker review of Hindi and Kannada text:** all `data/templates/hi.yaml` and
      `kn.yaml` entries, and the Hindi/Kannada/romanized patterns in `data/policy/guardrails.yaml`
      and (later) `data/lexicon/`, were drafted by me and are marked `draft`.

- [ ] **Verify facts in `data/facts/base_rates.yaml`** (all `verified_by_human: false`). Each has
      a page-cited quote from the primary SEBI PDF. Note: SEBI's FY26 Table 30 labels "medium"
      portfolios as ₹1-10 lakh and "large" as >₹1 crore while the counts sum to the total, so a
      band label looks wrong in the source; Ruko does not use those portfolio bands.
- [ ] **Policy numbers are my proposals:** band edges/typical values, the 10/25/50% leverage
      illustration, L1 budget 3/week, decay streak 5, L3 default cooling-off 15 min
      (`data/policy/intervention.yaml`). Please confirm or change.

- [ ] **Verify `data/facts/regulatory.yaml`** (all unverified): `@valid` UPI rule (SEBI circular
      2025/86, 11 Jun 2025), SEBI Check URL, SEBI recognised-intermediaries URL, the official
      domains list, and capital-gains figures (20% / 12.5% / ₹1.25 lakh / 12 months, as of
      23 Jul 2024). TODO_VERIFY: the Income-tax Act, 2025 (from 1 Apr 2026) renumbers these
      provisions; rates reported unchanged only by secondary sources.

---

## Stage reports

```
STAGE 0 DONE: Project foundation
What I built:
- FastAPI app factory (src/ruko/main.py) with GET /health returning status + version only
- Typed settings from RUKO_* env vars / .env (src/ruko/config.py), secrets as SecretStr
- Request-ID middleware + allow-listed JSON logging that never logs bodies, queries or raw paths
- Standard error contract {error: {code, message_key, retryable}} with typed ErrorCode enum
- Dockerfile, .gitignore, .dockerignore, .env.example, README run instructions, docs/decisions.md
Files added/changed: pyproject.toml, Dockerfile, .gitignore, .dockerignore, .env.example,
  README.md, STATUS.md, docs/decisions.md, src/ruko/{__init__,config,errors,observability,main}.py,
  src/ruko/api/{health,error_handlers}.py, empty packages per BUILD_PLAN section C,
  tests/conftest.py, tests/integration/{test_health,test_error_contract,test_no_body_logging}.py
Tests: 12 / 12 | Lint: pass (ruff check + ruff format --check) | Guardrail suite: n/a (Stage 2)
Facts needing human verification: none (no facts displayed yet)
Decisions I made that weren't in the plan:
- No pydantic-settings / python-dotenv dependency: settings are a plain Pydantic model with a
  10-line .env reader (keeps the stack as planned).
- Validation errors add an optional `fields` list (field locations only, never values) to the
  error object; the three contract keys are unchanged.
- httpx/httpcore loggers capped at WARNING and uvicorn access log disabled, because they print
  full URLs (found by the no-body-logging test).
- Request IDs from clients are accepted only if they match [A-Za-z0-9-]{8,64} (log-injection guard).
Open questions: none
Git: proposed `git init`, then commit "Set up FastAPI project skeleton" (awaiting approval)
```

```
STAGE 1 DONE: Spec documents and contracts
What I built:
- docs/journey_map.md (BEFORE/DURING/AFTER for both harm flows, with "must not" per step)
- docs/observability_matrix.md (every signal; broker/bank-only signals marked unavailable)
- docs/reason_codes.md (21 codes: meaning, trigger source, severity, solo level, template key)
- docs/intervention_policy.md (level table in plain language) and docs/api_contract.md
- Pydantic contracts in src/ruko/models/: RawInput, NormalizedInput, Signal, DecisionEvent,
  UserProfile (+ rules, plans, exit plan, attention counts), InterventionDecision, ExplanationCard,
  PauseResponse, RefusalResponse, ClarifyResponse, JournalEntry, RecoveryGuide, request bodies
Files added/changed: docs/{journey_map,observability_matrix,reason_codes,intervention_policy,
  api_contract,decisions}.md, src/ruko/models/{__init__,common,inputs,event,profile,decision,
  responses,journal,recovery,requests}.py, tests/unit/{test_models,test_request_models}.py
Tests: 45 / 45 | Lint: pass | Guardrail suite: n/a (Stage 2)
Facts needing human verification: none displayed yet
Decisions I made that weren't in the plan:
- Money = integer rupees (not paise).
- Profile sends bands by default (expense, savings, age bands matching SEBI's study bands),
  with optional exact figures; ratios are shown as ranges.
- Added DecisionEvent fields: holding_intent (for intraday-cost / tax cards), has_exit_plan,
  plan_id, protected_goal_id. Added profile.emergency_buffer_months (user-set; no Ruko default).
- Each reason code has a "solo level"; LEVERAGED_PRODUCT alone is L0 (informational), so an
  experienced user with an exit plan inside their rules is not nagged.
- Attention budget only silences L1 nudges whose reasons are all low severity (keeps the
  "L0 never has above-low reasons" property true).
- /v1/speak takes template references, not free text; responses carry `speak[]` for it.
- Voice and image arrive as base64 inside JSON (no python-multipart dependency).
- Broker order-intent takes an amount band; rule checks use its upper bound.
Open questions:
- Please approve or edit docs/journey_map.md and docs/observability_matrix.md (plan gate).
Git: proposed commit "Add journey map, signal matrix and data contracts" (awaiting approval)
```

```
STAGE 2 DONE: Guardrail layer
What I built:
- data/policy/guardrails.yaml: 5 pattern-based refusal classes (en, hi, kn, romanized hi/kn),
  sensitive-data patterns, injection cues, output-filter categories, broker/platform blocklist
- Intent gate (deterministic + optional second opinion that can only add refusals)
- Sensitive-data detector (OTP, PIN, CVV, password, Luhn card, first-person account number)
- Output filter (trade directives, return promises, safety claims, predictions, names) and the
  Renderer that runs it on every outgoing string; fixed localized refusal templates in en/hi/kn
- Adversarial suite: 100 cases across en, hi, kn, hi_latn, kn_latn, code-mixed
Files added/changed: data/policy/guardrails.yaml, data/templates/{en,hi,kn}.yaml,
  src/ruko/data_files.py, src/ruko/guardrails/{normalize,policy,intent_gate,sensitive,
  output_filter}.py, src/ruko/language/templates.py, tests/guardrails/{adversarial_cases.yaml,
  test_adversarial_suite,test_output_filter,test_sensitive}.py
Tests: 210 / 210 | Lint: pass | Guardrail suite: 100 / 100 cases refused or safely handled (100%);
  all 90 templates (30 keys x 3 locales) pass the output filter
Facts needing human verification: none
Decisions I made that weren't in the plan:
- Refusal patterns are question-shaped so forwarded tips ("BUY NOW, target 450") are analyzed,
  not refused.
- "Is this a scam / safe / legit?" is not refused: it is analyzed, with a fixed "Ruko can't vouch"
  line, and never a yes/no.
- Account numbers trigger the sensitive-data refusal only in first-person context; payee details
  in scam messages become signals instead (Stage 5).
- Prompt injection inside content is flagged (trace) and handled as data, not refused.
- The template store/renderer was built here (planned for Stage 3) because refusals need it.
- Evidence excerpts are not echoed back to clients.
Open questions: none
Git: proposed commit "Add guardrail gate and output filter" (awaiting approval)
```

```
STAGE 3 DONE: Language foundation
What I built:
- Language/script detection for en, hi, kn, romanized hi/kn and code-mixed text, with confidence
- Local PII redaction with counts by type (phone, upi_id, email, pan, card, account, name)
- Indian digit grouping and rupee amounts in words for en, hi, kn (lakh/crore)
- Template linter (completeness across locales, slot consistency, output-filter safety,
  required keys) and English fallback with missing-key recording
Files added/changed: data/language/{languages,numbers_en,numbers_hi,numbers_kn}.yaml,
  src/ruko/language/{detect,redact,numbers,template_lint}.py, tests/unit/test_language.py
Tests: 254 / 254 | Lint: pass | Guardrail suite: 100% (unchanged) | Template linter: green
Facts needing human verification:
- Hindi and Kannada number words (data/language/numbers_hi.yaml, numbers_kn.yaml) are drafts;
  in particular the Kannada hundreds forms (e.g. "ನೂರ ಐದು" for 105) need a native check.
Decisions I made that weren't in the plan:
- Language registry and number words are data files (adding a language = data only).
- UPI redaction keeps the handle and any SEBI category suffix (payee type), drops the username.
- Numbers right after ₹/Rs/INR are not redacted; spaced digit runs are only treated as
  card/account numbers in 4-4-4 grouping (so "10000 20000" stays as amounts).
- "Sir"/"Madam" are not treated as name salutations (they precede ordinary words in messages).
Open questions: none
Git: proposed commit "Add language detection, redaction and number words" (awaiting approval)
```

```
STAGE 4 DONE: Deterministic safety engine
What I built:
- Pure metric functions (months of expenses, share of savings, savings and buffer left, leverage
  illustration), as ranges with a typical value when the profile uses bands
- User-rule checks, declared-context signals, novelty, leverage, plan matching (relief and
  deviation), exit-plan check, level table (solo levels + combination rules)
- Weekly attention budget, friction decay, cooling-off suggestion, recovery-entry flag
- Base-rate selection from SEBI study data (age band preferred), with source, as_of, caveat key
Files added/changed: data/policy/intervention.yaml, data/facts/base_rates.yaml,
  src/ruko/engine/{policy,metrics,rules,novelty,context,plan,levels,attention,decay,base_rates,
  engine}.py, src/ruko/models/decision.py (typical value on ranges), docs/intervention_policy.md,
  tests/unit/test_engine.py
Tests: 305 / 305 | Lint: pass | Guardrail suite: 100% | Policy doc <-> YAML sync: pass
Facts needing human verification:
- 10 facts in data/facts/base_rates.yaml (SEBI FY26 F&O: overall 87.7%, by age band 88.55 /
  88.05 / 87.80 / 85.29 / 80.95%, costs = 35% of loss-makers' gross losses; SEBI FY23 intraday:
  71% overall, 76% under 30, costs added 57% to losses)
Decisions I made that weren't in the plan:
- Added engine/context.py (declared context + event-field signals) beside the planned modules.
- Leverage illustration uses 10/25/50% of the amount put in (2% of an options premium is not
  informative); it is labelled an illustration.
- Rule breaches computed from bands are certainty "possible" unless they hold across the band.
- FIRST_TIME_PRODUCT only from a declared "none"; EMERGENCY_BUFFER_AT_RISK only from the user's
  own buffer setting or a declared emergency fund.
- Matching a logged plan removes FIRST_TIME_PRODUCT and NO_EXIT_PLAN (plan relief).
- The intraday study has no causality statement, so its caveat is our generic "group, not a
  prediction" line; the FY26 study's own "descriptive, not cause-and-effect" caveat is quoted.
Open questions: none (policy numbers listed under "Waiting on you")
Git: proposed commit "Add deterministic intervention engine" (awaiting approval)
```

```
STAGE 5 DONE: Signal detection (deterministic)
What I built:
- Multilingual red-flag lexicons (en, hi, kn + romanized) for 9 reason codes, with weak/strong
  patterns and conservative certainty; extraction hints for the Stage 6 fallback
- Link analyzer on strings only (shortener, invite, APK, IP host, no HTTPS, punycode, lookalike
  of regulator/market domains by containment, affix or one edit)
- Payment-destination classifier on redacted placeholders (phone UPI, other UPI, @valid pattern,
  bank details in chat, QR); never infers "broker"
- regulatory.yaml with the SEBI @valid UPI rule (source, as_of, unverified) and facts.py accessor
Files added/changed: data/lexicon/{en,hi,kn}.yaml, data/policy/links.yaml,
  data/facts/regulatory.yaml, src/ruko/facts.py, src/ruko/understanding/{lexicon,links,
  payments}.py, src/ruko/language/redact.py (suffixes from data), tests/unit/test_signals.py
Tests: 393 / 393 | Lint: pass | Guardrail suite: 100% | False-positive set: 15/15 clean
Facts needing human verification: regulatory.yaml (5 entries, see "Waiting on you")
Decisions I made that weren't in the plan:
- The verified-handle rule exists: SEBI circular dated 11 Jun 2025, UPI IDs from 1 Oct 2025;
  encoded with verified_by_human: false. The @valid pattern is never treated as verification.
- Lookalike detection uses containment/affix/edit-distance-1 against an official-domains list
  kept in regulatory.yaml (data, not code).
- A non-phone UPI ID / bank details / QR only produce a signal with a payment instruction.
- Impersonation patterns are narrow (regulator "officer/department", "on behalf of", frozen
  account threats) because the code is critical severity (L3).
Open questions: none
Git: proposed commit "Add multilingual red-flag and link checks" (awaiting approval)
```
