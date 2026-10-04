// See -> Think -> Decide: where the person is in a decision, shown the same way on each step so the
// flow never feels like a maze. It only shows position; it never forces the next step.

import { useCopy } from "../CopyContext";

export type FlowStep = 1 | 2 | 3;

export function FlowSteps({ step }: { step: FlowStep }) {
  const t = useCopy();
  const labels = [t.stepSee, t.stepThink, t.stepDecide];
  return (
    <ol className="flow-steps" aria-label={t.stepsLabel}>
      {labels.map((label, index) => {
        const n = (index + 1) as FlowStep;
        const state = n < step ? "done" : n === step ? "current" : "next";
        return (
          <li key={label} className={`flow-step flow-step-${state}`} aria-current={n === step ? "step" : undefined}>
            <span className="flow-step-dot" aria-hidden="true" />
            {label}
          </li>
        );
      })}
    </ol>
  );
}
