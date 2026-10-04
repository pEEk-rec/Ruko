// The calculate path in the app (logic and rendering only).

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { answerFor, ClarificationChoice } from "../components/ClarificationChoice";
import { ResultScreen } from "../screens/ResultScreen";
import { isAnalyzeResponse } from "../services/validate";
import { mergeAnswers } from "../state/answers";
import type { AnalyzeResponse, ClarifyResponse } from "../types/api";
import calculationConsequence from "../fixtures/calculation_consequence.json";
import calculationSip from "../fixtures/calculation_sip.json";
import clarifyCalc from "../fixtures/clarify_calc.json";

const noop = () => {};
const handlers = {
  onLearn: noop,
  onReflect: noop,
  onContinue: noop,
  onRecover: noop,
  onShareAnother: noop,
  onHome: noop,
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(
    "ruko.settings.v1",
    JSON.stringify({ onboarded: true, locale: "en", largeText: false, style: "balanced" })
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("calculation responses", () => {
  it("captured calculation responses pass the runtime validator", () => {
    expect(isAnalyzeResponse(calculationSip)).toBe(true);
    expect(isAnalyzeResponse(calculationConsequence)).toBe(true);
    expect(isAnalyzeResponse(clarifyCalc)).toBe(true);
  });

  it("a calculation with fewer than two scenarios is rejected", () => {
    const one = { ...calculationSip, scenarios: calculationSip.scenarios.slice(0, 1) };
    expect(isAnalyzeResponse(one)).toBe(false);
    expect(isAnalyzeResponse({ ...calculationSip, is_illustration: false })).toBe(false);
  });

  it("renders the headline, every scenario line, the explanation and the assumptions", () => {
    render(<ResultScreen response={calculationSip as unknown as AnalyzeResponse} {...handlers} />);
    expect(screen.getByText(calculationSip.headline)).toBeTruthy();
    for (const scenario of calculationSip.scenarios) {
      expect(screen.getByRole("region", { name: scenario.label })).toBeTruthy();
      for (const line of scenario.lines) expect(screen.getAllByText(line).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(calculationSip.explanation)).toBeTruthy();
    for (const line of calculationSip.assumptions) expect(screen.getByText(line)).toBeTruthy();
  });
});

describe("calculator clarify answers", () => {
  it("calculator fields go under answers.calculation", () => {
    expect(answerFor("calculation.months", 120)).toEqual({ calculation: { months: 120 } });
    expect(answerFor("calculation.tool", "sip")).toEqual({ calculation: { tool: "sip" } });
    expect(answerFor("funding_source", "savings")).toEqual({ funding_source: "savings" });
  });

  it("answers merge field by field", () => {
    const merged = mergeAnswers({ calculation: { tool: "sip" } }, { calculation: { months: 60 } });
    expect(merged).toEqual({ calculation: { tool: "sip", months: 60 } });
  });

  it("a months question takes a plain number and cannot be skipped", () => {
    const onAnswer = vi.fn();
    const question = (clarifyCalc as unknown as ClarifyResponse).questions[0];
    render(<ClarificationChoice question={question} onAnswer={onAnswer} />);
    expect(screen.queryByRole("button", { name: "Prefer not to say" })).toBeNull();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "120" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onAnswer).toHaveBeenCalledWith({ calculation: { months: 120 } });
  });
});

describe("calculate flow", () => {
  it("share → missing months asked → calculation shown", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(clarifyCalc))
      .mockResolvedValueOnce(jsonResponse(calculationSip));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Share something" }));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "What will my SIP of 5000 a month look like?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));
    await screen.findByText(clarifyCalc.questions[0].text);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "120" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText(calculationSip.headline);
    const second = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(second.answers).toEqual({ calculation: { months: 120 } });
  });
});
