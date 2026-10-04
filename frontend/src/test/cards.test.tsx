// P4: the structured cards. Real backend responses, rendered by kind and card type; the
// cooling-off timer (skippable, recorded), lessons, Listen with its fallback, and the charts.

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { CoolingOffTimer, clock } from "../components/CoolingOffTimer";
import { LessonCard } from "../components/LessonCard";
import { ListenButton } from "../components/ListenButton";
import { PauseCard } from "../components/PauseCard";
import { copyFor } from "../copy";
import { ResultRenderer } from "../screens/ResultScreen";
import { addJournalRecord, loadJournal, loadProfile } from "../services/device";
import { stopListening } from "../services/listen";
import type { AnalyzeResponse, Lesson, PauseResponse } from "../types/api";
import calculationConsequence from "../fixtures/calculation_consequence.json";
import calculationSip from "../fixtures/calculation_sip.json";
import clarifyFields from "../fixtures/clarify_fields.json";
import contentReport from "../fixtures/content_report.json";
import glossary from "../fixtures/glossary.json";
import pauseL0 from "../fixtures/pause_l0.json";
import pauseL1 from "../fixtures/pause_l1.json";
import pauseL2 from "../fixtures/pause_l2.json";
import pauseL3 from "../fixtures/pause_l3.json";
import recovery from "../fixtures/recovery.json";
import refusal from "../fixtures/refusal.json";

const en = copyFor("en");
const noop = () => undefined;
const handlers = {
  onLearn: noop,
  onReflect: noop,
  onContinue: noop,
  onRecover: noop,
  onShareAnother: noop,
  onHome: noop,
};

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(
    "ruko.settings.v1",
    JSON.stringify({ onboarded: true, locale: "en", largeText: false, style: "balanced" }),
  );
});
afterEach(() => {
  stopListening();
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("ResultRenderer renders every kind", () => {
  const cases: [string, unknown, string][] = [
    ["pause L0", pauseL0, pauseL0.headline],
    ["pause L1", pauseL1, pauseL1.headline],
    ["pause L2", pauseL2, pauseL2.headline],
    ["pause L3", pauseL3, pauseL3.headline],
    ["content report", contentReport, contentReport.headline],
    ["glossary", glossary, glossary.body],
    ["recovery", recovery, recovery.steps[0].text],
    ["refusal", refusal, refusal.message],
    ["calculation (SIP)", calculationSip, calculationSip.headline],
    ["calculation (consequence)", calculationConsequence, calculationConsequence.headline],
  ];
  it.each(cases)("%s", (_name, response, text) => {
    render(<ResultRenderer response={response as AnalyzeResponse} {...handlers} />);
    expect(screen.getAllByText(text, { exact: false }).length).toBeGreaterThan(0);
  });

  it("a clarify response is not a result screen", () => {
    const { container } = render(<ResultRenderer response={clarifyFields as AnalyzeResponse} {...handlers} />);
    expect(container.textContent).toBe("");
  });
});

describe("charts", () => {
  it("the SIP result draws a line per assumption plus money put in, labelled for people who cannot see colour", async () => {
    render(<ResultRenderer response={calculationSip as unknown as AnalyzeResponse} {...handlers} />);
    const chart = await screen.findByRole("img", { name: en.chartAltSeries });
    expect(chart.querySelectorAll("path.chart-line").length).toBe(calculationSip.scenarios.length + 1);
    const legend = chart.closest("figure")!.querySelector("figcaption")!;
    expect(legend.textContent).toContain(en.chartPutIn);
    for (const scenario of calculationSip.scenarios) expect(legend.textContent).toContain(scenario.label);
    expect(screen.getByText(en.calcIllustration)).toBeTruthy();
  });

  it("the consequence result draws one bar per fall with Indian-grouped rupees and a marker for the money put in", async () => {
    render(<ResultRenderer response={calculationConsequence as unknown as AnalyzeResponse} {...handlers} />);
    const chart = await screen.findByRole("img", { name: en.chartAltBars });
    expect(chart.querySelectorAll("rect.chart-bar").length).toBe(calculationConsequence.scenarios.length);
    expect(chart.textContent).toContain("₹1,25,000"); // the 50% fall on ₹2,50,000
    expect(chart.textContent).toContain(`${en.chartPutIn}: ₹50,000`);
    expect(chart.querySelector("line.chart-marker")).toBeTruthy();
  });

  it("charts only draw numbers the backend returned (no extra points are invented)", async () => {
    render(<ResultRenderer response={calculationSip as unknown as AnalyzeResponse} {...handlers} />);
    const chart = await screen.findByRole("img", { name: en.chartAltSeries });
    const first = calculationSip.scenarios[0].series;
    const path = chart.querySelector("path.chart-line-0")!.getAttribute("d")!;
    expect(path.split("L").length).toBe(first.length); // one M plus (n-1) L segments
  });
});

describe("lessons", () => {
  const lesson = pauseL2.lessons[0] as Lesson;

  it("a pause with lessons offers Learn, even when it has no cards", () => {
    const onLearn = vi.fn();
    render(<PauseCard pause={pauseL2 as unknown as PauseResponse} {...handlers} onLearn={onLearn} />);
    fireEvent.click(screen.getByRole("button", { name: en.learnWhy }));
    expect(onLearn).toHaveBeenCalledOnce();
  });

  it("shows title, body, read time, sources, date and 'not yet checked by a person'", () => {
    render(<LessonCard lesson={lesson} />);
    const card = screen.getByRole("article", { name: lesson.title });
    expect(within(card).getByText(lesson.body)).toBeTruthy();
    expect(within(card).getByText(en.lessonReadTime(lesson.read_seconds))).toBeTruthy();
    expect(within(card).getAllByRole("link").length).toBeGreaterThan(0);
    expect(card.textContent).toContain(en.unverified);
  });

  it("offers a calculator only when the lesson names one and the app can open it", () => {
    const onTool = vi.fn();
    const sip = calculationSip.lessons[0] as Lesson;
    const { rerender } = render(<LessonCard lesson={sip} onTool={onTool} />);
    fireEvent.click(screen.getByRole("button", { name: en.lessonTool }));
    expect(onTool).toHaveBeenCalledWith("sip");
    rerender(<LessonCard lesson={lesson} onTool={onTool} />);
    expect(screen.queryByRole("button", { name: en.lessonTool })).toBeNull();
  });

  it("Listen on a lesson asks /v1/speak for that lesson by ID", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ kind: "speech", audio_base64: "AAAA", audio_format: "wav", provider: "fake", meta: {} }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("Audio", class { play = () => Promise.resolve(); pause = noop; });
    render(<LessonCard lesson={lesson} />);
    fireEvent.click(screen.getByRole("button", { name: en.listen }));
    await screen.findByRole("button", { name: en.listenStop });
    expect(fetchMock.mock.calls[0][0]).toBe("/v1/speak");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({ locale: "en", lesson_id: lesson.id });
  });

  it("a content report shows its lessons", () => {
    render(<ResultRenderer response={contentReport as AnalyzeResponse} {...handlers} />);
    for (const item of contentReport.lessons) {
      expect(screen.getByRole("article", { name: item.title })).toBeTruthy();
    }
  });
});

