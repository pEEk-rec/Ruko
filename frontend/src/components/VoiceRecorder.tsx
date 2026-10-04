// Voice input control: record, then stop and send. It enforces the backend's limits (30 s,
// 5 MB), explains every failure calmly, and always leaves the text path open. Audio is held in
// memory only and handed to `onRecorded` once.

import { useEffect, useRef, useState } from "react";
import { useCopy } from "../CopyContext";
import { VOICE_LIMITS } from "../config/defaults";
import {
  canRecord,
  RecordingError,
  startRecording,
  type ActiveRecording,
  type Recorded,
  type RecordingProblem,
} from "../services/recorder";
import { ActionButton } from "./ActionButton";

interface Props {
  onRecorded: (recorded: Recorded) => void;
}

type Phase = "idle" | "starting" | "recording" | "finishing";

export function VoiceRecorder({ onRecorded }: Props) {
  const t = useCopy();
  const [phase, setPhase] = useState<Phase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [problem, setProblem] = useState<RecordingProblem | null>(null);
  const active = useRef<ActiveRecording | null>(null);
  const timer = useRef<number | null>(null);

  function clearTimer() {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
  }

  useEffect(
    () => () => {
      clearTimer();
      active.current?.cancel();
    },
    [],
  );

  async function begin() {
    setProblem(null);
    setPhase("starting");
    try {
      active.current = await startRecording();
    } catch (err) {
      setProblem(err instanceof RecordingError ? err.kind : "failed");
      setPhase("idle");
      return;
    }
    setSeconds(0);
    setPhase("recording");
    timer.current = window.setInterval(() => {
      setSeconds((current) => {
        const next = current + 1;
        if (next >= VOICE_LIMITS.maxSeconds) void finish();
        return next;
      });
    }, 1000);
  }

  async function finish() {
    const recording = active.current;
    if (!recording) return;
    active.current = null;
    clearTimer();
    setPhase("finishing");
    try {
      onRecorded(await recording.stop());
      setPhase("idle");
    } catch (err) {
      setProblem(err instanceof RecordingError ? err.kind : "failed");
      setPhase("idle");
    }
  }

  function cancel() {
    clearTimer();
    active.current?.cancel();
    active.current = null;
    setPhase("idle");
  }

  if (!canRecord() && problem === null) {
    return <p className="hint">{t.voiceProblems.unsupported}</p>;
  }

  return (
    <div className="stack">
      {phase === "recording" ? (
        <>
          <p className="muted" role="status">
            {t.voiceRecording(seconds, VOICE_LIMITS.maxSeconds)}
          </p>
          <ActionButton label={t.voiceStop} onClick={() => void finish()} />
          <ActionButton label={t.voiceCancel} onClick={cancel} variant="text" />
        </>
      ) : phase === "finishing" ? (
        <p className="muted" role="status">
          {t.voiceSending}
        </p>
      ) : (
        <ActionButton
          label={t.voiceStart}
          onClick={() => void begin()}
          variant="secondary"
          disabled={phase === "starting"}
        />
      )}
      {problem ? (
        <p className="field-error" role="alert">
          {t.voiceProblems[problem]}
        </p>
      ) : null}
      <p className="hint">{t.voiceTextAlways}</p>
    </div>
  );
}
