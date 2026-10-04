// The live calculator. Change any number and the result updates: each change asks the backend
// (`POST /v1/calculate`) and shows what comes back, so the arithmetic is the same tested code
// as everywhere else and the browser computes nothing. It starts empty (or from the numbers of
// a result the person is adjusting) and shows an example only once the required numbers exist.
// Always at least two scenarios, always "an illustration, not a prediction".

import { useEffect, useMemo, useRef, useState } from "react";
import { useCopy, useLocale } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { CalculationCard } from "../components/CalculationCard";
import { LearnNext } from "../components/LearnNext";
import { TermsProvider } from "../components/Terms";
import { ChoiceList } from "../components/ChoiceList";
import { parseAmount } from "../components/ClarificationChoice";
import { NoticeCard, ScreenBody } from "../components/Layout";
import { RukoMessage } from "../components/RukoMessage";
import { AppError, calculate, CancelledError } from "../services/api";
import { loadJournal, loadProfile } from "../services/device";
import { profileForRequest } from "../services/profile";
import { formatInr } from "../utils/format";
import type {
  CalculationInputs,
  CalculationResponse,
  CalculatorTool,
} from "../types/api";
import { Lessons } from "./ResultScreen";

const DEBOUNCE_MS = 350;
const MAX_CHIPS = 4;
const TOOLS: CalculatorTool[] = ["sip", "goal", "inflation", "consequence", "costs"];

type NumberField = Exclude<
  keyof CalculationInputs,
  "tool" | "rates_pct" | "drops_pct"
>;

/** Which fields each calculator needs, and which of them can be left empty. */
const FIELDS: Record<CalculatorTool, { name: NumberField; optional?: boolean }[]> = {
  sip: [{ name: "monthly_inr" }, { name: "months" }],
  goal: [{ name: "goal_inr" }, { name: "months" }, { name: "already_saved_inr", optional: true }],
  inflation: [{ name: "amount_inr" }, { name: "years" }],
  consequence: [{ name: "amount_inr" }, { name: "leverage", optional: true }],
  costs: [{ name: "trade_value_inr" }, { name: "trades_per_month" }],
  tax: [],
};
const HAS_RATES: CalculatorTool[] = ["sip", "goal", "inflation"];

const AMOUNT_FIELDS: NumberField[] = ["monthly_inr", "goal_inr", "amount_inr", "trade_value_inr"];
const MONTH_CHIPS = [12, 36, 60, 120];
const YEAR_CHIPS = [1, 3, 5, 10];

interface Quick {
  label: string;
  value: number;
}

/**
 * Starting points from the person's own data on this phone: the amount of their last decision, a
 * goal they protected, the top of a plan they wrote. Offered as chips; nothing is filled in until
 * they tap one.
 */
function personalAmounts(field: NumberField, t: ReturnType<typeof useCopy>): Quick[] {
  if (!AMOUNT_FIELDS.includes(field)) return [];
  const found: Quick[] = [];
  const last = loadJournal().find((r) => r.entry.amount_inr)?.entry.amount_inr;
  if (last) found.push({ label: t.calcMineLast(formatInr(last)), value: last });
  const profile = loadProfile();
  const goal = (profile.rules?.protected_goals ?? []).find((g) => g.amount_inr)?.amount_inr;
  if (goal && field !== "monthly_inr") found.push({ label: t.calcMineGoal(formatInr(goal)), value: goal });
  const plans = profile.plans ?? [];
  const plan = plans[plans.length - 1];
  if (plan) found.push({ label: t.calcMinePlan(formatInr(plan.amount_max_inr)), value: plan.amount_max_inr });
  return found.filter((q, i, all) => all.findIndex((o) => o.value === q.value) === i).slice(0, 3);
}

function quickChips(field: NumberField, t: ReturnType<typeof useCopy>): Quick[] {
  if (field === "months") return MONTH_CHIPS.map((m) => ({ label: t.calcYears(m / 12), value: m }));
  if (field === "years") return YEAR_CHIPS.map((y) => ({ label: t.calcYears(y), value: y }));
  return personalAmounts(field, t);
}

