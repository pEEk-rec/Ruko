// "Listen": reads Ruko's own text aloud. Uses Ruko's voice when available, falls back to the
// phone's own voice for the same on-screen text, and says which one it used.

import { useEffect, useRef, useState } from "react";
import { useCopy, useLocale } from "../CopyContext";
import { listen, stopListening, type ListenOutcome, type ListenSource } from "../services/listen";
import { ActionButton } from "./ActionButton";

interface Props {
  /** Template references from a response (`speak[]`), or one lesson ID. */
  source: ListenSource;
  /** The same content as shown on screen, read by the phone's voice if Ruko's is unavailable. */
  text: string;
}

type Phase = "idle" | "loading" | "playing";

export function ListenButton({ source, text }: Props) {
  const t = useCopy();
  const locale = useLocale();
  const [phase, setPhase] = useState<Phase>("idle");
  const [note, setNote] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      stopListening();
    };
  }, []);

  async function start() {
    setNote(null);
    setPhase("loading");
    const outcome: ListenOutcome = await listen(locale, source, text);
    if (!mounted.current) return;
    if (outcome === "browser_voice") setNote(t.listenBrowserVoice);
    if (outcome === "unavailable") setNote(t.listenUnavailable);
    setPhase(outcome === "unavailable" ? "idle" : "playing");
  }

  function stop() {
    stopListening();
    setPhase("idle");
  }

  return (
    <div className="stack">
      {phase === "playing" ? (
        <ActionButton label={t.listenStop} onClick={stop} variant="secondary" />
      ) : (
        <ActionButton
          label={phase === "loading" ? t.listenLoading : t.listen}
          onClick={() => void start()}
          variant="secondary"
          disabled={phase === "loading"}
        />
      )}
      {note ? (
        <p className="hint" role="status">
          {note}
        </p>
      ) : null}
    </div>
  );
}
