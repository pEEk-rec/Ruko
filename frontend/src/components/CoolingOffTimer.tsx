// The cooling-off wait for an L3 pause, using the user's own minutes (or the backend's
// suggestion). It is never a lock: the wait can be skipped, and what the user did is recorded
// (finished or skipped) for their own journal.

import { useEffect, useRef, useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "./ActionButton";

interface Props {
  minutes: number;
  /** Called once: `skipped` is false if the wait ran to the end, true if the user skipped it. */
  onFinish: (skipped: boolean) => void;
}

/** Format seconds as m:ss. */
export function clock(totalSeconds: number): string {
  const safe = Math.max(0, Math.ceil(totalSeconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

export function CoolingOffTimer({ minutes, onFinish }: Props) {
  const t = useCopy();
  const [remaining, setRemaining] = useState(minutes * 60);
  const [outcome, setOutcome] = useState<"running" | "done" | "skipped">("running");
  const reported = useRef(false);
  const onFinishRef = useRef(onFinish);
  onFinishRef.current = onFinish;

  function finish(skipped: boolean) {
    if (reported.current) return;
    reported.current = true;
    setOutcome(skipped ? "skipped" : "done");
    onFinishRef.current(skipped);
  }

  useEffect(() => {
    if (outcome !== "running") return;
    const endsAt = Date.now() + remaining * 1000;
    const timer = window.setInterval(() => {
      const left = Math.round((endsAt - Date.now()) / 1000);
      setRemaining(Math.max(0, left));
      if (left <= 0) {
        window.clearInterval(timer);
        if (!reported.current) {
          reported.current = true;
          setOutcome("done");
          onFinishRef.current(false);
        }
      }
    }, 1000);
    return () => window.clearInterval(timer);
    // The interval is created once per run; `remaining` is read only when it starts.
  }, [outcome]);

  return (
    <section className="card card-context" aria-label={t.timerTitle}>
      <h2 className="card-label">{t.timerTitle}</h2>
      <p className="learn-body">{t.timerBody(minutes)}</p>
      {outcome === "running" ? (
        <>
          <p className="ruko-headline" role="timer" aria-live="off">
            {t.timerRemaining(clock(remaining))}
          </p>
          <ActionButton label={t.timerSkip} onClick={() => finish(true)} variant="text" />
        </>
      ) : (
        <p className="muted" role="status">
          {outcome === "done" ? t.timerDone : t.timerSkipped}
        </p>
      )}
    </section>
  );
}
