interface Props {
  text: string;
  subtext?: string | null;
}

/** Ruko's main line for a screen (a backend-rendered headline), with optional subtext. */
export function RukoMessage({ text, subtext }: Props) {
  return (
    <div className="ruko-message">
      <h1 className="ruko-headline">{text}</h1>
      {subtext ? <p className="ruko-subtext">{subtext}</p> : null}
    </div>
  );
}
