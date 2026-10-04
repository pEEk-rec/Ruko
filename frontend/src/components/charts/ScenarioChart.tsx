// Picks the chart for a calculation by the structure the backend returned: a yearly series
// means a line chart (SIP and goal), a rupee loss per scenario means bars (consequence).
// This module is loaded lazily so the charts stay out of the first download.

import type { CalculationResponse } from "../../types/api";
import { BarChart } from "./BarChart";
import { LineChart } from "./LineChart";

export default function ScenarioChart({ calculation }: { calculation: CalculationResponse }) {
  const hasSeries = calculation.scenarios.some((s) => s.series.length > 1);
  if (hasSeries) return <LineChart scenarios={calculation.scenarios} />;
  const amount = calculation.inputs.amount_inr;
  return (
    <BarChart
      scenarios={calculation.scenarios}
      amountInr={typeof amount === "number" ? amount : undefined}
    />
  );
}
