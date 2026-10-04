// First run, language, settings, the recovery form, "My patterns", voice and the
// calculator entry, driven through the whole app with fetch stubbed to real backend responses.

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { copyFor } from "../copy";
import { addJournalRecord, loadEvidence, loadProfile } from "../services/device";
import { loadSettings } from "../services/settings";
import clarifyFields from "../fixtures/clarify_fields.json";
import journalReview from "../fixtures/journal_review.json";
import pauseL2 from "../fixtures/pause_l2.json";
import recoverPaid from "../fixtures/recover_paid.json";

const en = copyFor("en");
const hi = copyFor("hi");
const kn = copyFor("kn");

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

const bodyOf = (fetchMock: ReturnType<typeof vi.fn>, call = 0) =>
  JSON.parse(fetchMock.mock.calls[call][1].body as string);

function onboarded(over: Record<string, unknown> = {}) {
  window.localStorage.setItem(
    "ruko.settings.v1",
    JSON.stringify({ onboarded: true, locale: "en", largeText: false, style: "balanced", ...over }),
  );
}

function entry(date = "2026-10-01") {
  return {
    entry: {
      id: "e1", date, stage: "consider_action" as const, product_class: "scheme_or_app" as const,
      amount_inr: 5000, source_type: "unsolicited_group" as const, level_shown: "L2" as const,
      reason_codes: ["UNSOLICITED_SOURCE"], action: "delayed" as const, overrode: false,
      override_reason_given: false, pause_completed: true, could_state_why: true,
      followed_own_rules: true,
    },
    notes: { shared_excerpt: "SECRET group tip", reflection_choice: null, reflection_text: "PRIVATE reason" },
  }; // prettier-ignore
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("first run", () => {
  function firstRun() {
    window.localStorage.clear(); // not onboarded
    render(<App />);
  }

  it("starts with the language choice and switches the app language at once", () => {
    firstRun();
    expect(screen.getByText(en.onboardLanguageTitle)).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "हिन्दी" }));
    expect(screen.getByText(hi.onboardLanguageTitle)).toBeTruthy();
    expect(screen.getByText(hi.languageDraft)).toBeTruthy(); // says the translation is a draft
  });

  it("'Skip, use safe defaults' sets no rules and goes home in the chosen language", () => {
    firstRun();
    fireEvent.click(screen.getByRole("radio", { name: "ಕನ್ನಡ" }));
    fireEvent.click(screen.getByRole("button", { name: kn.onboardSkip }));
    expect(screen.getByText(kn.homeTitle)).toBeTruthy();
    expect(loadProfile()).toEqual({});
    expect(loadSettings()).toEqual({ locale: "kn", onboarded: true, largeText: false, style: "balanced" });
  });

  it("walks language, rules and style, and saves exactly what the user wrote", () => {
    firstRun();
    fireEvent.click(screen.getByRole("button", { name: en.onboardNext }));
    expect(screen.getByText(en.onboardRulesTitle)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(en.maxShare), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(en.coolingRule), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText(en.protectedGoal), { target: { value: "₹2,00,000" } });
    fireEvent.click(screen.getByLabelText(en.noBorrowed));
    fireEvent.click(screen.getByRole("button", { name: en.onboardNext }));
    fireEvent.click(screen.getByRole("radio", { name: en.styleQuiet }));
    fireEvent.click(screen.getByRole("button", { name: en.onboardStart }));
    expect(screen.getByText(en.homeTitle)).toBeTruthy();
    expect(loadProfile()).toEqual({
      rules: {
        max_share_of_savings_pct: 10,
        cooling_off_minutes: 20,
        no_borrowed_money: true,
        protected_goals: [{ id: "goal-1", amount_inr: 200000 }],
      },
    });
    expect(loadSettings().style).toBe("quiet");
  });

  it("an out-of-range rule is not saved (the backend would reject it)", () => {
    firstRun();
    fireEvent.click(screen.getByRole("button", { name: en.onboardNext }));
    fireEvent.change(screen.getByLabelText(en.maxShare), { target: { value: "150" } });
    fireEvent.change(screen.getByLabelText(en.emergencyBuffer), { target: { value: "99" } });
    fireEvent.click(screen.getByRole("button", { name: en.onboardNext }));
    fireEvent.click(screen.getByRole("button", { name: en.onboardStart }));
    expect(loadProfile()).toEqual({});
  });

  it("a shared message skips the welcome and goes straight to analysis", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(pauseL2)));
    window.history.replaceState(null, "", "/?text=Guaranteed%203x%20return");
    firstRun();
    await screen.findByText(pauseL2.headline);
  });
});

