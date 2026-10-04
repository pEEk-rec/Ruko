// A plain SVG bar chart for the consequence calculator: one bar per illustrative fall showing
// the rupee loss, with a marker at the money the user put in, so a bar that passes the marker
// shows a loss larger than the amount put in. Bar lengths are scaled from the backend's numbers.

import { useCopy } from "../../CopyContext";
import type { Scenario } from "../../types/api";
import { formatInr } from "../../utils/format";

const WIDTH = 320;
const ROW = 44;
const PAD = { left: 8, right: 8, top: 22 };

interface Props {
  scenarios: Scenario[];
  /** The money the user put in (echoed back in the response inputs). */
  amountInr?: number;
}

export function BarChart({ scenarios, amountInr }: Props) {
  const t = useCopy();
  const rows = scenarios.filter((s) => typeof s.values.loss_inr === "number");
  if (rows.length === 0) return null;
  const max = Math.max(...rows.map((s) => s.values.loss_inr), amountInr ?? 0);
  const innerW = WIDTH - PAD.left - PAD.right;
  const w = (value: number) => (max === 0 ? 0 : (Math.max(0, value) / max) * innerW);
  const height = PAD.top + rows.length * ROW + 6;
  const markerX = amountInr !== undefined ? PAD.left + w(amountInr) : null;

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={t.chartAltBars} preserveAspectRatio="xMidYMid meet">
        {rows.map((s, i) => {
          const top = PAD.top + i * ROW;
          return (
            <g key={i}>
              <text className="chart-label" x={PAD.left} y={top + 10}>
                {s.label}
              </text>
              <rect className="chart-bar" x={PAD.left} y={top + 15} width={w(s.values.loss_inr)} height={14} rx={3} />
              <text className="chart-label" x={PAD.left + w(s.values.loss_inr) + 4} y={top + 27}>
                {formatInr(s.values.loss_inr)}
              </text>
            </g>
          );
        })}
        {markerX !== null ? (
          <g>
            <line className="chart-marker" x1={markerX} y1={PAD.top - 6} x2={markerX} y2={height - 4} />
            <text className="chart-label" x={markerX} y={PAD.top - 9} textAnchor="middle">
              {t.chartPutIn}: {formatInr(amountInr as number)}
            </text>
          </g>
        ) : null}
      </svg>
    </figure>
  );
}
