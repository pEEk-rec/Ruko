// "My patterns": the user's own journal, reviewed by /v1/journal/review. Only the journal
// entries (the backend's JournalEntry fields: no notes, no excerpts) are sent, for this one
// request, and nothing is kept. The numbers and highlights are the backend's; nothing is
// scored here, and fewer pauses is never shown as success.

import { useEffect, useState } from "react";
import { useCopy, useLocale } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, NoticeCard, ScreenBody, ScreenFooter } from "../components/Layout";
import { ProcessingState } from "../components/ProcessingState";
import { RukoMessage } from "../components/RukoMessage";
import { reviewJournal } from "../services/api";
import { loadJournal } from "../services/device";
import type { JournalReviewResponse } from "../types/api";

type Phase = "loading" | "empty" | "offline" | "ready";

type MetricKey =
  | "total_decisions"
  | "unsolicited_share_pct"
  | "plans_set_pct"
  | "pauses"
  | "pause_completion_pct"
  | "comprehension_pct"
  | "reconsideration_pct"
  | "overrides_with_reason"
  | "overrides_without_reason";

const METRICS: MetricKey[] = [
  "total_decisions",
  "unsolicited_share_pct",
  "plans_set_pct",
  "pauses",
  "pause_completion_pct",
  "comprehension_pct",
  "reconsideration_pct",
  "overrides_with_reason",
  "overrides_without_reason",
];

/** Show a backend number as-is: percentages get a % sign, missing values say so. */
export function metricText(key: MetricKey, review: JournalReviewResponse, notEnough: string): string {
  const value = review[key];
  if (value === null || value === undefined) return notEnough;
  return key.endsWith("_pct") ? `${value}%` : String(value);
}

export function MirrorScreen({ onBack }: { onBack: () => void }) {
  const t = useCopy();
  const locale = useLocale();
  const [phase, setPhase] = useState<Phase>("loading");
  const [review, setReview] = useState<JournalReviewResponse | null>(null);

  useEffect(() => {
    let alive = true;
    const entries = loadJournal().map((record) => record.entry);
    if (entries.length === 0) {
      setPhase("empty");
      return;
    }
    setPhase("loading");
    reviewJournal(locale, entries)
      .then((result) => {
        if (!alive) return;
        setReview(result);
        setPhase("ready");
      })
      .catch(() => alive && setPhase("offline"));
    return () => {
      alive = false;
    };
  }, [locale]);

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton label={t.back} onClick={onBack} />
          <ScreenFooter>{t.journalFooter}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.mirrorEyebrow}</Eyebrow>
      <RukoMessage text={t.mirrorTitle} subtext={t.mirrorBody} />
      {phase === "loading" ? <ProcessingState /> : null}
      {phase === "empty" ? <p className="muted">{t.mirrorEmpty}</p> : null}
      {phase === "offline" ? (
        <div role="alert">
          <NoticeCard>{t.mirrorOffline}</NoticeCard>
        </div>
      ) : null}
      {phase === "ready" && review ? (
        <>
          {review.highlights.length > 0 ? (
            <section className="card">
              <ul className="plain-list">
                {review.highlights.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </section>
          ) : null}
          <section className="card" aria-label={t.mirrorEyebrow}>
            <dl className="metric-list">
              {METRICS.map((key) => (
                <div key={key} className="metric-row">
                  <dt>{t.mirrorMetrics[key]}</dt>
                  <dd>{metricText(key, review, t.mirrorNotEnough)}</dd>
                </div>
              ))}
            </dl>
          </section>
          {review.weekly.length > 0 ? (
            <section className="card" aria-label={t.mirrorWeekly}>
              <h2 className="card-label">{t.mirrorWeekly}</h2>
              <ul className="plain-list">
                {review.weekly.map((week) => (
                  <li key={week.week_start} className="week-row">
                    <span>{t.mirrorWeek(week.week_start)}</span>
                    <span className="week-bar" aria-hidden="true">
                      <span style={{ width: `${Math.min(1, week.per_decision) * 100}%` }} />
                    </span>
                    <span>
                      {week.interventions} / {week.decisions}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <p className="muted">{t.mirrorOutro}</p>
        </>
      ) : null}
    </ScreenBody>
  );
}