describe("settings", () => {
  function openSettings() {
    onboarded();
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(en.settings) }));
  }

  it("changes apply and save without leaving the screen", () => {
    openSettings();
    fireEvent.click(screen.getByLabelText(en.largeText));
    expect(screen.getByText(en.settingsTitle)).toBeTruthy();
    expect(document.querySelector(".app")!.classList.contains("large-text")).toBe(true);
    expect(loadSettings().largeText).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: en.styleQuiet }));
    expect(screen.getByText(en.settingsTitle)).toBeTruthy();
    expect(loadSettings().style).toBe("quiet");
  });

  it("switching language re-renders every screen in that language, and it persists", () => {
    openSettings();
    fireEvent.click(screen.getByRole("radio", { name: "हिन्दी" }));
    expect(screen.getByText(hi.settingsTitle)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: hi.back }));
    expect(screen.getByText(hi.homeTitle)).toBeTruthy();
    expect(document.querySelector(".app")!.getAttribute("lang")).toBe("hi");
    cleanup();
    render(<App />); // a fresh start reads the saved language
    expect(screen.getByText(hi.homeTitle)).toBeTruthy();
  });

  it("the demo tools stay hidden until the version line is tapped five times", () => {
    openSettings();
    expect(screen.queryByRole("link", { name: en.demoBroker })).toBeNull();
    const version = screen.getByRole("button", { name: en.versionLine });
    for (let i = 0; i < 4; i++) fireEvent.click(version);
    expect(screen.queryByRole("link", { name: en.demoBroker })).toBeNull();
    fireEvent.click(version);
    expect(screen.getByRole("link", { name: en.demoBroker }).getAttribute("href")).toBe("/demo/broker");
  });

  it("the home screen has no link to the demo broker", () => {
    onboarded();
    render(<App />);
    expect(document.querySelector('a[href="/demo/broker"]')).toBeNull();
  });

  it("downloads the anonymised summary", () => {
    openSettings();
    const create = vi.fn(() => "blob:summary");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    fireEvent.click(screen.getByRole("button", { name: en.exportButton }));
    expect(create).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(screen.getByText(en.exportDone)).toBeTruthy();
    click.mockRestore();
  });
});

