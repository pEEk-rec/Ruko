// The live calculator: empty until numbers exist, debounced and cancellable requests, rate chips,
// stale answers ignored, calm errors. The browser computes nothing; every number is from fetch.

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { copyFor } from "../copy";
import { CalculatorScreen } from "../screens/CalculatorScreen";
import calculateClarify from "../fixtures/calculate_clarify.json";
import calculateSip from "../fixtures/calculate_sip.json";

const en = copyFor("en");
const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

function mount(seed: Parameters<typeof CalculatorScreen>[0]["seed"] = null) {
  return render(
    <CalculatorScreen seed={seed} onBack={() => undefined} />,
  );
}
const settle = () => act(() => vi.advanceTimersByTimeAsync(500));
const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  vi.useFakeTimers();
  window.localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("live calculator", () => {
  it("starts empty and asks for nothing until a tool is chosen", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    mount();
    expect(screen.queryByLabelText(en.calcFields.monthly_inr)).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("waits for every required number, then asks the backend once, after a pause in typing", async () => {
    const fetchMock = vi.fn(async () => json(calculateSip));
    vi.stubGlobal("fetch", fetchMock);
    mount();
    fireEvent.click(screen.getByRole("radio", { name: en.calcTools.sip }));
    type(en.calcFields.monthly_inr, "5000");
    await settle();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(en.calcFillIn)).toBeTruthy();
    type(en.calcFields.months, "1");
    type(en.calcFields.months, "12");
    type(en.calcFields.months, "120");
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const sent = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, { body: string }])[1].body);
    expect(sent.inputs).toMatchObject({ tool: "sip", monthly_inr: 5000, months: 120 });
    expect(screen.getByText(calculateSip.headline)).toBeTruthy();
    expect(screen.getByText(en.calcIllustration)).toBeTruthy();
  });

  it("adds the person's own rate next to the labelled ones, and can remove it", async () => {
    const fetchMock = vi.fn(async () => json(calculateSip));
    vi.stubGlobal("fetch", fetchMock);
    mount({ tool: "sip", monthly_inr: 5000, months: 120 });
    await settle();
    fireEvent.change(screen.getByLabelText(en.calcRates), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: en.calcAddRate }));
    await settle();
    const last = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as unknown as [string, { body: string }];
    expect(JSON.parse(last[1].body).inputs.rates_pct).toEqual([9]);
    fireEvent.click(screen.getByRole("button", { name: en.calcRemove("9") }));
    await settle();
    const after = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as unknown as [string, { body: string }];
    expect(JSON.parse(after[1].body).inputs.rates_pct).toBeUndefined();
  });

  it("starts from the numbers of a result being adjusted", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(calculateSip)));
    mount({ tool: "sip", monthly_inr: 7000, months: 60 });
    expect((screen.getByLabelText(en.calcFields.monthly_inr) as HTMLInputElement).value).toBe("7000");
    await settle();
    expect(screen.getByText(calculateSip.headline)).toBeTruthy();
  });

  it("ignores an older answer that arrives after a newer request", async () => {
    const stale = { ...calculateSip, headline: "STALE ANSWER" };
    let release: (r: Response) => void = () => undefined;
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => new Promise<Response>((resolve) => (release = resolve)))
      .mockImplementation(async () => json(calculateSip));
    vi.stubGlobal("fetch", fetchMock);
    mount({ tool: "sip", monthly_inr: 5000, months: 120 });
    await settle();
    type(en.calcFields.months, "240");
    await settle();
    await act(async () => release(json(stale)));
    expect(screen.queryByText("STALE ANSWER")).toBeNull();
    expect(screen.getByText(calculateSip.headline)).toBeTruthy();
  });

  it("shows a calm message when the server fails, never a stack trace", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
    mount({ tool: "sip", monthly_inr: 5000, months: 120 });
    await settle();
    expect(screen.getByRole("alert").textContent).toBe(en.errors.invalid_response);
  });

  it("shows no result when the backend wants more information", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(calculateClarify)));
    mount({ tool: "sip", monthly_inr: 5000, months: 120 });
    await settle();
    expect(screen.queryByText(en.calcIllustration)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("only shows rate chips for tools that use them, and falls for the consequence tool", () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(calculateSip)));
    mount();
    fireEvent.click(screen.getByRole("radio", { name: en.calcTools.costs }));
    expect(screen.queryByLabelText(en.calcRates)).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: en.calcTools.consequence }));
    expect(screen.getByLabelText(en.calcDrops)).toBeTruthy();
  });
});
