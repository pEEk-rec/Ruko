// First run: language, the user's own rules, and how much Ruko speaks up. Every step can be
// skipped with "Skip, use safe defaults" (config/defaults.ts): no rules, no amounts, balanced.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import { LanguagePicker, StylePicker } from "../components/Pickers";
import { ProfileFields } from "../components/ProfileFields";
import { RukoMessage } from "../components/RukoMessage";
import { DEFAULT_PROFILE, type Settings } from "../config/defaults";
import type { UserProfile } from "../types/api";

type Step = "language" | "rules" | "style";
const STEPS: Step[] = ["language", "rules", "style"];

interface Props {
  settings: Settings;
  /** Language changes apply at once, so the next steps read in the chosen language. */
  onSettings: (settings: Settings) => void;
  /** Finish: `profile` is what the user wrote, or the safe defaults if they skipped. */
  onDone: (profile: UserProfile, settings: Settings) => void;
}

export function OnboardingScreen({ settings, onSettings, onDone }: Props) {
  const t = useCopy();
  const [step, setStep] = useState<Step>("language");
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const index = STEPS.indexOf(step);
  const last = index === STEPS.length - 1;

  const skip = () => onDone(DEFAULT_PROFILE, { ...settings, style: "balanced", onboarded: true });
  const next = () =>
    last ? onDone(profile, { ...settings, onboarded: true }) : setStep(STEPS[index + 1]);

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton label={last ? t.onboardStart : t.onboardNext} onClick={next} />
          <ActionButton label={t.onboardSkip} onClick={skip} variant="text" />
          <ScreenFooter>{t.onboardSafeDefaults}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>
        {t.onboardEyebrow} · {index + 1}/{STEPS.length}
      </Eyebrow>
      {step === "language" ? (
        <>
          <RukoMessage text={t.onboardLanguageTitle} subtext={t.onboardLanguageBody} />
          <LanguagePicker
            value={settings.locale}
            onChange={(locale) => onSettings({ ...settings, locale })}
          />
        </>
      ) : null}
      {step === "rules" ? (
        <>
          <RukoMessage text={t.onboardRulesTitle} subtext={t.onboardRulesBody} />
          <ProfileFields profile={profile} onChange={setProfile} />
        </>
      ) : null}
      {step === "style" ? (
        <>
          <RukoMessage text={t.onboardStyleTitle} />
          <StylePicker value={settings.style} onChange={(style) => onSettings({ ...settings, style })} />
        </>
      ) : null}
    </ScreenBody>
  );
}
