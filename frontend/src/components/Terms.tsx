// The shared word layer. Every screen explains its own words the same way: a glossary word in
// any of Ruko's texts is a button, and tapping it opens a small pop-up above it with a short,
// curated explanation. The words and explanations come from the backend (`terms` on a
// response); this only finds them in the text and shows them. It never explains anything itself.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useCopy } from "../CopyContext";
import { splitByTerms, type TextPart } from "../utils/terms";
import type { TermHit } from "../types/api";

interface TermsValue {
  terms: TermHit[];
  /** The id of the word whose pop-up is open (one at a time). */
  open: string | null;
  setOpen: (key: string | null) => void;
  /** Ask for the full explanation of a term (by its title). */
  onAsk?: (title: string) => void;
}

/** Space kept clear at the screen edge, and under the app header, when placing a pop-up. */
const POP_MARGIN = 8;
const TOP_CLEARANCE = 72;

const EMPTY: TermsValue = { terms: [], open: null, setOpen: () => undefined };
const TermsContext = createContext<TermsValue>(EMPTY);

/** Gives every text below it the same words to make tappable. */
export function TermsProvider({
  terms,
  onAsk,
  children,
}: {
  terms: TermHit[] | undefined;
  onAsk?: (title: string) => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (open === null) return;
    const close = (event: Event) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.(".term-wrap")) return;
      setOpen(null);
    };
    const escape = (event: KeyboardEvent) => event.key === "Escape" && setOpen(null);
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const value = useMemo(() => ({ terms: terms ?? [], open, setOpen, onAsk }), [terms, open, onAsk]);
  return <TermsContext.Provider value={value}>{children}</TermsContext.Provider>;
}

function Parts({ parts, text }: { parts: TextPart[]; text: string }) {
  const owner = useId();
  if (parts.length === 1 && parts[0].term === null) return <>{text}</>;
  return (
    <>
      {parts.map((part, index) =>
        part.term ? (
          <Term key={index} id={`${owner}:${index}`} term={part.term} shown={part.text} />
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </>
  );
}

/** Plain text with its glossary words tappable. Renders the text unchanged if none apply. */
export function Words({ text }: { text: string }) {
  const { terms } = useContext(TermsContext);
  const parts = useMemo(() => splitByTerms(text, terms), [text, terms]);
  return <Parts parts={parts} text={text} />;
}

/**
 * A lesson body: paragraphs separated by a blank line. Each word is tappable once in the whole
 * body (not again in every paragraph), so a long lesson does not turn into a field of links.
 */
export function Paragraphs({ text, className = "learn-body" }: { text: string; className?: string }) {
  const { terms } = useContext(TermsContext);
  const paragraphs = useMemo(() => {
    const tapped = new Set<string>();
    return text.split(/\n{2,}/).map((paragraph) => {
      const parts = splitByTerms(paragraph, terms, tapped);
      parts.forEach((part) => part.term && tapped.add(part.term.id));
      return { paragraph, parts };
    });
  }, [text, terms]);
  return (
    <>
      {paragraphs.map(({ paragraph, parts }, index) => (
        <p key={index} className={className}>
          <Parts parts={parts} text={paragraph} />
        </p>
      ))}
    </>
  );
}

function Term({ id, term, shown }: { id: string; term: TermHit; shown: string }) {
  const t = useCopy();
  const { open, setOpen, onAsk } = useContext(TermsContext);
  const isOpen = open === id;
  const button = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLSpanElement>(null);
  const [shift, setShift] = useState(0);
  const [below, setBelow] = useState(false);

  // Keep the pop-up on screen: slide it sideways if it would run off an edge, and open it
  // below the word when there is no room above (under the header or off the top).
  useLayoutEffect(() => {
    if (!isOpen || !pop.current) return;
    const rect = pop.current.getBoundingClientRect();
    const room = document.documentElement.clientWidth;
    if (rect.width === 0) return;
    if (rect.right > room - POP_MARGIN) setShift(room - POP_MARGIN - rect.right);
    else if (rect.left < POP_MARGIN) setShift(POP_MARGIN - rect.left);
    if (rect.top < TOP_CLEARANCE) setBelow(true);
  }, [isOpen]);

  const close = useCallback(() => {
    setOpen(null);
    button.current?.focus();
  }, [setOpen]);

  return (
    <span className="term-wrap">
      <button
        ref={button}
        type="button"
        className="term"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        onClick={() => {
          setShift(0);
          setBelow(false);
          setOpen(isOpen ? null : id);
        }}
      >
        {shown}
      </button>
      {isOpen ? (
        <span
          ref={pop}
          role="dialog"
          aria-label={term.title}
          className={below ? "term-pop term-pop-below" : "term-pop"}
          style={shift ? { transform: `translateX(${shift}px)` } : undefined}
          onKeyDown={(event) => event.key === "Escape" && close()}
        >
          <strong className="term-pop-title">{term.title}</strong>
          <span className="term-pop-brief">{term.brief}</span>
          <span className="term-pop-actions">
            {onAsk ? (
              <button type="button" className="term-pop-more" onClick={() => onAsk(term.title)}>
                {t.termMore}
              </button>
            ) : null}
            <button type="button" className="term-pop-close" onClick={close}>
              {t.termClose}
            </button>
          </span>
        </span>
      ) : null}
    </span>
  );
}
