// The plans the person has written, with their own words (kept on this phone) and a way to
// remove each one. A plan is how the backend can tell later if a decision strays from it.

import { useCopy } from "../CopyContext";
import { loadMemory, removePlanNote } from "../services/memory";
import type { PlannedDecision } from "../types/api";
import { formatInr } from "../utils/format";
import { ActionButton } from "./ActionButton";

export function PlansList({
  plans,
  onRemove,
}: {
  plans: PlannedDecision[];
  onRemove: (id: string) => void;
}) {
  const t = useCopy();
  const notes = loadMemory().planNotes;
  return (
    <section className="card" aria-label={t.plansTitle}>
      <h2 className="card-label">{t.plansTitle}</h2>
      {plans.length === 0 ? <p className="muted">{t.plansEmpty}</p> : null}
      <ul className="plain-list">
        {plans.map((plan) => {
          const name = (t.productNames as Record<string, string>)[plan.product_class] ?? "";
          return (
            <li key={plan.id}>
              <strong>{name}</strong>{" "}
              <span>
                {t.planRange(formatInr(plan.amount_min_inr), formatInr(plan.amount_max_inr))}
              </span>
              {plan.horizon ? <span> · {t.planHorizonOptions[plan.horizon]}</span> : null}
              {notes[plan.id]?.reason ? <p className="muted">{notes[plan.id].reason}</p> : null}
              <ActionButton
                label={t.planRemove}
                variant="text"
                onClick={() => {
                  removePlanNote(plan.id);
                  onRemove(plan.id);
                }}
              />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