describe("language is sent with every request", () => {
  it("analyze carries the chosen locale", async () => {
    onboarded({ locale: "hi" });
    const fetchMock = vi.fn().mockResolvedValue(json(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: hi.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "some tip" } });
    fireEvent.click(screen.getByRole("button", { name: hi.composeSubmit }));
    await screen.findByText(pauseL2.headline);
    expect(bodyOf(fetchMock).locale).toBe("hi");
  });

  it("the profile sent includes the attention counts counted from the journal", async () => {
    onboarded();
    const today = new Date().toISOString().slice(0, 10);
    addJournalRecord(entry(today));
    const fetchMock = vi.fn().mockResolvedValue(json(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tip" } });
    fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
    await screen.findByText(pauseL2.headline);
    expect(bodyOf(fetchMock).profile.attention).toEqual({
      l1_this_week: 0,
      l2_this_week: 1,
      l3_this_week: 0,
      rule_following_streak: 1,
    });
  });
});

describe("the recovery form", () => {
  async function fillAndSubmit(fetchMock: ReturnType<typeof vi.fn>) {
    onboarded();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(en.alreadyPaid) }));
    fireEvent.click(within(screen.getByRole("region", { name: en.recoverPaid })).getByRole("radio", { name: en.yes }));
    fireEvent.click(screen.getByRole("radio", { name: en.paymentMethods.upi }));
    fireEvent.click(
      within(screen.getByRole("region", { name: en.recoverCannotWithdraw })).getByRole("radio", { name: en.yes }),
    );
    fireEvent.click(screen.getByRole("button", { name: en.recoverSubmit }));
  }

  it("sends only the yes/no answers and shows urgent steps, tap-to-call and a draft", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(recoverPaid));
    await fillAndSubmit(fetchMock);
    await screen.findByText(en.recoveryUrgent);
    expect(fetchMock.mock.calls[0][0]).toBe("/v1/recover");
    expect(bodyOf(fetchMock)).toEqual({
      locale: "en",
      answers: {
        paid_money: true,
        payment_method: "upi",
        installed_app: false,
        registered_broker_involved: false,
        unauthorized_trade: false,
        cannot_withdraw: true,
      },
    });
    const call = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "tel:1930");
    expect(call).toBeTruthy();
    expect(screen.getByText(recoverPaid.draft_complaint.slice(0, 20), { exact: false })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/refund|money back|guarantee/i);
  });

  it("the evidence checklist ticks are remembered on this phone", async () => {
    await fillAndSubmit(vi.fn().mockResolvedValue(json(recoverPaid)));
    const first = (await screen.findAllByRole("checkbox"))[0];
    fireEvent.click(first);
    expect(loadEvidence(recoverPaid.scenario)).toEqual([0]);
    expect(screen.getByText(en.recoveryTicked(1, recoverPaid.evidence_checklist.length))).toBeTruthy();
    cleanup();
    // Opening the same guide again shows the tick.
    await fillAndSubmit(vi.fn().mockResolvedValue(json(recoverPaid)));
    expect(((await screen.findAllByRole("checkbox"))[0] as HTMLInputElement).checked).toBe(true);
  });

  it("cannot be submitted until the first question is answered; 'no' sends payment method none", () => {
    onboarded();
    const fetchMock = vi.fn().mockResolvedValue(json(recoverPaid));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(en.alreadyPaid) }));
    expect((screen.getByRole("button", { name: en.recoverSubmit }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(screen.getByRole("region", { name: en.recoverPaid })).getByRole("radio", { name: en.no }));
    expect(screen.queryByText(en.recoverMethod)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: en.recoverSubmit }));
    expect(bodyOf(fetchMock).answers.payment_method).toBe("none");
    expect(bodyOf(fetchMock).answers.paid_money).toBe(false);
  });
});

describe("My patterns (the mirror)", () => {
  function openMirror() {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(en.myPatterns) }));
  }

  it("with an empty journal it says so and sends nothing", () => {
    onboarded();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    openMirror();
    expect(screen.getByText(en.mirrorEmpty)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends only the journal entries (never notes or text) and shows the backend's numbers in words", async () => {
    onboarded();
    addJournalRecord(entry());
    const fetchMock = vi.fn().mockResolvedValue(json(journalReview));
    vi.stubGlobal("fetch", fetchMock);
    openMirror();
    await screen.findByText(journalReview.highlights[0]);
    expect(fetchMock.mock.calls[0][0]).toBe("/v1/journal/review");
    const body = bodyOf(fetchMock);
    expect(Object.keys(body).sort()).toEqual(["entries", "locale"]);
    expect(JSON.stringify(body)).not.toMatch(/SECRET|PRIVATE|shared_excerpt|reflection/);
    expect(screen.getByText(en.mirrorMetrics.total_decisions)).toBeTruthy();
    expect(screen.getByText(`${journalReview.reconsideration_pct}%`)).toBeTruthy();
    expect(screen.getByText(en.mirrorOutro)).toBeTruthy(); // "not a score"
  });

  it("when offline it says the journal still works and shows no numbers", async () => {
    onboarded();
    addJournalRecord(entry());
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    openMirror();
    expect(await screen.findByText(en.mirrorOffline)).toBeTruthy();
    expect(screen.queryByText(en.mirrorMetrics.total_decisions)).toBeNull();
  });
});

