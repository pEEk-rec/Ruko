import { useCopy } from "../CopyContext";
import type { RawInput } from "../types/api";

interface Props {
  input: RawInput;
}

/** What the user shared, shown back to them as a quoted message (or the screenshot). */
export function SharedContent({ input }: Props) {
  const t = useCopy();
  return (
    <figure className="shared-content">
      <figcaption className="shared-label">{t.messageYouReceived}</figcaption>
      {input.type === "image" ? (
        <img className="shared-image" src={`data:image/*;base64,${input.content}`} alt={t.aScreenshot} />
      ) : (
        <blockquote className="shared-quote">{input.content}</blockquote>
      )}
    </figure>
  );
}

/** A short line the user wrote, shown as their own bubble. */
export function UserMessage({ text }: { text: string }) {
  return <p className="user-message">{text}</p>;
}
