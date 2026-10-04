// Screens after the pause: learn, decide, journal summary, and the error state.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { ChoiceList } from "../components/ChoiceList";
import { JournalSummary } from "../components/JournalSummary";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import { LearnCard } from "../components/LearnCard";
import { LessonCard } from "../components/LessonCard";
import { RukoMessage } from "../components/RukoMessage";
import type { AppErrorKind } from "../services/api";
import type { JournalRecord, PauseFeeling } from "../services/device";
import type { CalculatorTool, ExplanationCard, JournalAction, Lesson } from "../types/api";

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
    <ScreenBody
      actions={
        <>
          <ActionButton label={t.thinkThrough} onClick={onReflect} />
          <ActionButton label={t.back} onClick={onBack} variant="text" />
        </>
      }
    >
      <Eyebrow>{t.learnEyebrow}</Eyebrow>
      {cards.map((card) => (
        <LearnCard key={card.id} card={card} />
      ))}
      {lessons.map((lesson) => (
        <LessonCard key={lesson.id} lesson={lesson} onTool={onTool} />
      ))}
    </ScreenBody>
  );
}

const DECISION_ORDER: JournalAction[] = ["delayed", "changed_amount", "dropped", "went_ahead"];

/** The user's own decision. Every option is equal; Ruko does not pick one. */
export function DecideScreen({ onDecide }: { onDecide: (action: JournalAction) => void }) {
  const t = useCopy();
  const [selected, setSelected] = useState<JournalAction | null>(null);
  return (
    <ScreenBody
      actions={
        <>
          <ActionButton
            label={t.continue}
            onClick={() => selected && onDecide(selected)}
            disabled={selected === null}
          />
          <ScreenFooter>{t.pauseFooter}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.decideEyebrow}</Eyebrow>
      <RukoMessage text={t.decideTitle} subtext={t.decideBody} />
      <ChoiceList
        name={t.decideTitle}
        choices={DECISION_ORDER.map((value) => ({ value, label: t.actions[value] }))}
        selected={selected}
        onSelect={(value) => setSelected(value as JournalAction)}
      />
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
