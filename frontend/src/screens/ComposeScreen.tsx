// Paste or screenshot input. Only what the user chooses to share is sent.

import { useRef, useState } from "react";
import { useCopy } from "../CopyContext";
import { IMAGE_TYPES, MAX_IMAGE_BYTES } from "../share/readSharedContent";
import type { Copy } from "../copy";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import { VoiceRecorder } from "../components/VoiceRecorder";
import type { Recorded } from "../services/recorder";
import type { EntryMode } from "../state/flow";
import type { RawInput } from "../types/api";

interface Props {
  entry: EntryMode;
  initial: RawInput | null;
  onSubmit: (input: RawInput) => void;
  onSubmitVoice: (recorded: Recorded) => void;
  onBack: () => void;
}

const EYEBROW: Record<EntryMode, (t: Copy) => string> = {
  share: (t) => t.composeEyebrow,
  decision: (t) => t.composeDecisionEyebrow,
};
const LABEL: Record<EntryMode, (t: Copy) => string> = {
  share: (t) => t.composeLabel,
  decision: (t) => t.composeDecisionLabel,
};

const MAX_TEXT = 8000;
const URL_ONLY = /^https?:\/\/\S+$/i;

/** Read a file as base64 without the data-URL prefix. */
function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function ComposeScreen({ entry, initial, onSubmit, onSubmitVoice, onBack }: Props) {
  const t = useCopy();
  const [text, setText] = useState(initial?.type !== "image" ? initial?.content ?? "" : "");
  const [image, setImage] = useState<string | null>(initial?.type === "image" ? initial.content : null);
  const [problem, setProblem] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function chooseFile(file: File | undefined) {
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type) || file.size > MAX_IMAGE_BYTES) {
      setProblem(t.errors.unsupported_input);
      return;
    }
    try {
      setImage(await readBase64(file));
      setProblem(null);
    } catch {
      setProblem(t.errors.unsupported_input);
    }
  }

  function submit() {
    const trimmed = text.trim();
    if (image) return onSubmit({ type: "image", content: image });
    if (!trimmed) return setProblem(t.composeEmpty);
    onSubmit({ type: URL_ONLY.test(trimmed) ? "link" : "text", content: trimmed });
  }

  const actions = (
    <>
      <ActionButton label={t.composeSubmit} onClick={submit} />
      <ActionButton label={t.back} onClick={onBack} variant="text" />
      <ScreenFooter>{t.composeFooter}</ScreenFooter>
    </>
  );

  return (
    <ScreenBody actions={actions}>
      <Eyebrow>{EYEBROW[entry](t)}</Eyebrow>
      <label className="field">
        <span className="field-label-large">{LABEL[entry](t)}</span>
        <textarea
          className="input textarea"
          maxLength={MAX_TEXT}
          placeholder={t.composePlaceholder}
          value={text}
          disabled={image !== null}
          onChange={(e) => {
            setText(e.target.value);
            setProblem(null);
          }}
        />
      </label>
      <input
        ref={fileRef}
        type="file"
        accept={IMAGE_TYPES.join(",")}
        hidden
        onChange={(e) => void chooseFile(e.target.files?.[0])}
      />
      {image ? (
        <div className="screenshot-chosen">
          <span>{t.composeScreenshotChosen}</span>
          <ActionButton label={t.composeRemoveScreenshot} onClick={() => setImage(null)} variant="text" />
        </div>
      ) : (
        <ActionButton
          label={t.composeAddScreenshot}
          onClick={() => fileRef.current?.click()}
          variant="secondary"
        />
      )}
      {problem ? (
        <p className="field-error" role="alert">
          {problem}
        </p>
      ) : null}
      {!image ? (
        <section className="card">
          <VoiceRecorder onRecorded={onSubmitVoice} />
        </section>
      ) : null}
    </ScreenBody>
  );
}
