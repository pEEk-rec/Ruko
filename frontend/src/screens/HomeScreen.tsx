import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Icon, type IconName } from "../components/Icon";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import type { HomeCard } from "../state/home";

interface Props {
  onShare: () => void;
  onDecision: () => void;
  onCalculate: () => void;
  onAlreadyPaid: () => void;
  onRules: () => void;
  onJournal: () => void;
  onMirror: () => void;
  onSettings: () => void;
  onLearn?: () => void;
  onOpenLesson?: (lessonId: string) => void;
  /** What matters to this person right now (see state/home.ts). */
  cards?: HomeCard[];
  /** Has used Ruko before: the greeting changes. */
  returning?: boolean;
  onWaitLookAgain?: (id: string) => void;
  onWaitLetGo?: (id: string) => void;
  onPlanFollow?: (entryId: string, followed: boolean | null) => void;
  onDismiss?: (card: "rules" | "patterns" | "learn") => void;
  /** Counts from this phone only: own rules, decisions in the last 7 days, lessons read. */
  snapshot?: { rules: number; decisions: number; lessons: number };
  /** Local hour, for the greeting. */
  hour?: number;
}

export function HomeScreen(props: Props) {
  const t = useCopy();
  const tiles: { label: string; hint: string; icon: IconName; onClick: () => void }[] = [
    ...(props.onLearn
      ? [{ label: t.learnTile, hint: t.learnTileHint, icon: "learn" as IconName, onClick: props.onLearn }]
      : []),
    { label: t.workOutNumber, hint: t.workOutNumberHint, icon: "calc", onClick: props.onCalculate },
    { label: t.alreadyPaid, hint: t.alreadyPaidHint, icon: "help", onClick: props.onAlreadyPaid },
    { label: t.myRules, hint: t.myRulesHint, icon: "rules", onClick: props.onRules },
    { label: t.journal, hint: t.journalHint, icon: "journal", onClick: props.onJournal },
    { label: t.myPatterns, hint: t.myPatternsHint, icon: "pattern", onClick: props.onMirror },
    { label: t.settings, hint: t.settingsHint, icon: "settings", onClick: props.onSettings },
  ];
  const hour = props.hour ?? new Date().getHours();
  const greeting = hour < 12 ? t.greetMorning : hour < 17 ? t.greetAfternoon : t.greetEvening;
  const snap = props.snapshot;
  return (
    <ScreenBody actions={<ScreenFooter>{t.homeFooter}</ScreenFooter>}>
      <Eyebrow>{props.returning ? `${greeting} · ${t.homeBack}` : t.homeEyebrow}</Eyebrow>
      <h1 className="hero-title">{t.homeTitle}</h1>
      {props.returning ? null : <p className="hero-body">{t.homeBody}</p>}

      {(props.cards ?? []).map((card) => {
        if (card.kind === "wait") {
          return (
            <section
              key={card.wait.id}
              className="card card-context"
              aria-label={card.due ? t.waitDueTitle : t.waitPendingTitle}
            >
              <h2 className="card-label">{card.due ? t.waitDueTitle : t.waitPendingTitle}</h2>
              <p className="learn-body">{card.wait.note ? `“${card.wait.note}”` : ""}</p>
              <p className="muted">{card.due ? t.waitDueBody : t.waitPendingBody}</p>
              <ActionButton label={t.waitLookAgain} onClick={() => props.onWaitLookAgain?.(card.wait.id)} />
              <ActionButton
                label={t.waitLetGo}
                onClick={() => props.onWaitLetGo?.(card.wait.id)}
                variant="text"
              />
            </section>
          );
        }
        if (card.kind === "plan") {
          return (
            <section key={card.entryId} className="card card-context" aria-label={t.planFollowTitle}>
              <h2 className="card-label">{t.planFollowTitle}</h2>
              <p className="muted">{t.planFollowBody(card.date)}</p>
              <div className="action-row">
                <ActionButton label={t.planYes} onClick={() => props.onPlanFollow?.(card.entryId, true)} variant="secondary" />
                <ActionButton label={t.planNo} onClick={() => props.onPlanFollow?.(card.entryId, false)} variant="secondary" />
              </div>
              <ActionButton label={t.planNotYet} onClick={() => props.onPlanFollow?.(card.entryId, null)} variant="text" />
            </section>
          );
        }
        if (card.kind === "learn") {
          return (
            <section key="learn" className="card card-context" aria-label={t.homeLearnTitle}>
              <h2 className="card-label">{t.homeLearnTitle}</h2>
              <p className="learn-body">
                <strong>{card.lesson.title}</strong>
                <br />
                <span className="muted">{card.lesson.summary}</span>
              </p>
              <ActionButton label={t.learnRead} onClick={() => props.onOpenLesson?.(card.lesson.id)} variant="secondary" />
              <ActionButton label={t.notNow} onClick={() => props.onDismiss?.("learn")} variant="text" />
            </section>
          );
        }
        const isRules = card.kind === "rules";
        return (
          <section
            key={card.kind}
            className="card card-context"
            aria-label={isRules ? t.homeRulesNudgeTitle : t.homePatternsNudgeTitle}
          >
            <h2 className="card-label">{isRules ? t.homeRulesNudgeTitle : t.homePatternsNudgeTitle}</h2>
            <p className="muted">{isRules ? t.homeRulesNudgeBody : t.homePatternsNudgeBody}</p>
            <ActionButton
              label={isRules ? t.homeRulesNudgeButton : t.myPatterns}
              onClick={isRules ? props.onRules : props.onMirror}
            />
            <ActionButton label={t.notNow} onClick={() => props.onDismiss?.(card.kind)} variant="text" />
          </section>
        );
      })}

      <div className="stack">
        <ActionButton label={t.shareSomething} onClick={props.onShare} />
        <p className="hint">{t.shareHint}</p>
        <ActionButton label={t.thinkDecision} onClick={props.onDecision} variant="secondary" />
      </div>
      {props.returning && snap ? (
        <section className="snapshot" aria-label={t.snapshotTitle}>
          <div className="snapshot-item">
            <span className="snapshot-value">{snap.rules}</span>
            <span className="snapshot-label">{t.snapshotRules}</span>
          </div>
          <div className="snapshot-item">
            <span className="snapshot-value">{snap.decisions}</span>
            <span className="snapshot-label">{t.snapshotDecisions}</span>
          </div>
          <div className="snapshot-item">
            <span className="snapshot-value">{snap.lessons}</span>
            <span className="snapshot-label">{t.snapshotLessons}</span>
          </div>
        </section>
      ) : null}
      <div className="tile-grid">
        {tiles.map((tile) => (
          <button key={tile.label} type="button" className="tile" onClick={tile.onClick}>
            <span className="tile-icon">
              <Icon name={tile.icon} />
            </span>
            <span className="card-label">{tile.label}</span>
            <span className="tile-hint">{tile.hint}</span>
          </button>
        ))}
      </div>
    </ScreenBody>
  );
}
