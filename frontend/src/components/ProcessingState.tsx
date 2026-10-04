import { useCopy } from "../CopyContext";

/** Shown while the backend reads the shared content. */
export function ProcessingState() {
  const t = useCopy();
  return (
    <div className="processing" role="status" aria-live="polite">
      <span className="dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <p className="processing-title">{t.processingTitle}</p>
      <p className="muted">{t.processingBody}</p>
    </div>
  );
}
