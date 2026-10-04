// The user's own message, shown back to them with the words behind each signal marked. It only
// exists on this phone: the text comes from what they just shared, and the marks come from the
// quotes the backend returned. Voice notes and screenshots have no text here, so it is hidden.

import { createContext, useContext, useState } from "react";
import { useCopy } from "../CopyContext";
import type { SignalView } from "../types/api";
import { highlight } from "../utils/highlight";

/** The text of what the user just shared (null for voice notes and screenshots). */
export const MessageContext = createContext<string | null>(null);

export function useMessageText(): string | null {
  return useContext(MessageContext);
}

export function QuotedMessage({ signals }: { signals: SignalView[] }) {
  const t = useCopy();
  const text = useMessageText();
  const [open, setOpen] = useState(false);
  const quotes = signals.map((s) => s.quote).filter((q): q is string => !!q);
  if (!text || quotes.length === 0) return null;
  return (
    <section className="card" aria-label={t.yourMessageTitle}>
      <button
        type="button"
        className="btn btn-text"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open ? t.hideMessage : t.showMessage}
      </button>
      {open ? (
        <p className="shared-quote" data-testid="quoted-message">
          {highlight(text, quotes).map((segment, i) =>
            segment.marked ? (
              <mark key={i} className="noticed">
                {segment.text}
              </mark>
            ) : (
              <span key={i}>{segment.text}</span>
            ),
          )}
        </p>
      ) : null}
    </section>
  );
}
