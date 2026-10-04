import { useCopy } from "../CopyContext";
import type { JournalRecord } from "../services/device";

/** One journal note: what was considered, why, and what the user decided. */
export function JournalSummary({ record }: { record: JournalRecord }) {
  const t = useCopy();
  const why = [record.notes.reflection_choice, record.notes.reflection_text]
    .filter(Boolean)
    .join(" · ");
  return (
    <section className="card journal-card">
      <h2 className="card-label">{t.whatIConsidered}</h2>
      <p className="journal-text">{record.notes.shared_excerpt || t.aScreenshot}</p>
      <hr />
      <h2 className="card-label">{t.why}</h2>
      <p className="journal-text">{why || t.notStated}</p>
      <hr />
      <h2 className="card-label">{t.myDecision}</h2>
      <p className="journal-text">{t.actionPast[record.entry.action]}</p>
      <p className="meta-line">{record.entry.date}</p>
    </section>
  );
}
