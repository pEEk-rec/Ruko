# Impact metrics: what "measurably helps" means for Ruko

Ruko should help people make decisions they would still stand by later, without making them
dependent on Ruko. These metrics are computed per user, on the device's own journal, by
`POST /v1/journal/review` (stateless), and in aggregate only if users choose to share them.

| Metric | Definition | Journal fields used | Where |
|---|---|---|---|
| Pause completion rate | Share of L2/L3 pauses the user read through to the end | `level_shown`, `pause_completed` | `pause_completion_pct` |
| Reconsideration rate | Share of pauses after which the user changed the amount, delayed, wrote a plan, or let it go | `level_shown`, `action` (`changed_amount`, `delayed`, `set_plan`, `dropped`) | `reconsideration_pct` |
| Comprehension | Share of pauses where the user could say why the pause appeared | `could_state_why` | `comprehension_pct` |
| Override with reason | Overrides are fine; unexplained overrides are a signal to look at | `overrode`, `override_reason_given` | `overrides_with_reason`, `overrides_without_reason` |
| Plans set and followed | Share of decisions with a written plan; share of logged plans that were followed | `plan`, `plan_followed` | `plans_set_pct`, `plans_followed_pct`, `plans_pending` |
| Unsolicited share | Share of decisions that started from a group tip or an influencer | `source_type` | `unsolicited_share_pct` |
| Rule articulation over time | Do the user's own written rules and plans grow? | `own_rules_count`, `own_plans_count` (first vs latest entry) | `rule_articulation` |
| Quiet-on-ordinary | Share of ordinary decisions left alone (L0) | evaluation dataset | `docs/eval_report.md` |
| Over-intervention | Share of ordinary decisions given L2/L3 | evaluation dataset | `docs/eval_report.md` |

## What is explicitly NOT a success metric

- **"Fewer interventions" on its own.** A falling count can mean the user's decisions got
  calmer, but it can equally mean Ruko became less sensitive. The weekly
  interventions-per-decision points are returned as data and never framed as a score.
- **Gains or losses.** Outcomes depend on markets; Ruko never judges a strategy by its result,
  so outcome fields are stored on the device but not analysed.
- **Engagement.** Time in app, streaks for their own sake, or notifications opened. Success is
  the user needing Ruko less, through their own rules and plans.

## Interpreting the numbers honestly

- All rates come from what the user logged; they are self-reports.
- Tiny journals (fewer than 3 entries) still get numbers, with a "too early" note.
- No comparison with other users and no ranking, ever.
