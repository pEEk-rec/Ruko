// Language and intervention-style pickers, shared by the first-run flow and Settings.

import { useCopy } from "../CopyContext";
import { LOCALES, type InterventionStyle } from "../config/defaults";
import { hasDraftStrings } from "../copy";
import type { Locale } from "../types/api";
import { ChoiceList } from "./ChoiceList";

export function LanguagePicker({ value, onChange }: { value: Locale; onChange: (l: Locale) => void }) {
  const t = useCopy();
  return (
    <>
      <ChoiceList
        name={t.languageLabel}
        choices={LOCALES.map((l) => ({ value: l.value, label: l.label }))}
        selected={value}
        onSelect={(v) => onChange(v as Locale)}
      />
      {hasDraftStrings(value) && value !== "en" ? <p className="hint">{t.languageDraft}</p> : null}
    </>
  );
}

export function StylePicker({
  value,
  onChange,
}: {
  value: InterventionStyle;
  onChange: (s: InterventionStyle) => void;
}) {
  const t = useCopy();
  return (
    <>
      <ChoiceList
        name={t.styleLabel}
        choices={[
          { value: "balanced", label: t.styleBalanced },
          { value: "quiet", label: t.styleQuiet },
        ]}
        selected={value}
        onSelect={(v) => onChange(v as InterventionStyle)}
      />
      <p className="hint">{t.styleNote}</p>
    </>
  );
}