describe("Listen and its fallback", () => {
  const speechOk = { kind: "speech", audio_base64: "AAAA", audio_format: "wav", provider: "fake", meta: {} };

  it("reads with Ruko's voice, then Stop ends it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(speechOk)));
    const pause = vi.fn();
    vi.stubGlobal("Audio", class { play = () => Promise.resolve(); pause = pause; });
    render(<ListenButton source={{ items: [{ key: "pause.override", slots: {} }] }} text="Continue anyway" />);
    fireEvent.click(screen.getByRole("button", { name: en.listen }));
    fireEvent.click(await screen.findByRole("button", { name: en.listenStop }));
    expect(pause).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: en.listen })).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("falls back to the phone's own voice for the same text, and says so", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    const spoken: { text: string; lang: string }[] = [];
    vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} lang = ""; });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: { cancel: noop, speak: (u: { text: string; lang: string }) => spoken.push(u) },
    });
    render(<ListenButton source={{ items: [] }} text="Wait for now" />);
    fireEvent.click(screen.getByRole("button", { name: en.listen }));
    expect((await screen.findByRole("status")).textContent).toBe(en.listenBrowserVoice);
    expect(spoken).toHaveLength(1);
    expect(spoken[0]).toMatchObject({ text: "Wait for now", lang: "en-IN" });
    Reflect.deleteProperty(window, "speechSynthesis");
  });

  it("says so when neither voice is available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    Reflect.deleteProperty(window, "speechSynthesis");
    render(<ListenButton source={{ items: [] }} text="Wait for now" />);
    fireEvent.click(screen.getByRole("button", { name: en.listen }));
    expect((await screen.findByRole("status")).textContent).toBe(en.listenUnavailable);
    expect(screen.getByRole("button", { name: en.listen })).toBeTruthy();
  });

  it("the pause screen has a Listen button; the request carries the pause's own speak references", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(speechOk));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("Audio", class { play = () => Promise.resolve(); pause = noop; });
    render(<PauseCard pause={pauseL2 as unknown as PauseResponse} {...handlers} />);
    fireEvent.click(screen.getByRole("button", { name: en.listen }));
    await screen.findByRole("button", { name: en.listenStop });
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(sent.items).toEqual(pauseL2.speak.slice(0, 10));
  });
});

