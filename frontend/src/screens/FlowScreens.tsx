// Screens after the pause: learn, decide, journal summary, and the error state.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { ChoiceList } from "../components/ChoiceList";
import { JournalSummary } from "../components/JournalSummary";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import { FlowSteps } from "../components/FlowSteps";
import { LessonShorts, slidesFor } from "../components/LessonShorts";
import { RukoMessage } from "../components/RukoMessage";
import type { AppErrorKind } from "../services/api";
import type { JournalRecord, PauseFeeling } from "../services/device";
import { parseAmount } from "../components/ClarificationChoice";
import type {
  CalculatorTool,
  ExplanationCard,
  JournalAction,
  Lesson,
  PauseResponse,
} from "../types/api";

/** "Why this matters": the backend's explanation cards and lessons (at most 3 together). */
export function LearnScreen({
  cards,
  lessons = [],
  onReflect,
  onBack,
  onTool,
}: {
  cards: ExplanationCard[];
  lessons?: Lesson[];
  onReflect: () => void;
  onBack: () => void;
  onTool?: (tool: CalculatorTool) => void;
}) {
  const t = useCopy();
  return (
    <ScreenBody actions={<ActionButton label={t.back} onClick={onBack} variant="text" />}>
      <FlowSteps step={1} />
      <Eyebrow>{t.learnEyebrow}</Eyebrow>
      <LessonShorts
        label={t.learnEyebrow}
        slides={slidesFor(lessons, cards, "learn", onTool)}
        end={{ title: t.shortsEndTitle, body: t.shortsEndBody, action: t.thinkThrough, onAction: onReflect }}
      />
    </ScreenBody>
  );
}

const PLAN_REASONS = ["UNPLANNED_DECISION", "PLAN_INCOMPLETE", "PLAN_DEVIATION"];

/**
 * The options for this decision, in an order that fits it: a stronger pause leads with waiting
 * and reconsidering and puts "go ahead" last; a small nudge leads with going ahead. A plan is
 * offered first when the decision lacks one. Every option stays available and equal.
 */
export function decisionOptions(pause: PauseResponse | null): JournalAction[] {
  const strong = pause?.level === "L2" || pause?.level === "L3";
  const needsPlan = !!pause?.decision.reasons.some((r) => PLAN_REASONS.includes(r.code));
  const core: JournalAction[] = strong
    ? ["delayed", "changed_amount", "dropped", "went_ahead"]
    : ["went_ahead", "delayed", "changed_amount", "dropped"];
  return needsPlan ? ["set_plan", ...core] : [...core, "set_plan"];
}

/** The user's own decision. Every option is equal; Ruko does not pick one. */
export function DecideScreen({
  pause = null,
  onDecide,
  onChangeAmount,
  onPlan,
}: {
  pause?: PauseResponse | null;
  onDecide: (action: JournalAction) => void;
  /** Re-check the same message with a different amount. */
  onChangeAmount?: (amount: number) => void;
  /** Open the plan builder. */
  onPlan?: () => void;
}) {
  const t = useCopy();
  const [selected, setSelected] = useState<JournalAction | null>(null);
  const [amount, setAmount] = useState("");
  const [invalid, setInvalid] = useState(false);
  const options = decisionOptions(pause).filter(
    (o) => (o !== "changed_amount" || !!onChangeAmount) && (o !== "set_plan" || !!onPlan),
  );
  const changing = selected === "changed_amount";

  function choose(value: JournalAction) {
    if (value === "set_plan") return onPlan?.();
    setSelected(value);
    setInvalid(false);
  }

  function proceed() {
    if (!selected) return;
    if (changing) {
      const value = parseAmount(amount);
      if (value === null) return setInvalid(true);
      return onChangeAmount?.(value);
    }
    onDecide(selected);
  }

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton
            label={changing ? t.changeAmountButton : t.continue}
            onClick={proceed}
            disabled={selected === null}
          />
          <ScreenFooter>{t.pauseFooter}</ScreenFooter>
        </>
      }
    >
      <FlowSteps step={3} />
      <Eyebrow>{t.decideEyebrow}</Eyebrow>
      <RukoMessage text={t.decideTitle} subtext={t.decideBody} />
      <ChoiceList
        name={t.decideTitle}
        choices={options.map((value) => ({ value, label: t.actions[value] }))}
        selected={selected}
        onSelect={(value) => choose(value as JournalAction)}
      />
      {changing ? (
        <label className="field">
          <span className="field-label">{t.changeAmountTitle}</span>
          <input
            className="input"
            inputMode="numeric"
            autoComplete="off"
            placeholder={t.amountPlaceholder}
            value={amount}
            aria-invalid={invalid}
            onChange={(e) => {
              setAmount(e.target.value);
              setInvalid(false);
            }}
            onKeyDown={(e) => e.key === "Enter" && proceed()}
          />
          {invalid ? (
            <span className="field-error" role="alert">
              {t.clarifyAmountInvalid}
            </span>
          ) : null}
        </label>
      ) : null}
    </ScreenBody>
  );
}