describe("voice input", () => {
  class FakeRecorder {
    static isTypeSupported = () => true;
    static instances: FakeRecorder[] = [];
    state = "inactive";
    mimeType = "audio/webm;codecs=opus";
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    onstop: ((e: Event) => void) | null = null;
    onerror: (() => void) | null = null;
    constructor() {
      FakeRecorder.instances.push(this);
    }
    start() {
      this.state = "recording";
    }
    stop() {
      this.state = "inactive";
      this.ondataavailable?.({ data: new Blob(["abc"], { type: "audio/webm" }) });
      this.onstop?.(new Event("stop"));
    }
  }

  function withMicrophone(getUserMedia: () => Promise<unknown>) {
    FakeRecorder.instances = [];
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
  }
  const stream = { getTracks: () => [{ stop: () => undefined }] };

  function openCompose() {
    onboarded();
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
  }

  it("records, sends the audio to /v1/analyze/voice, and keeps the text path open", async () => {
    withMicrophone(() => Promise.resolve(stream));
    const fetchMock = vi.fn().mockResolvedValue(json(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    openCompose();
    expect(screen.getByRole("textbox")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    fireEvent.click(await screen.findByRole("button", { name: en.voiceStop }));
    await screen.findByText(pauseL2.headline);
    expect(fetchMock.mock.calls[0][0]).toBe("/v1/analyze/voice");
    expect(bodyOf(fetchMock)).toMatchObject({
      audio_base64: "YWJj",
      audio_format: "webm",
      locale: "en",
      speech_locale: "en",
      answers: {},
    });
  });

  it("a clarify question after a voice note resends the same audio with the answers", async () => {
    withMicrophone(() => Promise.resolve(stream));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(clarifyFields))
      .mockResolvedValueOnce(json(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    openCompose();
    fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    fireEvent.click(await screen.findByRole("button", { name: en.voiceStop }));
    await screen.findByText("How much are you thinking of putting in? (in rupees)");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "20000" } });
    fireEvent.click(screen.getByRole("radio", { name: "My emergency money" }));
    fireEvent.click(screen.getByRole("radio", { name: "A scheme, app or platform" }));
    fireEvent.click(screen.getByRole("button", { name: en.clarifyContinue }));
    await screen.findByText(pauseL2.headline);
    expect(fetchMock.mock.calls[1][0]).toBe("/v1/analyze/voice");
    expect(bodyOf(fetchMock, 1).audio_base64).toBe("YWJj");
    expect(bodyOf(fetchMock, 1).answers.amount_inr).toBe(20000);
  });

  it("explains a refused microphone calmly and leaves typing available", async () => {
    withMicrophone(() => Promise.reject(Object.assign(new Error("no"), { name: "NotAllowedError" })));
    openCompose();
    fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    expect((await screen.findByRole("alert")).textContent).toBe(en.voiceProblems.permission_denied);
    expect(screen.getByRole("textbox")).toBeTruthy();
  });

  it("says so when the browser cannot record at all", () => {
    vi.stubGlobal("MediaRecorder", undefined);
    Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
    openCompose();
    expect(screen.getByText(en.voiceProblems.unsupported)).toBeTruthy();
    expect(screen.queryByRole("button", { name: en.voiceStart })).toBeNull();
  });

  it("stops by itself at the backend's 30 second limit", async () => {
    withMicrophone(() => Promise.resolve(stream));
    const fetchMock = vi.fn().mockResolvedValue(json(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    openCompose();
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    });
    expect(FakeRecorder.instances).toHaveLength(1);
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });
    vi.useRealTimers();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toBe("/v1/analyze/voice");
  });
});
