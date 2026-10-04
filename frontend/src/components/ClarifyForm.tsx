// All the questions Ruko needs, on one screen, instead of one screen per question.
//
// It adapts to the person and to the message:
// - the amount question offers the amounts the message itself mentions, as one-tap chips
//   (a tap confirms; nothing is ever filled in for them);
// - the option that matches what the message describes carries a small tag;
// - the funding source they chose last time carries a "Last time" tag;
// - once a product is known, it asks (once, optionally) how familiar that kind of decision is,
//   and, for trading products, how trading has been lately. Both are kept on this phone and
//   sent as the person's own declaration, never observed.
//
// The same form serves the calculator's missing numbers (numeric questions, no skipping).

import { useMemo, useState } from "react";
import { useCopy } from "../CopyContext";
import { loadProfile, saveProfile } from "../services/device";
import { freshRecent, loadMemory, rememberFunding, rememberRecent } from "../services/memory";
import type {
  ClarifyQuestion,
  DecisionAnswers,
  Experience,
  FundingSource,
  ProductClass,
  TradesPerWeekBand,
} from "../types/api";
import { ActionButton } from "./ActionButton";
import { ChoiceList } from "./ChoiceList";
import { parseAmount, answerFor } from "./ClarificationChoice";
import { Eyebrow, ScreenBody, ScreenFooter } from "./Layout";

const ASKS_EXPERIENCE: ProductClass[] = ["cash_equity", "derivative", "ipo", "mutual_fund", "crypto"];
const ASKS_RECENT: ProductClass[] = ["cash_equity", "derivative", "crypto"];
const TRADE_BANDS: TradesPerWeekBand[] = ["0", "1_5", "6_20", "gt_20"];

interface Props {
  questions: ClarifyQuestion[];
  /** The product, if it is already known (the form then asks the optional questions for it). */
  knownProduct?: ProductClass | null;
  onComplete: (answers: DecisionAnswers) => void;
  /** Hide the screen chrome (used when the form sits inside another screen). */
  embedded?: boolean;
  /** Label of the submit button (defaults to "Continue"). */
  submitLabel?: string;
}

const isNumeric = (q: ClarifyQuestion) => q.options.length === 0;
const canSkip = (q: ClarifyQuestion) => !q.field.startsWith("calculation.");

