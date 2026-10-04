// A clearly fictional broker's order screen, to show how a real broker could embed Ruko.
// Before an order it calls POST /v1/order-intent with a product class, an amount band, a
// funding flag, a leverage flag and the device profile. It sends no instrument identity and
// no user ID. L0 passes silently; L1 to L3 show an inline sheet, and "Place order anyway" is
// always there. Every outcome goes to the device journal. Invented names only.

import { useState } from "react";
import { ActionButton } from "../components/ActionButton";
import { parseAmount } from "../components/ClarificationChoice";
import { orderIntent } from "../services/api";
import { addJournalRecord } from "../services/device";
import { profileForRequest } from "../services/profile";
import type { InterventionLevel, JournalAction, OrderIntentResponse, ProductClass } from "../types/api";
import { LEVEL_HEADLINES, reasonLabel } from "./labels";
import { brokerRecord } from "./record";

type DemoProduct = Extract<ProductClass, "cash_equity" | "derivative" | "mutual_fund">;

const INSTRUMENTS: { value: DemoProduct; label: string }[] = [
  { value: "cash_equity", label: "Stock A" },
  { value: "derivative", label: "Index option B" },
  { value: "mutual_fund", label: "Fund C" },
];

type Phase = "form" | "checking" | "sheet" | "placed" | "cancelled" | "unreachable";

export function BrokerApp() {
  const [product, setProduct] = useState<DemoProduct>("cash_equity");
  const [amountText, setAmountText] = useState("10000");
  const [leveraged, setLeveraged] = useState(false);
  const [borrowed, setBorrowed] = useState(false);
  const [phase, setPhase] = useState<Phase>("form");
  const [problem, setProblem] = useState<string | null>(null);
  const [intent, setIntent] = useState<OrderIntentResponse | null>(null);

  const amount = parseAmount(amountText);

  function record(level: InterventionLevel, reasons: string[], action: JournalAction) {
    if (amount !== null) addJournalRecord(brokerRecord(product, amount, level, reasons, action));
  }

  async function placeOrder() {
    if (amount === null) {
      setProblem("Enter a whole rupee amount, like 10000.");
      return;
    }
    setProblem(null);
    setPhase("checking");
    try {
      const result = await orderIntent({
        product_class: product,
        amount_band: { min_inr: amount, max_inr: amount },
        borrowed_funds: borrowed,
        leveraged,
        profile: profileForRequest(),
      });
      setIntent(result);
      if (result.level === "L0") {
        record("L0", [], "went_ahead");
        setPhase("placed");
      } else {
        setPhase("sheet");
      }
    } catch {
      setPhase("unreachable");
    }
  }

  function finish(action: JournalAction) {
    if (intent) record(intent.level, intent.reason_codes, action);
    setPhase(action === "went_ahead" ? "placed" : "cancelled");
  }

  const banner = <header className="broker-demo-banner">Demo – not a real broker</header>;

  if (phase === "placed" || phase === "cancelled" || phase === "unreachable") {
    return (
      <div className="broker-demo">
        {banner}
        <section className="card" role="status">
          <h1 className="ruko-headline">
            {phase === "placed"
              ? "Demo order placed."
              : phase === "cancelled"
                ? "Order cancelled."
                : "Ruko could not be reached."}
          </h1>
          <p className="muted">
            {phase === "placed"
              ? "No real order exists. The outcome was noted in your Ruko journal on this phone."
              : phase === "cancelled"
                ? "Nothing was placed. The outcome was noted in your Ruko journal on this phone."
                : "Nothing was placed. Check your connection and try again."}
          </p>
        </section>
        <ActionButton
          label="Start a new demo order"
          onClick={() => {
            setIntent(null);
            setPhase("form");
          }}
        />
      </div>
    );
  }

  return (
    <div className="broker-demo">
      {banner}
      <h1 className="ruko-headline">Fictional TradeApp</h1>
      <section className="card stack" aria-label="Order">
        <label className="field">
          <span className="field-label">Instrument</span>
          <select
            className="input"
            value={product}
            onChange={(e) => setProduct(e.target.value as DemoProduct)}
          >
            {INSTRUMENTS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Amount (₹)</span>
          <input
            className="input"
            inputMode="numeric"
            autoComplete="off"
            value={amountText}
            onChange={(e) => setAmountText(e.target.value)}
          />
        </label>
        <label className="toggle">
          <input type="checkbox" checked={leveraged} onChange={(e) => setLeveraged(e.target.checked)} />
          <span>Use leverage or margin</span>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={borrowed} onChange={(e) => setBorrowed(e.target.checked)} />
          <span>I am using borrowed money</span>
        </label>
        {problem ? (
          <p className="field-error" role="alert">
            {problem}
          </p>
        ) : null}
        <ActionButton
          label={phase === "checking" ? "Checking…" : "Place order"}
          onClick={() => void placeOrder()}
          disabled={phase === "checking"}
        />
      </section>

      {phase === "sheet" && intent && intent.level !== "L0" ? (
        <div className="broker-demo-sheet" role="dialog" aria-label="Before you place this order">
          <h2 className="ruko-headline">{LEVEL_HEADLINES[intent.level]}</h2>
          <ul className="plain-list">
            {intent.reason_codes.map((code) => (
              <li key={code}>{reasonLabel(code)}</li>
            ))}
          </ul>
          <div className="stack">
            <ActionButton label="Place order anyway" onClick={() => finish("went_ahead")} />
            <ActionButton label="Cancel the order" onClick={() => finish("dropped")} variant="secondary" />
            <p className="screen-footer">The choice is yours. Ruko does not block orders.</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
