// "Write your own plan." Ruko never writes it. The words stay on this phone; the backend only
// learns which parts exist (a reason, a horizon, a condition to reconsider), which is all it
// needs to tell a complete plan from a missing one, and to notice later if a decision strays.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { ChoiceList } from "../components/ChoiceList";
import { parseAmount } from "../components/ClarificationChoice";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import { RukoMessage } from "../components/RukoMessage";
import type { DecisionPlan, PlanHorizon } from "../types/api";

const MAX_WORDS = 280;
const HORIZONS: PlanHorizon[] = ["days", "weeks", "months", "years", "unsure"];

export interface PlanResult {
  /** The flags the backend learns. */
  plan: DecisionPlan;
  /** The user's words, kept on the device. */
  reason: string;
  reconsider: string;
  /** Present when they gave an amount range and want the plan kept for next time. */
  range: { min: number; max: number } | null;
  save: boolean;
}

interface Props {
  /** The amount being decided, if known (offered as the starting range). */
  amountHint?: number;
  /** A saved plan needs a known product class; without one the plan is for this decision only. */
  canSave: boolean;
  onSubmit: (result: PlanResult) => void;
  onBack: () => void;
}

export function PlanScreen({ amountHint, canSave, onSubmit, onBack }: Props) {
  const t = useCopy();
  const [reason, setReason] = useState("");
  const [reconsider, setReconsider] = useState("");
  const [horizon, setHorizon] = useState<PlanHorizon | null>(null);
  const [min, setMin] = useState(amountHint ? String(amountHint) : "");
  const [max, setMax] = useState(amountHint ? String(amountHint) : "");
  const [save, setSave] = useState(canSave);
  const [problem, setProblem] = useState<string | null>(null);

  function submit() {
    const hasWords = reason.trim() !== "" || reconsider.trim() !== "" || horizon !== null;
    if (!hasWords) return setProblem(t.planEmpty);
    const low = parseAmount(min);
    const high = parseAmount(max);
    const gaveRange = min.trim() !== "" || max.trim() !== "";
    if (gaveRange && (low === null || high === null || low > high)) return setProblem(t.planRangeInvalid);
    onSubmit({
      plan: {
        reason_given: reason.trim() !== "",
        horizon,
        reconsider_condition_given: reconsider.trim() !== "",
      },
      reason: reason.trim(),
      reconsider: reconsider.trim(),
      range: gaveRange && low !== null && high !== null ? { min: low, max: high } : null,
      save: save && canSave,
    });
  }

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton label={t.planSubmit} onClick={submit} />
          <ActionButton label={t.back} onClick={onBack} variant="text" />
          <ScreenFooter>{t.planBody}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.planEyebrow}</Eyebrow>
      <RukoMessage text={t.planTitle} />
      <label className="field">
        <span className="field-label">{t.planReason}</span>
        <textarea
          className="input textarea-small"
          maxLength={MAX_WORDS}
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            setProblem(null);
          }}
        />
      </label>
      <section className="field" aria-label={t.planHorizon}>
        <span className="field-label">{t.planHorizon}</span>
        <ChoiceList
          name={t.planHorizon}
          compact
          choices={HORIZONS.map((value) => ({ value, label: t.planHorizonOptions[value] }))}
          selected={horizon}
          onSelect={(value) => {
            setHorizon(value === horizon ? null : (value as PlanHorizon));
            setProblem(null);
          }}
        />
      </section>
      <label className="field">
        <span className="field-label">{t.planReconsider}</span>
        <textarea
          className="input textarea-small"
          maxLength={MAX_WORDS}
          value={reconsider}
          onChange={(e) => {
            setReconsider(e.target.value);
            setProblem(null);
          }}
        />
      </label>
      {canSave ? (
        <section className="card" aria-label={t.planRangeTitle}>
          <h2 className="card-label">{t.planRangeTitle}</h2>
          <div className="action-row">
            <label className="field">
              <span className="field-label">{t.planFrom}</span>
              <input
                className="input"
                inputMode="numeric"
                value={min}
                onChange={(e) => setMin(e.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">{t.planTo}</span>
              <input
                className="input"
                inputMode="numeric"
                value={max}
                onChange={(e) => setMax(e.target.value)}
              />
            </label>
          </div>
          <label className="toggle">
            <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} />
            <span>{t.planSave}</span>
          </label>
        </section>
      ) : null}
      {problem ? (
        <p className="field-error" role="alert">
          {problem}
        </p>
      ) : null}
    </ScreenBody>
  );
}