export function ClarifyForm({
  questions,
  knownProduct,
  onComplete,
  embedded = false,
  submitLabel,
}: Props) {
  const t = useCopy();
  const memory = useMemo(() => loadMemory(), []);
  const profile = useMemo(() => loadProfile(), []);
  const [values, setValues] = useState<Record<string, string>>({});
  const [skipped, setSkipped] = useState<string[]>([]);
  const [tried, setTried] = useState(false);
  const [experience, setExperience] = useState<Experience | null>(null);
  const [lostRecently, setLostRecently] = useState<"yes" | "no" | null>(null);
  const [trades, setTrades] = useState<TradesPerWeekBand | null>(null);

  const product = (values.product_class ??
    (knownProduct && knownProduct !== "unknown" ? knownProduct : undefined)) as
    | ProductClass
    | undefined;
  const askExperience =
    !!product && ASKS_EXPERIENCE.includes(product) && profile.experience?.[product] === undefined;
  const askRecent = !!product && ASKS_RECENT.includes(product) && !freshRecent(memory);

  const valid = (q: ClarifyQuestion): boolean => {
    if (skipped.includes(q.field)) return true;
    const value = values[q.field];
    if (value === undefined || value === "") return false;
    return isNumeric(q) ? parseAmount(value) !== null : true;
  };
  const allValid = questions.every(valid);

  function submit() {
    setTried(true);
    if (!allValid) return;
    let answers: DecisionAnswers = {};
    for (const q of questions) {
      if (skipped.includes(q.field)) {
        answers = { ...answers, skipped_fields: [...(answers.skipped_fields ?? []), q.field] };
        continue;
      }
      const raw = values[q.field];
      answers = {
        ...answers,
        ...answerFor(q.field, isNumeric(q) ? (parseAmount(raw) as number) : raw),
        ...(answers.skipped_fields ? { skipped_fields: answers.skipped_fields } : {}),
      };
    }
    // Remember what the person told us, before the next request reads it.
    rememberFunding(answers.funding_source as FundingSource | undefined);
    if (product && experience) {
      saveProfile({ ...profile, experience: { ...profile.experience, [product]: experience } });
    }
    if (askRecent && (lostRecently || trades)) {
      rememberRecent({ postLoss: lostRecently === "yes", trades: trades ?? "0" });
    }
    onComplete(answers);
  }

  const set = (field: string, value: string) => {
    setValues((v) => ({ ...v, [field]: value }));
    setSkipped((s) => s.filter((f) => f !== field));
  };

  const body = (
    <>
      {questions.map((q) => {
        const missing = tried && !valid(q);
        return (
          <section key={q.field} className="card" aria-label={q.text}>
            <h2 className="card-label">{q.text}</h2>
            {isNumeric(q) ? (
              <div className="field">
                {(q.hints ?? []).length > 0 ? (
                  <div className="choice-list choice-list-compact">
                    {(q.hints ?? []).map((hint) => (
                      <button
                        key={hint.value}
                        type="button"
                        className={`choice ${values[q.field] === hint.value ? "choice-selected" : ""}`}
                        onClick={() => set(q.field, hint.value)}
                      >
                        {hint.label}
                      </button>
                    ))}
                  </div>
                ) : null}
                <input
                  className="input"
                  inputMode="numeric"
                  autoComplete="off"
                  aria-label={q.text}
                  aria-invalid={missing}
                  placeholder={q.field.endsWith("_inr") ? t.clarifyAmountPlaceholder : t.clarifyNumberPlaceholder}
                  value={values[q.field] ?? ""}
                  disabled={skipped.includes(q.field)}
                  onChange={(e) => set(q.field, e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                />
                {canSkip(q) ? (
                  <button
                    type="button"
                    className="btn btn-text"
                    onClick={() =>
                      setSkipped((s) => (s.includes(q.field) ? s.filter((f) => f !== q.field) : [...s, q.field]))
                    }
                  >
                    {skipped.includes(q.field) ? t.clarifyAnswerAfterSkip : t.clarifySkip}
                  </button>
                ) : null}
              </div>
            ) : (
              <ChoiceList
                name={q.text}
                compact
                choices={q.options.map((o) => ({
                  value: o.value,
                  label: o.label,
                  tag:
                    q.suggested === o.value
                      ? q.suggested_tag
                      : q.field === "funding_source" && memory.lastFunding === o.value
                        ? t.lastTime
                        : null,
                }))}
                selected={values[q.field] ?? null}
                onSelect={(value) => set(q.field, value)}
              />
            )}
            {missing ? (
              <p className="field-error" role="alert">
                {isNumeric(q)
                  ? q.field.endsWith("_inr")
                    ? t.clarifyAmountInvalid
                    : t.clarifyNumberInvalid
                  : t.clarifyChooseOne}
              </p>
            ) : null}
          </section>
        );
      })}

      {askExperience || askRecent ? (
        <section className="card card-context" aria-label={t.aboutYouTitle}>
          <h2 className="card-label">{t.aboutYouTitle}</h2>
          <p className="hint">{t.aboutYouNote}</p>
          {askExperience ? (
            <>
              <p className="field-label">{t.experienceQuestion}</p>
              <ChoiceList
                name={t.experienceQuestion}
                compact
                choices={(["none", "some", "regular"] as Experience[]).map((v) => ({
                  value: v,
                  label: t.experienceOptions[v],
                }))}
                selected={experience}
                onSelect={(v) => setExperience(v === experience ? null : (v as Experience))}
              />
            </>
          ) : null}
          {askRecent ? (
            <>
              <p className="field-label">{t.recentLossQuestion}</p>
              <ChoiceList
                name={t.recentLossQuestion}
                compact
                choices={(["yes", "no"] as const).map((v) => ({ value: v, label: t.recentLossOptions[v] }))}
                selected={lostRecently}
                onSelect={(v) => setLostRecently(v === lostRecently ? null : (v as "yes" | "no"))}
              />
              <p className="field-label">{t.tradesQuestion}</p>
              <ChoiceList
                name={t.tradesQuestion}
                compact
                choices={TRADE_BANDS.map((v) => ({ value: v, label: t.tradesOptions[v] }))}
                selected={trades}
                onSelect={(v) => setTrades(v === trades ? null : (v as TradesPerWeekBand))}
              />
            </>
          ) : null}
        </section>
      ) : null}

      <ActionButton label={submitLabel ?? t.clarifyContinue} onClick={submit} />
    </>
  );

  if (embedded) return <div className="stack">{body}</div>;
  return (
    <ScreenBody actions={<ScreenFooter>{t.clarifyFooter}</ScreenFooter>}>
      <Eyebrow>{t.clarifyEyebrow}</Eyebrow>
      {body}
    </ScreenBody>
  );
}
