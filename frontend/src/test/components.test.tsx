// Rendering tests against real backend responses captured in src/fixtures/.

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClarificationChoice, parseAmount } from "../components/ClarificationChoice";
import { PauseCard } from "../components/PauseCard";
import { signalBody } from "../components/SignalCard";
import { ResultScreen } from "../screens/ResultScreen";
import { isAnalyzeResponse } from "../services/validate";
import type { AnalyzeResponse, ClarifyResponse, PauseResponse } from "../types/api";
import clarifyFields from "../fixtures/clarify_fields.json";
import contentReport from "../fixtures/content_report.json";
import glossary from "../fixtures/glossary.json";
import pauseL0 from "../fixtures/pause_l0.json";
import pauseL1 from "../fixtures/pause_l1.json";
import pauseL2 from "../fixtures/pause_l2.json";
import pauseL2Hi from "../fixtures/pause_l2_hi.json";
import pauseL3 from "../fixtures/pause_l3.json";
import recovery from "../fixtures/recovery.json";
import refusal from "../fixtures/refusal.json";

afterEach(cleanup);

const noop = () => {};
const handlers = { onLearn: noop, onReflect: noop, onContinue: noop, onRecover: noop };

function renderPause(pause: unknown, overrides: Partial<typeof handlers> = {}) {
  return render(<PauseCard pause={pause as PauseResponse} {...handlers} {...overrides} />);
}

describe("fixtures", () => {
  it("every captured backend response passes the runtime validator", () => {
    for (const body of [pauseL0, pauseL1, pauseL2, pauseL2Hi, pauseL3, clarifyFields, contentReport, glossary, recovery, refusal]) {
      expect(isAnalyzeResponse(body)).toBe(true);
    }
  });
});