describe("clock", () => {
  it("formats m:ss and never goes negative", () => {
    expect(clock(900)).toBe("15:00");
    expect(clock(61)).toBe("1:01");
    expect(clock(0.2)).toBe("0:01");
    expect(clock(-5)).toBe("0:00");
  });
});

describe("cooling-off timer", () => {
  it("counts down, can be skipped, and reports the skip once", () => {
    vi.useFakeTimers();
    const onFinish = vi.fn();
    render(<CoolingOffTimer minutes={2} onFinish={onFinish} />);
    expect(screen.getByRole("timer").textContent).toBe(en.timerRemaining("2:00"));
    act(() => void vi.advanceTimersByTime(30_000));
    expect(screen.getByRole("timer").textContent).toBe(en.timerRemaining("1:30"));
    fireEvent.click(screen.getByRole("button", { name: en.timerSkip }));
    expect(onFinish).toHaveBeenCalledTimes(1);
    expect(onFinish).toHaveBeenCalledWith(true);
    expect(screen.getByText(en.timerSkipped)).toBeTruthy();
    act(() => void vi.advanceTimersByTime(300_000));
    expect(onFinish).toHaveBeenCalledOnce();
  });

  it("running to the end reports that the wait was not skipped", () => {
    vi.useFakeTimers();
    const onFinish = vi.fn();
    render(<CoolingOffTimer minutes={1} onFinish={onFinish} />);
    act(() => void vi.advanceTimersByTime(61_000));
    expect(onFinish).toHaveBeenCalledTimes(1);
    expect(onFinish).toHaveBeenCalledWith(false);
    expect(screen.getByText(en.timerDone)).toBeTruthy();
    expect(screen.queryByRole("button", { name: en.timerSkip })).toBeNull();
  });

  it("only an L3 pause with minutes shows it, and only when the app can record the result", () => {
    const cooling = pauseL3.decision.cooling_off_minutes;
    expect(cooling).toBe(15);
    const { unmount } = render(<PauseCard pause={pauseL3 as unknown as PauseResponse} {...handlers} onCooling={noop} />);
    expect(screen.getByRole("timer").textContent).toBe(en.timerRemaining("15:00"));
    unmount();
    render(<PauseCard pause={pauseL3 as unknown as PauseResponse} {...handlers} />);
    expect(screen.queryByRole("timer")).toBeNull();
    cleanup();
    render(<PauseCard pause={pauseL2 as unknown as PauseResponse} {...handlers} onCooling={noop} />);
    expect(screen.queryByRole("timer")).toBeNull();
  });

  it("never blocks: continuing is available the whole time", () => {
    const onContinue = vi.fn();
    render(<PauseCard pause={pauseL3 as unknown as PauseResponse} {...handlers} onCooling={noop} onContinue={onContinue} />);
    fireEvent.click(screen.getByRole("button", { name: pauseL3.override_label }));
    expect(onContinue).toHaveBeenCalledOnce();
  });
});

