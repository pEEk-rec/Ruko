// "My rules": the optional profile fields the backend already accepts (UserProfile).
// Saved on the device only, and sent with each analyze request.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody } from "../components/Layout";
import { RukoMessage } from "../components/RukoMessage";
import { loadProfile, saveProfile } from "../services/device";
import type { ExpenseBand, SavingsBand, UserProfile } from "../types/api";

const EXPENSE_BANDS: { value: ExpenseBand; label: string }[] = [
  { value: "lt_10k", label: "Under ₹10,000" },
  { value: "10k_25k", label: "₹10,000 – ₹25,000" },
  { value: "25k_50k", label: "₹25,000 – ₹50,000" },
  { value: "50k_1l", label: "₹50,000 – ₹1 lakh" },
  { value: "1l_2l", label: "₹1 – 2 lakh" },
  { value: "gt_2l", label: "Over ₹2 lakh" },
];

const SAVINGS_BANDS: { value: SavingsBand; label: string }[] = [
  { value: "lt_25k", label: "Under ₹25,000" },
  { value: "25k_1l", label: "₹25,000 – ₹1 lakh" },
  { value: "1l_3l", label: "₹1 – 3 lakh" },
  { value: "3l_10l", label: "₹3 – 10 lakh" },
  { value: "10l_25l", label: "₹10 – 25 lakh" },
  { value: "gt_25l", label: "Over ₹25 lakh" },
];

/** Parse an optional whole number within bounds; empty means "not set". */
function optionalNumber(raw: string, min: number, max: number): number | undefined {
  const value = Number(raw);
  return raw.trim() !== "" && Number.isInteger(value) && value >= min && value <= max
    ? value
    : undefined;
}

export function RulesScreen({ onBack }: { onBack: () => void }) {
  const t = useCopy();
  const [profile, setProfile] = useState<UserProfile>(() => loadProfile());
  const [status, setStatus] = useState<string | null>(null);
  const rules = profile.rules ?? {};

  function update(next: UserProfile) {
    setProfile(next);
    setStatus(null);
  }

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton
            label={t.save}
            onClick={() => setStatus(saveProfile(profile) ? t.saved : t.saveFailed)}
          />
          <ActionButton label={t.back} onClick={onBack} variant="text" />
          {status ? (
            <p className="screen-footer" role="status">
              {status}
            </p>
          ) : null}
        </>
      }
    >
      <Eyebrow>{t.rulesEyebrow}</Eyebrow>
      <RukoMessage text={t.rulesTitle} subtext={t.rulesBody} />
      <label className="field">
        <span className="field-label">{t.expenses}</span>
        <select
          className="input"
          value={profile.monthly_expenses_band ?? ""}
          onChange={(e) =>
            update({ ...profile, monthly_expenses_band: (e.target.value || undefined) as ExpenseBand })
          }
        >
          <option value="">{t.notSet}</option>
          {EXPENSE_BANDS.map((b) => (
            <option key={b.value} value={b.value}>
              {b.label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field-label">{t.savings}</span>
        <select
          className="input"
          value={profile.liquid_savings_band ?? ""}
          onChange={(e) =>
            update({ ...profile, liquid_savings_band: (e.target.value || undefined) as SavingsBand })
          }
        >
          <option value="">{t.notSet}</option>
          {SAVINGS_BANDS.map((b) => (
            <option key={b.value} value={b.value}>
              {b.label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field-label">{t.maxShare}</span>
        <input
          className="input"
          inputMode="numeric"
          placeholder={t.notSet}
          defaultValue={rules.max_share_of_savings_pct ?? ""}
          onChange={(e) =>
            update({
              ...profile,
              rules: { ...rules, max_share_of_savings_pct: optionalNumber(e.target.value, 1, 100) },
            })
          }
        />
      </label>
      <label className="field">
        <span className="field-label">{t.coolingRule}</span>
        <input
          className="input"
          inputMode="numeric"
          placeholder={t.notSet}
          defaultValue={rules.cooling_off_minutes ?? ""}
          onChange={(e) =>
            update({
              ...profile,
              rules: { ...rules, cooling_off_minutes: optionalNumber(e.target.value, 1, 10080) },
            })
          }
        />
      </label>
      <label className="toggle">
        <input
          type="checkbox"
          checked={rules.no_borrowed_money ?? false}
          onChange={(e) => update({ ...profile, rules: { ...rules, no_borrowed_money: e.target.checked } })}
        />
        <span>{t.noBorrowed}</span>
      </label>
    </ScreenBody>
  );
}
