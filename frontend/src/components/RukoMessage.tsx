import { Words } from "./Terms";

interface Props {
  text: string;
  subtext?: string | null;
}

/** Ruko's main line for a screen (a backend-rendered headline), with optional subtext. */
export function RukoMessage({ text, subtext }: Props) {
  return (
    <div className="ruko-message">
      <h1 className="ruko-headline">
        <Words text={text} />
      </h1>
      {subtext ? <p className="ruko-subtext">
          <Words text={subtext} />
        </p> : null}
    </div>
  );
}