describe("PauseCard", () => {
  it("L1 shows the headline, the signal with its certainty, and a one-tap continue", () => {
    const onContinue = vi.fn();
    renderPause(pauseL1, { onContinue });
    expect(screen.getByText(pauseL1.headline)).toBeTruthy();
    expect(screen.getByText("The message pushes you to act fast.")).toBeTruthy();
    expect(screen.getByText("Likely")).toBeTruthy();
    expect(screen.queryByText("Your context")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it("L2 shows signals, the user's own context, the question, learn and override", () => {
    const onLearn = vi.fn();
    const onContinue = vi.fn();
    renderPause(pauseL2, { onLearn, onContinue });
    expect(screen.getByText("A moment before action")).toBeTruthy();
    expect(screen.getByText("Your context")).toBeTruthy();
    expect(screen.getByText("This decision: ₹20,000.")).toBeTruthy();
    expect(screen.getByText(pauseL2.question!)).toBeTruthy();
    expect(screen.getAllByText("Likely").length).toBe(2);
    expect(screen.getByText("Possible")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Learn why this matters" }));
    expect(onLearn).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: pauseL2.override_label }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it("L3 leads with reflection, shows the user's rules, and still allows continuing", () => {
    const onReflect = vi.fn();
    const onContinue = vi.fn();
    renderPause(pauseL3, { onReflect, onContinue });
    expect(screen.getByText("A deliberate pause")).toBeTruthy();
    for (const rule of pauseL3.rules_text) expect(screen.getByText(rule)).toBeTruthy();
    const buttons = screen.getAllByRole("button");
    expect(buttons[0].textContent).toBe("Think this through");
    fireEvent.click(buttons[0]);
    expect(onReflect).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: pauseL3.override_label }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it("L0 is quiet: headline and continue only", () => {
    renderPause(pauseL0);
    expect(screen.getByText("Nothing stood out")).toBeTruthy();
    expect(screen.queryByText("What I see")).toBeNull();
    expect(screen.getByRole("button", { name: "Continue" })).toBeTruthy();
  });

  it("handles a pause with every optional section missing", () => {
    const minimal = {
      ...pauseL2,
      numbers_text: [],
      rules_text: [],
      signals: [],
      question: null,
      cards: [],
      recovery_entry: null,
      decision: { ...pauseL2.decision, reasons: [] },
    };
    renderPause(minimal);
    expect(screen.getByText(pauseL2.headline)).toBeTruthy();
    expect(screen.queryByText("What I see")).toBeNull();
    expect(screen.queryByText("Your context")).toBeNull();
    expect(screen.queryByText(/Learn/)).toBeNull();
    expect(screen.getByRole("button", { name: "Think this through" })).toBeTruthy();
    expect(screen.getByRole("button", { name: pauseL2.override_label })).toBeTruthy();
  });

  it("renders long generated text and long signal evidence in full", () => {
    const longHeadline = "This is a long headline sentence. ".repeat(5).trim();
    const longSignal = "Evidence ".repeat(80).trim();
    renderPause({
      ...pauseL2,
      headline: longHeadline,
      signals: [{ code: "X", certainty: "unclear", severity: null, text: longSignal }],
    });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(longHeadline);
    expect(screen.getByText(longSignal)).toBeTruthy();
    expect(screen.getByText("Unclear")).toBeTruthy();
  });

  it("offers the recovery path when the backend sends a recovery entry", () => {
    const onRecover = vi.fn();
    renderPause({ ...pauseL3, recovery_entry: { text: "Already paid? Get help now", endpoint: "/v1/recover" } }, { onRecover });
    fireEvent.click(screen.getByRole("button", { name: "Already paid? Get help now" }));
    expect(onRecover).toHaveBeenCalledOnce();
  });
});

describe("signal text", () => {
  const base = { code: "X", certainty: "likely" as const, severity: null };

  it("uses the backend's prefix-free reason_text when present", () => {
    expect(signalBody({ ...base, text: "संभावित: abc", certainty_label: "संभावित", reason_text: "abc" })).toBe("abc");
  });

  it("falls back to removing only the exact English prefix", () => {
    expect(signalBody({ ...base, text: "Likely: text" })).toBe("text");
    expect(signalBody({ ...base, text: "Possible: text" })).toBe("Possible: text");
  });

  it("Hindi pause: badge shows the Hindi label and the body does not repeat it", () => {
    renderPause(pauseL2Hi);
    for (const signal of pauseL2Hi.signals) {
      expect(screen.getAllByText(signal.certainty_label).length).toBeGreaterThan(0);
      expect(screen.getByText(signal.reason_text)).toBeTruthy();
    }
    expect(screen.queryByText(pauseL2Hi.signals[0].text)).toBeNull();
  });
});

describe("ClarificationChoice", () => {
  const questions = (clarifyFields as unknown as ClarifyResponse).questions;

  it("asks for an amount, rejects bad input, and sends whole rupees", () => {
    const onAnswer = vi.fn();
    render(<ClarificationChoice question={questions[0]} onAnswer={onAnswer} />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(onAnswer).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "₹20,000" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onAnswer).toHaveBeenCalledWith({ amount_inr: 20000 });
  });

  it("skipping uses the backend's skipped_fields contract", () => {
    const onAnswer = vi.fn();
    render(<ClarificationChoice question={questions[0]} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("button", { name: "Prefer not to say" }));
    expect(onAnswer).toHaveBeenCalledWith({ skipped_fields: ["amount_inr"] });
  });

  it("renders the backend's options and sends the chosen value", () => {
    const onAnswer = vi.fn();
    render(<ClarificationChoice question={questions[1]} onAnswer={onAnswer} />);
    const group = screen.getByRole("radiogroup");
    expect(within(group).getAllByRole("radio").length).toBe(questions[1].options.length);
    fireEvent.click(screen.getByRole("radio", { name: "My emergency money" }));
    expect(onAnswer).toHaveBeenCalledWith({ funding_source: "emergency_fund" });
  });

  it("parses amounts strictly", () => {
    expect(parseAmount("20000")).toBe(20000);
    expect(parseAmount("20,000")).toBe(20000);
    expect(parseAmount("0")).toBeNull();
    expect(parseAmount("-5")).toBeNull();
    expect(parseAmount("12.5")).toBeNull();
  });
});

describe("ResultScreen", () => {
  const props = { ...handlers, onShareAnother: noop, onHome: noop };

  it("content report: headline, signals and cards, no level and no verdict", () => {
    render(<ResultScreen response={contentReport as AnalyzeResponse} {...props} />);
    expect(screen.getByText(contentReport.headline)).toBeTruthy();
    expect(screen.getByText("About promised returns")).toBeTruthy();
    expect(screen.queryByText(/A deliberate pause|A moment before action/)).toBeNull();
  });

  it("glossary shows the curated explanation", () => {
    render(<ResultScreen response={glossary as AnalyzeResponse} {...props} />);
    expect(screen.getByText(glossary.title)).toBeTruthy();
  });

  it("recovery lists urgent steps first with a tap-to-call contact", () => {
    render(<ResultScreen response={recovery as AnalyzeResponse} {...props} />);
    expect(screen.getByText("Do this now")).toBeTruthy();
    expect(screen.getByRole("link", { name: "1930" }).getAttribute("href")).toBe("tel:1930");
    expect(screen.getByText(recovery.draft_complaint)).toBeTruthy();
  });

  it("refusal shows the message and what Ruko can do instead", () => {
    render(<ResultScreen response={refusal as AnalyzeResponse} {...props} />);
    expect(screen.getByText(refusal.message)).toBeTruthy();
    expect(screen.getByText(refusal.alternative)).toBeTruthy();
  });
});
