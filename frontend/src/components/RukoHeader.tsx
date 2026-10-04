import { useCopy } from "../CopyContext";

interface Props {
  onHome?: () => void;
}

/** App bar: Ruko mark and the privacy reminder. */
export function RukoHeader({ onHome }: Props) {
  const t = useCopy();
  return (
    <header className="ruko-header">
      <button type="button" className="ruko-mark" onClick={onHome} aria-label={t.home}>
        <span className="ruko-logo" aria-hidden="true">
          r
        </span>
        <span className="ruko-name">ruko</span>
      </button>
      <span className="privacy-tag">{t.privateByDesign}</span>
    </header>
  );
}