/**
 * "Decision recorded": shows the note; keeping it on the device is the user's choice. After a
 * pause (at most once a week) it offers an optional one-tap rating of how the pause felt.
 */
export function JournalSavedScreen({
  record,
  askFeeling = false,
  onFinish,
}: {
  record: JournalRecord | null;
  askFeeling?: boolean;
  onFinish: (keep: boolean, feeling?: PauseFeeling | null) => void;
}) {
  const t = useCopy();
  const [feeling, setFeeling] = useState<PauseFeeling | null>(null);
  const labels: Record<PauseFeeling, string> = {
    helpful: t.feelingHelpful,
    fine: t.feelingFine,
    annoying: t.feelingAnnoying,
  };
  return (
    <ScreenBody
      actions={
        <>
          <ActionButton label={t.done} onClick={() => onFinish(true, feeling)} />
          <ActionButton label={t.dontKeep} onClick={() => onFinish(false)} variant="text" />
          <ScreenFooter>{t.journalFooter}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.journalEyebrow}</Eyebrow>
      <span className="check" aria-hidden="true">
        ✓
      </span>
      <RukoMessage text={t.journalSavedTitle} subtext={t.journalSavedBody} />
      {record ? <JournalSummary record={record} /> : null}
      {askFeeling ? (
        <section className="card" aria-label={t.feelingAsk}>
          <h2 className="card-label">{t.feelingAsk}</h2>
          <ChoiceList
            name={t.feelingAsk}
            choices={(Object.keys(labels) as PauseFeeling[]).map((value) => ({
              value,
              label: labels[value],
            }))}
            selected={feeling}
            onSelect={(value) => setFeeling(value === feeling ? null : (value as PauseFeeling))}
          />
          {feeling ? (
            <p className="meta-line" role="status">
              {t.feelingThanks}
            </p>
          ) : null}
        </section>
      ) : null}
      <p className="muted">{t.journalOutro}</p>
    </ScreenBody>
  );
}

/** Journal list (device only). */
export function JournalListScreen({ records, onBack }: { records: JournalRecord[]; onBack: () => void }) {
  const t = useCopy();
  return (
    <ScreenBody
      actions={
        <>
          <ActionButton label={t.back} onClick={onBack} />
          <ScreenFooter>{t.journalFooter}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.journalEyebrow}</Eyebrow>
      {records.length === 0 ? <p className="muted">{t.journalEmpty}</p> : null}
      {records.map((record) => (
        <JournalSummary key={record.entry.id} record={record} />
      ))}
    </ScreenBody>
  );
}

/** Calm, actionable error. Never shows codes, stack traces or raw responses. */
export function ErrorScreen({
  kind,
  onRetry,
  onStartOver,
}: {
  kind: AppErrorKind;
  onRetry: () => void;
  onStartOver: () => void;
}) {
  const t = useCopy();
  const canRetry = kind !== "unsupported_input" && kind !== "invalid_request";
  return (
    <ScreenBody
      actions={
        <>
          {canRetry ? <ActionButton label={t.tryAgain} onClick={onRetry} /> : null}
          <ActionButton label={t.startOver} onClick={onStartOver} variant={canRetry ? "text" : "primary"} />
        </>
      }
    >
      <Eyebrow>{t.errorEyebrow}</Eyebrow>
      <div role="alert">
        <RukoMessage text={t.errors[kind]} />
      </div>
    </ScreenBody>
  );
}
