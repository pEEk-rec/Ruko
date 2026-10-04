import { useCopy } from "../CopyContext";
import type { Certainty, SignalView } from "../types/api";

const CERTAINTY_LABELS: Record<Certainty, string> = {
  possible: "Possible",
  likely: "Likely",
  unclear: "Unclear",
};

/** Certainty label for a signal. Shown as text, never as colour alone. */
export function ConfidenceBadge({ certainty, label }: { certainty: Certainty; label?: string | null }) {
  return <span className={`badge badge-${certainty}`}>{label || CERTAINTY_LABELS[certainty]}</span>;
}

/**
 * The explanation without its certainty label. Uses the backend's `reason_text` (any
 * locale); older responses only have `text`, where the exact English prefix is removed.
 */
export function signalBody(signal: SignalView): string {
  if (signal.reason_text) return signal.reason_text;
  const prefix = `${CERTAINTY_LABELS[signal.certainty]}: `;
  return signal.text.startsWith(prefix) ? signal.text.slice(prefix.length) : signal.text;
}

/** "What I see": each backend signal with its certainty. Renders nothing if empty. */
export function SignalCard({ signals }: { signals: SignalView[] }) {
  const t = useCopy();
  if (signals.length === 0) return null;
  return (
    <section className="card" aria-label={t.whatISee}>
      <h2 className="card-label">{t.whatISee}</h2>
      <ul className="signal-list">
        {signals.map((signal, index) => (
          <li key={`${signal.code}-${index}`} className="signal-row">
            <span className="signal-text">{signalBody(signal)}</span>
            <ConfidenceBadge certainty={signal.certainty} label={signal.certainty_label} />
          </li>
        ))}
      </ul>
    </section>
  );
}
