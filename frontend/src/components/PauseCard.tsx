// One component for every intervention level. What appears comes from the backend response:
// the level picks the presentation, and each section renders only if the backend sent it.
// The frontend never computes a level, a signal or a verdict.

import { useCopy } from "../CopyContext";
import type { CoolingOff } from "../state/flow";
import type { InterventionLevel, PauseResponse } from "../types/api";
import { ActionButton, ActionRow } from "./ActionButton";
import { CoolingOffTimer } from "./CoolingOffTimer";
import { Eyebrow, NoticeCard, ScreenBody, ScreenFooter } from "./Layout";
import { ListenButton } from "./ListenButton";
import { PersonalContextCard } from "./PersonalContextCard";
import { RukoMessage } from "./RukoMessage";
import { SignalCard } from "./SignalCard";

interface Props {
  pause: PauseResponse;
  onLearn: () => void;
  onReflect: () => void;
  onContinue: () => void;
  onRecover: () => void;
  /** Records an L3 wait (finished or skipped). Optional: without it no timer is shown. */
  onCooling?: (coolingOff: CoolingOff) => void;
  /** "Quiet" style trims optional extras on a small nudge; the backend decides everything else. */
  quiet?: boolean;
}

/** Presentation per level: how strong the pause is, never whether it can be skipped. */
const PRESENTATION: Record<
  InterventionLevel,
  { showContext: boolean; reflectFirst: boolean; tone: string }
> = {
  L0: { showContext: false, reflectFirst: false, tone: "calm" },
  L1: { showContext: false, reflectFirst: false, tone: "nudge" },
  L2: { showContext: true, reflectFirst: false, tone: "pause" },
  L3: { showContext: true, reflectFirst: true, tone: "strong" },
};

export function PauseCard({
  pause,
  onLearn,
  onReflect,
  onContinue,
  onRecover,
  onCooling,
  quiet = false,
}: Props) {
  const t = useCopy();
  const level = pause.level;
  const view = PRESENTATION[level];
  const lessons = pause.lessons ?? [];
  const hasCards = pause.cards.length + lessons.length > 0;
  const hasContentSignal = pause.decision.reasons.some((r) => r.dimension === "content");
  const cooling = pause.decision.cooling_off_minutes;

  const spoken = [
    pause.headline,
    ...pause.signals.map((signal) => signal.reason_text ?? signal.text),
    ...pause.rules_text,
    ...pause.numbers_text,
    pause.question ?? "",
  ].join(" ");
  const actions = renderActions();

  return (
    <div className={`pause pause-${view.tone}`} data-level={level}>
      <ScreenBody actions={actions}>
        <Eyebrow>{t.levelEyebrow[level]}</Eyebrow>
        <RukoMessage text={pause.headline} />
        <SignalCard signals={pause.signals} />
        {level !== "L0" && level !== "L1" && hasContentSignal ? (
          <NoticeCard>{t.cannotTell}</NoticeCard>
        ) : null}
        {view.showContext ? (
          <PersonalContextCard numbers={pause.numbers_text} rules={pause.rules_text} />
        ) : null}
        {pause.question && !(quiet && level === "L1") ? (
          <p className="reflection-question">{pause.question}</p>
        ) : null}
        {level === "L3" && cooling && onCooling ? (
          <CoolingOffTimer
            minutes={cooling}
            onFinish={(skipped) => onCooling({ minutes: cooling, skipped })}
          />
        ) : null}
        <ListenButton source={{ items: pause.speak }} text={spoken} />
        {pause.recovery_entry ? (
          <button type="button" className="recovery-link" onClick={onRecover}>
            {pause.recovery_entry.text}
          </button>
        ) : null}
      </ScreenBody>
    </div>
  );

  function renderActions() {
    const footer = (
      <ScreenFooter>{level === "L1" || level === "L0" ? t.pauseFooterL1 : t.pauseFooter}</ScreenFooter>
    );
    if (level === "L0") {
      return (
        <>
          <ActionButton label={t.continue} onClick={onContinue} />
          {footer}
        </>
      );
    }
    if (level === "L1") {
      return (
        <>
          {hasCards ? <ActionButton label={t.learnWhy} onClick={onLearn} /> : null}
          <ActionButton
            label={t.continue}
            onClick={onContinue}
            variant={hasCards ? "text" : "primary"}
          />
          {footer}
        </>
      );
    }
    // L2 and L3: reflection is offered, continuing is always one tap away.
    const primaryIsLearn = !view.reflectFirst && hasCards;
    return (
      <>
        <ActionButton
          label={primaryIsLearn ? t.learnWhy : t.thinkThrough}
          onClick={primaryIsLearn ? onLearn : onReflect}
        />
        <ActionRow>
          {primaryIsLearn ? (
            <ActionButton label={t.thinkThrough} onClick={onReflect} variant="text" />
          ) : hasCards ? (
            <ActionButton label={t.learn} onClick={onLearn} variant="text" />
          ) : null}
          <ActionButton label={pause.override_label} onClick={onContinue} variant="text" />
        </ActionRow>
        {footer}
      </>
    );
  }
}
