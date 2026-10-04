// A plain SVG line chart: money put in (one dashed line) and the value under each assumption
// (one line per scenario, labelled at its end, so colour is never the only cue). Positions are
// scaled from the backend's numbers; nothing is calculated or extrapolated here.

import { useCopy } from "../../CopyContext";
import type { Scenario } from "../../types/api";
import { formatInr } from "../../utils/format";

const WIDTH = 320;
const HEIGHT = 190;
const PAD = { left: 8, right: 8, top: 14, bottom: 22 };

interface Props {
  scenarios: Scenario[];
}

export function LineChart({ scenarios }: Props) {
  const t = useCopy();
  const drawn = scenarios.filter((s) => s.series.length > 1);
  if (drawn.length === 0) return null;
  const maxMonth = Math.max(...drawn.flatMap((s) => s.series.map((p) => p.month)));
  const maxValue = Math.max(...drawn.flatMap((s) => s.series.map((p) => p.value_inr)));
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const x = (month: number) => PAD.left + (maxMonth === 0 ? 0 : (month / maxMonth) * innerW);
  const y = (value: number) => PAD.top + innerH - (maxValue === 0 ? 0 : (value / maxValue) * innerH);
  const path = (points: { month: number; v: number }[]) =>
    points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.month).toFixed(1)} ${y(p.v).toFixed(1)}`).join(" ");
  const invested = drawn[0].series.map((p) => ({ month: p.month, v: p.invested_inr }));

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={t.chartAltSeries}
        preserveAspectRatio="xMidYMid meet"
      >
        <line className="chart-axis" x1={PAD.left} y1={HEIGHT - PAD.bottom} x2={WIDTH - PAD.right} y2={HEIGHT - PAD.bottom} />
        <path className="chart-line chart-line-invested" d={path(invested)} />
        {drawn.map((s, i) => (
          <g key={i}>
            <path
              className={`chart-line chart-line-${i % 3}`}
              d={path(s.series.map((p) => ({ month: p.month, v: p.value_inr })))}
            />
            <text className="chart-label" x={WIDTH - PAD.right} y={y(s.series[s.series.length - 1].value_inr) - 4} textAnchor="end">
              {s.assumption_pct !== null ? `${s.assumption_pct}%` : ""}
            </text>
          </g>
        ))}
        <text className="chart-label" x={PAD.left} y={PAD.top - 3}>
          {formatInr(maxValue)}
        </text>
      </svg>
      <figcaption className="chart-legend">
        <span className="legend-item">
          <i className="legend-swatch chart-line-invested" aria-hidden="true" /> {t.chartPutIn}
        </span>
        {drawn.map((s, i) => (
          <span key={i} className="legend-item">
            <i className={`legend-swatch chart-line-${i % 3}`} aria-hidden="true" /> {s.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
