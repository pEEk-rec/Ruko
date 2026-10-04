// The calculate path: headline, the scenarios side by side (rendered lines), a simple chart,
// the explanation and the assumptions, always labelled "an illustration, not a prediction".
// Every number and sentence comes from the backend; nothing is computed here.

import { lazy, Suspense } from "react";
import { useCopy } from "../CopyContext";
import type { CalculationResponse } from "../types/api";
import { Eyebrow } from "./Layout";
import { ListenButton } from "./ListenButton";
import { RukoMessage } from "./RukoMessage";

const ScenarioChart = lazy(() => import("./charts/ScenarioChart"));

export function CalculationCard({ calculation }: { calculation: CalculationResponse }) {
  const t = useCopy();
  const readAloud = [
    calculation.headline,
    ...calculation.scenarios.flatMap((s) => [s.label, ...s.lines]),
    calculation.explanation,
  ].join(" ");
  return (
    <>
      <Eyebrow>{t.calcEyebrow}</Eyebrow>
      <RukoMessage text={calculation.headline} />
      <p className="notice" role="note">
        {t.calcIllustration}
      </p>
      {calculation.scenarios.map((scenario, i) => (
        <section key={i} className="card" aria-label={scenario.label}>
          <h2 className="card-label">{scenario.label}</h2>
          <ul className="plain-list">
            {scenario.lines.map((line, j) => (
              <li key={j}>{line}</li>
            ))}
          </ul>
        </section>
      ))}
      <Suspense fallback={null}>
        <ScenarioChart calculation={calculation} />
      </Suspense>
      <p className="muted">{calculation.explanation}</p>
      <section className="card card-context" aria-label={t.calcAssumptions}>
        <h2 className="card-label">{t.calcAssumptions}</h2>
        <ul className="plain-list">
          {calculation.assumptions.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </section>
      <ListenButton source={{ items: calculation.speak }} text={readAloud} />
    </>
  );
}