function parseDecimal(raw: string): number | null {
  const cleaned = raw.replace(/[₹,\s]/g, "");
  if (!/^\d+(\.\d+)?$/.test(cleaned)) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

function initialText(seed: CalculationInputs | null): Record<string, string> {
  const text: Record<string, string> = {};
  if (!seed) return text;
  for (const [key, value] of Object.entries(seed)) {
    if (typeof value === "number") text[key] = String(value);
  }
  return text;
}

export function CalculatorScreen({
  seed,
  onBack,
  onOpenLesson,
  onAskTerm,
  onTool,
}: {
  seed: CalculationInputs | null;
  onBack: () => void;
  onOpenLesson?: (lessonId: string) => void;
  onAskTerm?: (title: string) => void;
  onTool?: (tool: CalculatorTool) => void;
}) {
  const t = useCopy();
  const locale = useLocale();
  const [tool, setTool] = useState<CalculatorTool | null>(seed?.tool ?? null);
  const [text, setText] = useState<Record<string, string>>(() => initialText(seed));
  const [rates, setRates] = useState<number[]>(seed?.rates_pct ?? []);
  const [drops, setDrops] = useState<number[]>(seed?.drops_pct ?? []);
  const [chipText, setChipText] = useState("");
  const [result, setResult] = useState<CalculationResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const latest = useRef<AbortController | null>(null);

  /** The request for the current fields, or null while a required number is missing. */
  const inputs = useMemo((): CalculationInputs | null => {
    if (!tool) return null;
    const built: Record<string, unknown> = { tool };
    for (const { name, optional } of FIELDS[tool]) {
      const raw = text[name] ?? "";
      const value = name === "leverage" ? parseDecimal(raw) : parseAmount(raw);
      if (value === null) {
        if (optional && raw.trim() === "") continue;
        return null;
      }
      built[name] = value;
    }
    if (HAS_RATES.includes(tool) && rates.length > 0) built.rates_pct = rates;
    if (tool === "consequence" && drops.length > 0) built.drops_pct = drops;
    return built as CalculationInputs;
  }, [tool, text, rates, drops]);

  useEffect(() => {
    latest.current?.abort();
    if (!inputs) {
      setResult(null);
      setPending(false);
      setProblem(null);
      return;
    }
    const controller = new AbortController();
    latest.current = controller;
    setPending(true);
    const timer = window.setTimeout(() => {
      calculate({ locale, inputs, profile: profileForRequest() }, controller.signal)
        .then((response) => {
          if (controller.signal.aborted) return; // a newer request replaced this one
          if (response.kind === "calculation") {
            setResult(response);
            setProblem(null);
          } else {
            setResult(null);
          }
          setPending(false);
        })
        .catch((err: unknown) => {
          if (err instanceof CancelledError || controller.signal.aborted) return;
          setProblem(err instanceof AppError ? t.errors[err.kind] : t.errors.server_error);
          setPending(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // `t` changes only with the language, which also changes `locale` above.
  }, [inputs, locale]); // eslint-disable-line react-hooks/exhaustive-deps

  const chips = tool === "consequence" ? drops : rates;
  const setChips = tool === "consequence" ? setDrops : setRates;
  const showChips = tool !== null && (HAS_RATES.includes(tool) || tool === "consequence");

  function addChip() {
    const value = parseDecimal(chipText);
    if (value === null || chips.length >= MAX_CHIPS || chips.includes(value)) return;
    setChips([...chips, value]);
    setChipText("");
  }

  return (
    <ScreenBody actions={<ActionButton label={t.back} onClick={onBack} variant="text" />}>
      <RukoMessage text={t.calcToolTitle} subtext={t.calcToolBody} />
      <ChoiceList
        name={t.calcToolTitle}
        compact
        choices={TOOLS.map((value) => ({ value, label: t.calcTools[value as Exclude<CalculatorTool, "tax">] }))}
        selected={tool}
        onSelect={(value) => {
          setTool(value as CalculatorTool);
          onTool?.(value as CalculatorTool);
        }}
      />
      {tool ? (
        <section className="card stack" aria-label={t.calcTools[tool as Exclude<CalculatorTool, "tax">]}>
          {FIELDS[tool].map(({ name }) => (
            <label key={name} className="field">
              <span className="field-label">{t.calcFields[name as keyof typeof t.calcFields]}</span>
              <input
                className="input"
                inputMode={name === "leverage" ? "decimal" : "numeric"}
                autoComplete="off"
                value={text[name] ?? ""}
                onChange={(e) => setText((v) => ({ ...v, [name]: e.target.value }))}
              />
              {quickChips(name, t).length > 0 ? (
                <span className="quick-chips">
                  {quickChips(name, t).map((q) => (
                    <button
                      key={q.label}
                      type="button"
                      className={`quick-chip ${text[name] === String(q.value) ? "quick-chip-on" : ""}`}
                      onClick={() => setText((v) => ({ ...v, [name]: String(q.value) }))}
                    >
                      {q.label}
                    </button>
                  ))}
                </span>
              ) : null}
            </label>
          ))}
          {showChips ? (
            <div className="field">
              <span className="field-label">{tool === "consequence" ? t.calcDrops : t.calcRates}</span>
              <div className="choice-list choice-list-compact">
                {chips.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className="choice choice-selected"
                    aria-label={t.calcRemove(String(value))}
                    onClick={() => setChips(chips.filter((v) => v !== value))}
                  >
                    {value}%
                  </button>
                ))}
              </div>
              {chips.length < MAX_CHIPS ? (
                <div className="action-row">
                  <input
                    className="input"
                    inputMode="decimal"
                    autoComplete="off"
                    aria-label={tool === "consequence" ? t.calcDrops : t.calcRates}
                    placeholder={t.calcRatePlaceholder}
                    value={chipText}
                    onChange={(e) => setChipText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addChip()}
                  />
                  <ActionButton label={t.calcAddRate} onClick={addChip} variant="secondary" />
                </div>
              ) : null}
              {tool !== "consequence" ? <span className="hint">{t.calcRateNote}</span> : null}
            </div>
          ) : null}
        </section>
      ) : null}
      {pending ? (
        <p className="muted" role="status">
          {t.calcUpdating}
        </p>
      ) : null}
      {problem ? (
        <div role="alert">
          <NoticeCard>{problem}</NoticeCard>
        </div>
      ) : null}
      {tool && !inputs && !pending ? <p className="muted">{t.calcFillIn}</p> : null}
      {result ? (
        <TermsProvider terms={result.terms} onAsk={onAskTerm}>
          <CalculationCard calculation={result} />
          <Lessons lessons={result.lessons ?? []} onTool={(next) => setTool(next)} />
          <LearnNext topic={result.learn_next} onOpen={onOpenLesson} />
        </TermsProvider>
      ) : null}
    </ScreenBody>
  );
}
