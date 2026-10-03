# Ruko order-intent API: broker embedding spec (v1)

> Status: draft public spec. Endpoint: `POST /v1/order-intent`.

## Purpose

A broker app can ask Ruko, just before an order is placed, whether this order touches
the user's own rules or a known risk pattern. Ruko answers with a **level and reason
codes only**. It never sees which instrument is being traded, never sees who the user
is, and never says anything about the order's merits.

## Request

```json
{
  "product_class": "derivative",
  "amount_band": {"min_inr": 10000, "max_inr": 50000},
  "borrowed_funds": false,
  "leveraged": false,
  "exit_plan_set": true,
  "profile": {
    "liquid_savings_band": "1l_3l",
    "rules": {"max_share_of_savings_pct": 10, "no_borrowed_money": true},
    "experience": {"derivative": "none"}
  }
}
```

| Field | Meaning |
|---|---|
| `product_class` | `cash_equity`, `derivative`, `ipo`, `mutual_fund`, `scheme_or_app`, `crypto`, `unknown` |
| `amount_band` | Order value range in whole rupees. Rule checks use `max_inr`. Send a band, not the exact value. |
| `borrowed_funds` | The user said the money is borrowed (for example a margin or loan facility the user flagged). |
| `leveraged` | The order uses leverage or margin. Adds `LEVERAGED_PRODUCT` even for cash orders. |
| `exit_plan_set` | An exit is attached to the order (for example a stop-loss). `null` = unknown. Without it, derivative orders get `NO_EXIT_PLAN`. |
| `profile` | The snapshot the **user** chose to share from their Ruko app (rules, bands, experience). Optional. |

There is **no field** for a symbol, ISIN, price, client ID, PAN, name or phone number. Unknown
fields are rejected with `422 INVALID_REQUEST`.

## Response

```json
{
  "kind": "order_intent",
  "level": "L2",
  "reason_codes": ["BORROWED_FUNDS", "NO_EXIT_PLAN", "LEVERAGED_PRODUCT"],
  "override_allowed": true,
  "policy_version": "1"
}
```

- `level`: `L0` (no friction) to `L3` (strong pause). See `docs/intervention_policy.md`.
- `reason_codes`: most severe first. Meanings in `docs/reason_codes.md`.
- `override_allowed` is always `true`: the broker must let the user continue.
- No text is returned. A broker that shows anything to the user should open the user's own
  Ruko app (which renders localized, filtered text) rather than write its own wording.

## Rules for integrators

1. Never block an order based on this response; show a pause and let the user decide.
2. Never use the level to promote, discourage or rank a product, broker or instrument.
3. Do not store the profile snapshot; it belongs to the user's device.
4. Ruko is stateless and keeps nothing from these calls; logs contain only request IDs,
   timings and reason codes.

## Errors

The standard error contract applies (`docs/api_contract.md`): `INVALID_REQUEST` (422),
`PAYLOAD_TOO_LARGE` (413), `UNSUPPORTED_MEDIA_TYPE` (415), `RATE_LIMITED` (429).
