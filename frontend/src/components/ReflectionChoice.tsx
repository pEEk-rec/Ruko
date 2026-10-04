// The optional reflection step. The choices and the free text stay on the device; nothing
// here is sent to the backend (there is no reflection contract in the API).

import { useState } from "react";
import { useCopy } from "../CopyContext";
import type { Reflection } from "../state/flow";
import { ActionButton } from "./ActionButton";
import { ChoiceList } from "./ChoiceList";
import { FlowSteps } from "./FlowSteps";
import { Eyebrow, ScreenBody, ScreenFooter } from "./Layout";
import { RukoMessage } from "./RukoMessage";

interface Props {
  onDone: (reflection: Reflection | null) => void;
  /** The choices to offer, already picked for this decision (see state/reflection.ts). */
  choices?: string[];
}

const MAX_NOTE_LENGTH = 280;

export function ReflectionChoice({ onDone, choices }: Props) {
  const t = useCopy();
  const [choice, setChoice] = useState<string | null>(null);
  const [text, setText] = useState("");

  const actions = (
    <>
      <ActionButton label={t.continue} onClick={() => onDone({ choice, text: text.trim() })} />
      <ActionButton label={t.reflectSkipButton} onClick={() => onDone(null)} variant="text" />
      <ScreenFooter>{t.reflectSkip}</ScreenFooter>
    </>
  );

  return (
    <ScreenBody actions={actions}>
      <FlowSteps step={2} />
      <Eyebrow>{t.reflectEyebrow}</Eyebrow>
      <RukoMessage text={t.reflectTitle} subtext={t.reflectBody} />
      <ChoiceList
        name={t.reflectTitle}
        choices={(choices ?? t.reflectChoices).map((label) => ({ value: label, label }))}
        selected={choice}
        onSelect={(value) => setChoice(value === choice ? null : value)}
      />
      <label className="field">
        <span className="field-label">{t.reflectOwnWords}</span>
        <textarea
          className="input textarea-small"
          maxLength={MAX_NOTE_LENGTH}
          placeholder={t.reflectPlaceholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </label>
    </ScreenBody>
  );
}
