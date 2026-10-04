// The user's own rules and context, as form fields. Used by "My rules" and by the first-run
// flow. Every field is optional and maps one-to-one to the backend's UserProfile
// (src/ruko/models/profile.py), with the same bounds, so a saved profile is never rejected.

import { useCopy } from "../CopyContext";
import type {
  AgeBand,
  Experience,
  ExpenseBand,
  ProductClass,
  SavingsBand,
  UserProfile,
  UserRules,
} from "../types/api";

const EXPERIENCE_CLASSES = ["cash_equity", "derivative", "ipo", "mutual_fund", "crypto"] as const;
const AGE_BANDS: AgeBand[] = ["lt_30", "30_40", "40_50", "50_60", "gt_60"];

const EXPENSE_BANDS: { value: ExpenseBand; label: string }[] = [
  { value: "lt_10k", label: "< ₹10,000" },
  { value: "10k_25k", label: "₹10,000 – ₹25,000" },
  { value: "25k_50k", label: "₹25,000 – ₹50,000" },
  { value: "50k_1l", label: "₹50,000 – ₹1,00,000" },
  { value: "1l_2l", label: "₹1,00,000 – ₹2,00,000" },
  { value: "gt_2l", label: "> ₹2,00,000" },
];

const SAVINGS_BANDS: { value: SavingsBand; label: string }[] = [
  { value: "lt_25k", label: "< ₹25,000" },
  { value: "25k_1l", label: "₹25,000 – ₹1,00,000" },
  { value: "1l_3l", label: "₹1,00,000 – ₹3,00,000" },
  { value: "3l_10l", label: "₹3,00,000 – ₹10,00,000" },
  { value: "10l_25l", label: "₹10,00,000 – ₹25,00,000" },
  { value: "gt_25l", label: "> ₹25,00,000" },
];

/** Bounds from models/profile.py. */
export const PROFILE_BOUNDS = {
  maxSharePct: [1, 100],
  maxAmountInr: [1, 1_000_000_000],
  emergencyBufferMonths: [0, 36],
  protectedGoalInr: [0, 1_000_000_000],
  coolingOffMinutes: [0, 1440],
} as const;

/** The device ID of the single protected goal this form edits. */
export const PROTECTED_GOAL_ID = "goal-1";

/** Parse an optional whole number within bounds; empty or invalid means "not set". */
export function optionalNumber(raw: string, [min, max]: readonly [number, number]): number | undefined {
  const cleaned = raw.replace(/[₹,\s]/g, "");
  const value = Number(cleaned);
  return cleaned !== "" && Number.isInteger(value) && value >= min && value <= max
    ? value
    : undefined;
}

/** Drop unset rule fields so the saved profile only holds what the user wrote. */
function cleanRules(rules: UserRules): UserRules {
  return Object.fromEntries(
    Object.entries(rules).filter(([, v]) => v !== undefined && !(Array.isArray(v) && v.length === 0)),
  ) as UserRules;
}

interface Props {
  profile: UserProfile;
  onChange: (profile: UserProfile) => void;
}

