import { useCopy } from "../CopyContext";

interface Props {
  numbers: string[];
  rules: string[];
}

/** "Your context": the user's own rules and numbers, as rendered by the backend. */
export function PersonalContextCard({ numbers, rules }: Props) {
  const t = useCopy();
  if (numbers.length === 0 && rules.length === 0) return null;
  return (
    <section className="card card-context" aria-label={t.yourContext}>
      <h2 className="card-label">{t.yourContext}</h2>
      <ul className="plain-list">
        {rules.map((line, i) => (
          <li key={`r${i}`} className="context-rule">
            {line}
          </li>
        ))}
        {numbers.map((line, i) => (
          <li key={`n${i}`}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
