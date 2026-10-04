import { useCopy } from "../CopyContext";
import type { ExplanationCard, SourceRef } from "../types/api";

/** One just-in-time explanation card with its sources and verification status. */
export function LearnCard({ card }: { card: ExplanationCard }) {
  const t = useCopy();
  return (
    <article className="card learn-card">
      <h2 className="learn-title">{card.title}</h2>
      <p className="learn-body">{card.body}</p>
      <SourceList sources={card.sources} />
      <p className="meta-line">
        {card.as_of ? t.asOf(card.as_of) : null}
        {card.verified_by_human ? null : <span> · {t.unverified}</span>}
      </p>
    </article>
  );
}

/** Citations. Links open the official site in the browser; Ruko never fetches them. */
export function SourceList({ sources }: { sources: SourceRef[] }) {
  const t = useCopy();
  if (sources.length === 0) return null;
  return (
    <ul className="source-list">
      {sources.map((s, i) => (
        <li key={i}>
          {t.source}:{" "}
          {s.source_url ? (
            <a href={s.source_url} target="_blank" rel="noopener noreferrer">
              {s.source_title}
            </a>
          ) : (
            s.source_title
          )}
        </li>
      ))}
    </ul>
  );
}