export function ProfileFields({ profile, onChange }: Props) {
  const t = useCopy();
  const rules = profile.rules ?? {};
  const goal = rules.protected_goals?.find((g) => g.id === PROTECTED_GOAL_ID);

  const setRules = (next: UserRules) => {
    const cleaned = cleanRules({ ...rules, ...next });
    const { rules: _dropped, ...rest } = profile;
    onChange(Object.keys(cleaned).length > 0 ? { ...rest, rules: cleaned } : rest);
  };
  const setTop = (next: Partial<UserProfile>) => {
    const merged = { ...profile, ...next };
    (Object.keys(next) as (keyof UserProfile)[]).forEach((k) => {
      if (merged[k] === undefined) delete merged[k];
    });
    onChange(merged);
  };

  const setExperience = (product: ProductClass, level: Experience | undefined) => {
    const experience = { ...(profile.experience ?? {}) };
    if (level) experience[product] = level;
    else delete experience[product];
    const { experience: _old, ...rest } = profile;
    onChange(Object.keys(experience).length > 0 ? { ...rest, experience } : rest);
  };

  return (
    <>
      <label className="field">
        <span className="field-label">{t.expenses}</span>
        <select
          className="input"
          value={profile.monthly_expenses_band ?? ""}
          onChange={(e) =>
            setTop({ monthly_expenses_band: (e.target.value || undefined) as ExpenseBand | undefined })
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
            setTop({ liquid_savings_band: (e.target.value || undefined) as SavingsBand | undefined })
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
      <NumberField
        label={t.emergencyBuffer}
        initial={profile.emergency_buffer_months}
        onValue={(v) => setTop({ emergency_buffer_months: optionalNumber(v, PROFILE_BOUNDS.emergencyBufferMonths) })}
      />
      <NumberField
        label={t.maxShare}
        initial={rules.max_share_of_savings_pct}
        onValue={(v) => setRules({ max_share_of_savings_pct: optionalNumber(v, PROFILE_BOUNDS.maxSharePct) })}
      />
      <NumberField
        label={t.maxAmount}
        initial={rules.max_amount_inr}
        onValue={(v) => setRules({ max_amount_inr: optionalNumber(v, PROFILE_BOUNDS.maxAmountInr) })}
      />
      <NumberField
        label={t.protectedGoal}
        initial={goal?.amount_inr}
        onValue={(v) => {
          const amount = optionalNumber(v, PROFILE_BOUNDS.protectedGoalInr);
          const others = (rules.protected_goals ?? []).filter((g) => g.id !== PROTECTED_GOAL_ID);
          setRules({
            protected_goals:
              amount === undefined ? others : [...others, { id: PROTECTED_GOAL_ID, amount_inr: amount }],
          });
        }}
      />
      <NumberField
        label={t.coolingRule}
        initial={rules.cooling_off_minutes}
        onValue={(v) => setRules({ cooling_off_minutes: optionalNumber(v, PROFILE_BOUNDS.coolingOffMinutes) })}
      />
      <label className="field">
        <span className="field-label">{t.ageBandLabel}</span>
        <select
          className="input"
          value={profile.age_band ?? ""}
          onChange={(e) => setTop({ age_band: (e.target.value || undefined) as AgeBand | undefined })}
        >
          <option value="">{t.notSet}</option>
          {AGE_BANDS.map((band) => (
            <option key={band} value={band}>
              {t.ageBands[band]}
            </option>
          ))}
        </select>
      </label>
      <section className="field" aria-label={t.profileExperience}>
        <span className="field-label">{t.profileExperience}</span>
        {EXPERIENCE_CLASSES.map((product) => (
          <label key={product} className="field">
            <span className="field-label">{t.productNames[product]}</span>
            <select
              className="input"
              value={profile.experience?.[product] ?? ""}
              onChange={(e) => setExperience(product, (e.target.value || undefined) as Experience | undefined)}
            >
              <option value="">{t.notSet}</option>
              {(["none", "some", "regular"] as Experience[]).map((level) => (
                <option key={level} value={level}>
                  {t.experienceOptions[level]}
                </option>
              ))}
            </select>
          </label>
        ))}
      </section>
      <label className="toggle">
        <input
          type="checkbox"
          checked={rules.no_borrowed_money ?? false}
          onChange={(e) => setRules({ no_borrowed_money: e.target.checked || undefined })}
        />
        <span>{t.noBorrowed}</span>
      </label>
    </>
  );
}

function NumberField({
  label,
  initial,
  onValue,
}: {
  label: string;
  initial: number | undefined;
  onValue: (raw: string) => void;
}) {
  const t = useCopy();
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input
        className="input"
        inputMode="numeric"
        autoComplete="off"
        placeholder={t.notSet}
        defaultValue={initial ?? ""}
        onChange={(e) => onValue(e.target.value)}
      />
    </label>
  );
}