describe("the L3 wait is recorded in the journal", () => {
  async function toJournal(act_: () => Promise<void> | void) {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(pauseL3)));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tip" } });
    fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
    await screen.findByText(pauseL3.headline);
    await act_();
    fireEvent.click(screen.getByRole("button", { name: pauseL3.override_label }));
    fireEvent.click(await screen.findByRole("button", { name: en.done }));
    return loadJournal()[0];
  }

  it("continuing before the wait ends counts as skipping it", async () => {
    const record = await toJournal(() => undefined);
    expect(record.notes.cooling_off).toEqual({ minutes: 15, skipped: true });
  });

  it("pressing Skip is recorded as skipped", async () => {
    const record = await toJournal(() => void fireEvent.click(screen.getByRole("button", { name: en.timerSkip })));
    expect(record.notes.cooling_off).toEqual({ minutes: 15, skipped: true });
  });

  it("sitting through the wait is recorded as not skipped", async () => {
    // Drive the timer by hand: capture its interval callback and move the clock.
    let now = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    const ticks: (() => void)[] = [];
    vi.spyOn(window, "setInterval").mockImplementation(((fn: () => void) => {
      ticks.push(fn);
      return ticks.length;
    }) as unknown as typeof window.setInterval);
    vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(pauseL3)));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tip" } });
    fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(screen.getByText(pauseL3.headline)).toBeTruthy();
    now += 15 * 60_000 + 2000;
    act(() => ticks.forEach((tick) => tick()));
    expect(screen.getByText(en.timerDone)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: pauseL3.override_label }));
    fireEvent.click(screen.getByRole("button", { name: en.done }));
    expect(loadJournal()[0].notes.cooling_off).toEqual({ minutes: 15, skipped: false });
  });

  it("a pause without a wait records none", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(pauseL2)));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tip" } });
    fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
    fireEvent.click(await screen.findByRole("button", { name: pauseL2.override_label }));
    fireEvent.click(await screen.findByRole("button", { name: en.done }));
    expect(loadJournal()[0].notes.cooling_off).toBeNull();
  });
});

describe("quiet style", () => {
  it("trims the optional question on a small nudge; balanced shows it", () => {
    const pause = { ...pauseL1, question: "Is this decision consistent with your plan?" } as unknown as PauseResponse;
    const { rerender } = render(<PauseCard pause={pause} {...handlers} />);
    expect(screen.getByText(pause.question!)).toBeTruthy();
    rerender(<PauseCard pause={pause} {...handlers} quiet />);
    expect(screen.queryByText(pause.question!)).toBeNull();
    expect(screen.getByText(pause.headline)).toBeTruthy(); // the nudge itself stays
  });

  it("does not trim anything from a stronger pause", () => {
    render(<PauseCard pause={pauseL2 as unknown as PauseResponse} {...handlers} quiet />);
    expect(screen.getByText(pauseL2.question!)).toBeTruthy();
    expect(screen.getByText(en.yourContext)).toBeTruthy();
  });
});

describe("after a decision", () => {
  async function runFlow(response: unknown) {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(response)));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tip" } });
    fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
    const pause = response as PauseResponse;
    const label = pause.level === "L0" ? en.continue : pause.override_label;
    fireEvent.click(await screen.findByRole("button", { name: label }));
  }

  it("offers the one-tap rating after a pause and keeps the answer on the phone", async () => {
    await runFlow(pauseL2);
    fireEvent.click(await screen.findByRole("radio", { name: en.feelingAnnoying }));
    expect(screen.getByText(en.feelingThanks)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: en.done }));
    expect(loadJournal()[0].notes.feeling).toBe("annoying");
  });

  it("does not ask again within a week, and never asks after a quiet L0", async () => {
    addJournalRecord({
      ...{
        entry: { id: "old", date: new Date().toISOString().slice(0, 10), stage: "consider_action", product_class: "unknown", source_type: "unknown", level_shown: "L2", reason_codes: [], action: "delayed", overrode: false, override_reason_given: false, pause_completed: true, could_state_why: true, followed_own_rules: true },
        notes: { shared_excerpt: "", reflection_choice: null, reflection_text: "", feeling: "fine" },
      },
    });
    await runFlow(pauseL2);
    await screen.findByText(en.journalSavedTitle);
    expect(screen.queryByRole("radio", { name: en.feelingHelpful })).toBeNull();
    cleanup();
    window.localStorage.removeItem("ruko.journal.v1");
    await runFlow(pauseL0);
    await screen.findByText(en.journalSavedTitle);
    expect(screen.queryByRole("radio", { name: en.feelingHelpful })).toBeNull();
  });

  it("marks non-critical lessons as seen so they fade, and never the safety-critical ones", async () => {
    const response = {
      ...pauseL3,
      lessons: [
        { ...(pauseL3.lessons[0] as object), id: "leverage_basics", safety_critical: false },
        { ...(pauseL2.lessons[0] as object), id: "guaranteed_returns", safety_critical: true },
      ],
    };
    await runFlow(response);
    fireEvent.click(await screen.findByRole("button", { name: en.done }));
    await waitFor(() => expect(loadProfile().seen_lesson_ids).toEqual(["leverage_basics"]));
  });
});
