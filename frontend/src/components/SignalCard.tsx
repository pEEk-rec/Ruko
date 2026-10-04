import { useCopy } from "../CopyContext";
import type { Certainty, SignalView } from "../types/api";

const CERTAINTY_LABELS: Record<Certainty, string> = {
  possible: "Possible",
  likely: "Likely",
  unclear: "Unclear",
};

/** Certainty label for a signal. Shown as text, never as colour alone. */
export function ConfidenceBadge({ certainty }: { certainty: Certainty }) {
  return <span className={`badge badge-${certainty}`}>{CERTAINTY_LABELS[certainty]}</span>;
}

/**
 * Remove the backend's leading "Likely: " style prefix, which repeats the badge.
 * Only the exact rendered certainty word is removed; anything else is shown as sent.
 */
export function withoutCertaintyPrefix(text: string, certainty: Certainty): string {
  const prefix = `${CERTAINTY_LABELS[certainty]}: `;
  return text.startsWith(prefix) ? text.slice(prefix.length) : text;
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
            <span className="signal-text">{withoutCertaintyPrefix(signal.text, signal.certainty)}</span>
            <ConfidenceBadge certainty={signal.certainty} />
          </li>
        ))}
      </ul>
    </section>
  );
}
