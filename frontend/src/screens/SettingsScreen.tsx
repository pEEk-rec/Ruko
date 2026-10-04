// Settings: language, text size, how much Ruko speaks up, and the anonymised summary download.
// Each change is applied and saved at once; the screen stays open. Tapping the version line
// five times reveals the demo tools (the fictional broker), which are not on the home screen.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody } from "../components/Layout";
import { LanguagePicker, StylePicker } from "../components/Pickers";
import { RukoMessage } from "../components/RukoMessage";
import type { Settings } from "../config/defaults";
import { downloadSummary } from "../services/summary";

const DEMO_TAPS = 5;

export function SettingsScreen({
  settings,
  onChange,
  onBack,
}: {
  settings: Settings;
  onChange: (settings: Settings) => void;
  onBack: () => void;
}) {
  const t = useCopy();
  const [taps, setTaps] = useState(0);
  const [exported, setExported] = useState<boolean | null>(null);

  return (
    <ScreenBody actions={<ActionButton label={t.back} onClick={onBack} />}>
      <Eyebrow>{t.settingsEyebrow}</Eyebrow>
      <RukoMessage text={t.settingsTitle} />
      <section className="card" aria-label={t.languageLabel}>
        <h2 className="card-label">{t.languageLabel}</h2>
        <LanguagePicker value={settings.locale} onChange={(locale) => onChange({ ...settings, locale })} />
      </section>
      <label className="toggle">
        <input
          type="checkbox"
          checked={settings.largeText}
          onChange={(e) => onChange({ ...settings, largeText: e.target.checked })}
        />
        <span>{t.largeText}</span>
      </label>
      <section className="card" aria-label={t.styleLabel}>
        <h2 className="card-label">{t.styleLabel}</h2>
        <StylePicker value={settings.style} onChange={(style) => onChange({ ...settings, style })} />
      </section>
      <section className="card" aria-label={t.exportTitle}>
        <h2 className="card-label">{t.exportTitle}</h2>
        <p className="learn-body">{t.exportBody}</p>
        <ActionButton
          label={t.exportButton}
          onClick={() => setExported(downloadSummary())}
          variant="secondary"
        />
        {exported ? (
          <p className="meta-line" role="status">
            {t.exportDone}
          </p>
        ) : null}
      </section>
      {taps >= DEMO_TAPS ? (
        <section className="card" aria-label={t.demoMenu}>
          <h2 className="card-label">{t.demoMenu}</h2>
          <a className="contact-link" href="/demo/broker">
            {t.demoBroker}
          </a>
        </section>
      ) : null}
      <button type="button" className="btn btn-text" onClick={() => setTaps(taps + 1)}>
        {t.versionLine}
      </button>
    </ScreenBody>
  );
}
