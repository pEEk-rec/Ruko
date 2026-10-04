// "Your money, big": the one picture that stops someone. It shows the backend's exposure figures
// for this decision (amount, share of savings, months of expenses, savings left, and for leveraged
// products what a move against the position means in rupees). Every number is the backend's; the
// app only formats it and scales bars to it. Nothing here is advice or a forecast.

import { useCopy } from "../CopyContext";
import type { ExposureNumbers, NumberRange } from "../types/api";
import { formatInr } from "../utils/format";

/** One decimal for small values (0.5 months), whole numbers otherwise. */
function show(value: number): string {
  return value < 10 ? String(Math.round(value * 10) / 10) : String(Math.round(value));
}

function approx(range: NumberRange, exact: boolean, about: string): string {
  return exact ? show(range.typical) : `${about} ${show(range.typical)}`;
}

export function hasMoneyHero(exposure: ExposureNumbers | undefined | null): boolean {
  return !!exposure?.amount_inr && (!!exposure.share_of_savings_pct || !!exposure.months_of_expenses);
}

export function MoneyHero({ exposure }: { exposure: ExposureNumbers }) {
  const t = useCopy();
  if (!exposure.amount_inr) return null;
  const exact = exposure.basis === "exact";
  const share = exposure.share_of_savings_pct;
  const months = exposure.months_of_expenses;
  const left = exposure.remaining_savings_inr;
  const fill = share ? Math.min(100, share.typical) : 0;
  const rangeLeft = share ? Math.min(100, share.low) : 0;
  const rangeWidth = share ? Math.max(0, Math.min(100, share.high) - rangeLeft) : 0;
  return (
    <section className="money-hero" aria-label={t.moneyThisDecision}>
      <p className="money-label">{t.moneyThisDecision}</p>
      <p className="money-amount">{formatInr(exposure.amount_inr)}</p>
      <div className="money-stats">
        {share ? (
          <div className="money-stat">
            <span className="money-stat-value">{approx(share, exact, "≈")}%</span>
            <span className="money-stat-label">{t.moneyOfSavings}</span>
          </div>
        ) : null}
        {months ? (
          <div className="money-stat">
            <span className="money-stat-value">{approx(months, exact, "≈")}</span>
            <span className="money-stat-label">{t.moneyMonths}</span>
          </div>
        ) : null}
      </div>
      {share ? (
        <div className="savings-bar-wrap">
          <div
            className="savings-bar"
            role="img"
            aria-label={`${approx(share, exact, t.moneyAbout)}% ${t.moneyOfSavings}`}
          >
            {!exact && rangeWidth > 0 ? (
              <span className="savings-bar-range" style={{ left: `${rangeLeft}%`, width: `${rangeWidth}%` }} />
            ) : null}
            <span className="savings-bar-fill" style={{ width: `${Math.max(fill, 1.5)}%` }} />
          </div>
          <p className="savings-bar-caption">
            <span>{t.moneyYourSavings}</span>
            {left ? <span>{t.moneyLeft(formatInr(left.typical), !exact)}</span> : null}
          </p>
        </div>
      ) : null}
      {exposure.adverse_moves.length > 0 ? <AdverseMoves exposure={exposure} /> : null}
    </section>
  );
}

/** For leveraged products: what a move against the position means, next to the money put in. */
function AdverseMoves({ exposure }: { exposure: ExposureNumbers }) {
  const t = useCopy();
  const put = exposure.amount_inr ?? 1;
  const widest = Math.max(put, ...exposure.adverse_moves.map((m) => m.loss_inr));
  return (
    <div className="moves" aria-label={t.movesTitle}>
      <p className="money-label">{t.movesTitle}</p>
      {exposure.adverse_moves.map((move) => (
        <div key={move.move_pct} className="move-row">
          <span className="move-label">{t.moveLine(show(move.move_pct))}</span>
          <span className="move-track">
            <span className="move-fill" style={{ width: `${(move.loss_inr / widest) * 100}%` }} />
            <span className="move-put" style={{ left: `${(put / widest) * 100}%` }} />
          </span>
          <span className={`move-value ${move.loss_inr > put ? "move-over" : ""}`}>
            −{formatInr(move.loss_inr)}
          </span>
        </div>
      ))}
      <p className="meta-line">{t.movesNote}</p>
    </div>
  );
}
