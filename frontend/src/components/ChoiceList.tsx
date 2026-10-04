interface Choice {
  value: string;
  label: string;
}

interface Props {
  choices: Choice[];
  selected?: string | null;
  onSelect: (value: string) => void;
  name: string;
}

/** Large tappable choices (clarification, reflection, decision). One tap selects. */
export function ChoiceList({ choices, selected, onSelect, name }: Props) {
  return (
    <div className="choice-list" role="radiogroup" aria-label={name}>
      {choices.map((choice) => (
        <button
          key={choice.value}
          type="button"
          role="radio"
          aria-checked={selected === choice.value}
          className={`choice ${selected === choice.value ? "choice-selected" : ""}`}
          onClick={() => onSelect(choice.value)}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}
