interface Choice {
  value: string;
  label: string;
  /** A small note beside the label, for example "Last time" or "Matches the message". */
  tag?: string | null;
}

interface Props {
  choices: Choice[];
  selected?: string | null;
  onSelect: (value: string) => void;
  name: string;
  /** Lay the choices out side by side and wrap (short labels), instead of one per line. */
  compact?: boolean;
}

/** Large tappable choices (clarification, reflection, decision). One tap selects. */
export function ChoiceList({ choices, selected, onSelect, name, compact = false }: Props) {
  return (
    <div
      className={`choice-list ${compact ? "choice-list-compact" : ""}`}
      role="radiogroup"
      aria-label={name}
    >
      {choices.map((choice) => (
        <button
          key={choice.value}
          type="button"
          role="radio"
          aria-checked={selected === choice.value}
          aria-label={choice.label}
          aria-description={choice.tag ?? undefined}
          className={`choice ${selected === choice.value ? "choice-selected" : ""}`}
          onClick={() => onSelect(choice.value)}
        >
          {choice.label}
          {choice.tag ? <span className="choice-tag">{choice.tag}</span> : null}
        </button>
      ))}
    </div>
  );
}
