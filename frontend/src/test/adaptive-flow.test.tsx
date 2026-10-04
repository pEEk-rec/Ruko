// A to F through the whole app: one adaptive question form, inline refine, quotes, contextual
// choices, plans, waits, pace and bridges. Fetch returns real backend responses.

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { PauseCard } from "../components/PauseCard";
import { copyFor } from "../copy";
import { addJournalRecord, loadJournal, loadProfile, type JournalRecord } from "../services/device";
import { loadMemory, updateMemory } from "../services/memory";
import type { PauseResponse } from "../types/api";
import clarifyHints from "../fixtures/clarify_hints.json";
import glossaryUnknown from "../fixtures/glossary_unknown.json";
import pauseL2 from "../fixtures/pause_l2.json";
import pauseL3 from "../fixtures/pause_l3.json";
import pauseScam from "../fixtures/pause_scam.json";
import refusal from "../fixtures/refusal.json";
import refusalPrediction from "../fixtures/refusal_prediction.json";

const en = copyFor("en");
const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
const bodyOf = (fetchMock: ReturnType<typeof vi.fn>, call = 0) =>
  JSON.parse(fetchMock.mock.calls[call][1].body as string);

function stub(...responses: unknown[]) {
  const fetchMock = vi.fn();
  responses.forEach((r) => fetchMock.mockResolvedValueOnce(json(r)));
  fetchMock.mockImplementation(async () => json(responses[responses.length - 1]));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function share(text: string) {
  fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
}

const chip = (name: string) => fireEvent.click(screen.getByRole("radio", { name }));
const button = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));

function entry(over: Partial<JournalRecord["entry"]> = {}): JournalRecord {
  return {
    entry: {
      id: "e1", date: "2026-09-20", stage: "consider_action", product_class: "scheme_or_app",
      source_type: "unsolicited_group", level_shown: "L2", reason_codes: [], action: "delayed",
      overrode: false, override_reason_given: false, pause_completed: true, could_state_why: true,
      followed_own_rules: true, ...over,
    },
    notes: { shared_excerpt: "an old tip", reflection_choice: null, reflection_text: "" },
  }; // prettier-ignore
}

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(
    "ruko.settings.v1",
    JSON.stringify({ onboarded: true, locale: "en", largeText: false, style: "balanced" }),
  );
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("B: one question form that adapts", () => {
  it("shows every question at once, offers the amount the message mentions, tags the matching product", async () => {
    updateMemory((m) => ({ ...m, lastFunding: "emergency_fund" }));
    stub(clarifyHints, pauseL2);
    render(<App />);
    await share("Join now! Guaranteed returns, deposit 15000 to start");
    await screen.findByText("How much are you thinking of putting in? (in rupees)");
    expect(screen.getByText("Where would this money come from?")).toBeTruthy();
    expect(screen.getByText("What kind of product is this?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "The message mentions ₹15,000" }));
    expect((screen.getAllByRole("textbox")[0] as HTMLInputElement).value).toBe("15000");
    expect(screen.getByText("Matches the message")).toBeTruthy();
    expect(screen.getByText(en.lastTime)).toBeTruthy();
  });

  it("will not continue until every question is answered, and says which", async () => {
    const fetchMock = stub(clarifyHints, pauseL2);
    render(<App />);
    await share("Join now! Guaranteed returns, deposit 15000 to start");
    await screen.findByText("Where would this money come from?");
    button(en.clarifyContinue);
    expect(screen.getAllByRole("alert").length).toBe(3);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends the answers together, and remembers the funding for next time", async () => {
    const fetchMock = stub(clarifyHints, pauseL2);
    render(<App />);
    await share("Join now! Guaranteed returns, deposit 15000 to start");
    await screen.findByText("Where would this money come from?");
    fireEvent.click(screen.getByRole("button", { name: "The message mentions ₹15,000" }));
    chip("My savings");
    chip("A scheme, app or platform");
    button(en.clarifyContinue);
    await screen.findByText(pauseL2.headline);
    expect(bodyOf(fetchMock, 1).answers).toEqual({
      amount_inr: 15000,
      funding_source: "savings",
      product_class: "scheme_or_app",
    });
    expect(loadMemory().lastFunding).toBe("savings");
  });

  it("'Prefer not to say' skips the amount without asking again", async () => {
    const fetchMock = stub(clarifyHints, pauseL2);
    render(<App />);
    await share("Join now! Guaranteed returns, deposit 15000 to start");
    await screen.findByText("Where would this money come from?");
    button(en.clarifySkip);
    chip("My savings");
    chip("A scheme, app or platform");
    button(en.clarifyContinue);
    await screen.findByText(pauseL2.headline);
    expect(bodyOf(fetchMock, 1).answers.skipped_fields).toEqual(["amount_inr"]);
    expect(bodyOf(fetchMock, 1).answers.amount_inr).toBeUndefined();
  });

  it("asks once how familiar the product is, keeps it, and sends it as their own declaration", async () => {
    const fetchMock = stub(clarifyHints, pauseL2, clarifyHints);
    render(<App />);
    await share("Thinking of nifty options, deposit 15000");
    await screen.findByText("Where would this money come from?");
    expect(screen.queryByText(en.experienceQuestion)).toBeNull(); // product not chosen yet
    chip("Futures or options (F&O)");
    chip(en.experienceOptions.none);
    fireEvent.click(screen.getByRole("button", { name: "The message mentions ₹15,000" }));
    chip("My savings");
    button(en.clarifyContinue);
    await screen.findByText(pauseL2.headline);
    expect(loadProfile().experience).toEqual({ derivative: "none" });
    expect(bodyOf(fetchMock, 1).profile.experience).toEqual({ derivative: "none" });
    // The second time the question is not asked again.
    button(en.home);
    await share("Another options idea");
    await screen.findByText("Where would this money come from?");
    chip("Futures or options (F&O)");
    expect(screen.queryByText(en.experienceQuestion)).toBeNull();
  });

  it("asks how trading has been lately, trusts the answer for a day, and sends it", async () => {
    const fetchMock = stub(clarifyHints, pauseL2, clarifyHints);
    render(<App />);
    await share("Thinking of nifty options, deposit 15000");
    await screen.findByText("Where would this money come from?");
    chip("Futures or options (F&O)");
    chip(en.recentLossOptions.yes);
    chip(en.tradesOptions["6_20"]);
    fireEvent.click(screen.getByRole("button", { name: "The message mentions ₹15,000" }));
    chip("My savings");
    button(en.clarifyContinue);
    await screen.findByText(pauseL2.headline);
    expect(bodyOf(fetchMock, 1).profile.recent).toEqual({ post_loss: true, trades_this_week: "6_20" });
    button(en.home);
    await share("Another options idea");
    await screen.findByText("Where would this money come from?");
    chip("Futures or options (F&O)");
    expect(screen.queryByText(en.recentLossQuestion)).toBeNull();
  });

  it("does not ask about trading lately for a product that is not traded", async () => {
    stub(clarifyHints, pauseL2);
    render(<App />);
    await share("Join now");
    await screen.findByText("Where would this money come from?");
    chip("A mutual fund");
    expect(screen.queryByText(en.recentLossQuestion)).toBeNull();
    expect(screen.getByText(en.experienceQuestion)).toBeTruthy();
  });
});

describe("C: a warning shown first carries the questions that make it personal", () => {
  it("asks them inside the pause, and re-checks with the person's own numbers", async () => {
    const fetchMock = stub(pauseScam, pauseL2);
    render(<App />);
    await share("Guaranteed 3x return in 7 days. Join our Telegram group, act today! Pay 5000 to x");
    await screen.findByText(pauseScam.headline);
    expect(screen.getByText(en.refineTitle)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /The message mentions/ }));
    chip("My emergency money");
    chip("A scheme, app or platform");
    button(en.refineButton);
    await screen.findByText(pauseL2.headline);
    const second = bodyOf(fetchMock, 1);
    expect(second.input.content).toContain("Guaranteed 3x");
    expect(second.answers).toMatchObject({
      amount_inr: 5000,
      funding_source: "emergency_fund",
      product_class: "scheme_or_app",
    });
    expect(screen.queryByText(en.refineTitle)).toBeNull();
  });

  it("a pause with nothing left to ask shows no refine form", async () => {
    stub(pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL2.headline);
    expect(screen.queryByText(en.refineTitle)).toBeNull();
  });
});

describe("E: the person's own words, from their own message", () => {
  it("each signal quotes the words it rests on, and the message can be shown with them marked", async () => {
    stub(pauseScam);
    render(<App />);
    const text = "Guaranteed 3x return in 7 days. Join our Telegram group, act today! Pay 5000 to x";
    await share(text);
    await screen.findByText(pauseScam.headline);
    expect(screen.getByText("Guaranteed 3x return in 7 days.")).toBeTruthy();
    button(en.showMessage);
    const marks = within(screen.getByTestId("quoted-message")).getAllByText(/Guaranteed|Join our/);
    expect(marks.map((m) => m.tagName)).toEqual(["MARK", "MARK"]);
    button(en.hideMessage);
    expect(screen.queryByTestId("quoted-message")).toBeNull();
  });

  it("with no message text (a voice note or screenshot) the quotes stay but the message view is hidden", () => {
    render(
      <PauseCard
        pause={pauseScam as unknown as PauseResponse}
        onLearn={() => undefined}
        onReflect={() => undefined}
        onContinue={() => undefined}
        onRecover={() => undefined}
      />,
    );
    expect(screen.getByText("Guaranteed 3x return in 7 days.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: en.showMessage })).toBeNull();
  });
});

describe("F: choices that fit the decision", () => {
  async function toDecide(pause: unknown = pauseL2) {
    stub(pause);
    render(<App />);
    await share("a tip");
    await screen.findByText((pause as { headline: string }).headline);
    button(en.thinkThrough);
    button(en.reflectSkipButton);
  }

  it("reflection offers what pulled this person in, not a fixed list", async () => {
    stub(pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL2.headline);
    button(en.learnWhy.length ? en.thinkThrough : en.thinkThrough);
    expect(screen.getByRole("radio", { name: en.reflectByReason.GUARANTEED_RETURN_CLAIM })).toBeTruthy();
    expect(screen.queryByRole("radio", { name: "I want quick returns" })).toBeNull();
  });

  it("'Change the amount' re-checks with the new amount and counts as reconsidering", async () => {
    await toDecide();
    chip(en.actions.changed_amount);
    fireEvent.change(screen.getByPlaceholderText(en.amountPlaceholder), { target: { value: "3,000" } });
    button(en.changeAmountButton);
    await screen.findByText(pauseL2.headline);
    const fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>;
    expect(bodyOf(fetchMock, 1).answers.amount_inr).toBe(3000);
    button(pauseL2.override_label);
    button(en.done);
    expect(loadJournal()[0].entry).toMatchObject({ action: "changed_amount", overrode: false });
  });

  it("a bad amount is caught before any request", async () => {
    await toDecide();
    chip(en.actions.changed_amount);
    fireEvent.change(screen.getByPlaceholderText(en.amountPlaceholder), { target: { value: "lots" } });
    button(en.changeAmountButton);
    expect(screen.getByRole("alert").textContent).toBe(en.clarifyAmountInvalid);
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });

  it("a decision without a plan leads with 'Make a plan first'", async () => {
    await toDecide(pauseL3);
    const radios = screen.getAllByRole("radio").map((r) => r.getAttribute("aria-label"));
    expect(radios[0]).toBe(en.actions.set_plan);
  });
});

describe("A: writing a plan", () => {
  async function toPlan() {
    const fetchMock = stub(pauseL3, pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL3.headline);
    button(en.thinkThrough);
    button(en.reflectSkipButton);
    chip(en.actions.set_plan);
    return fetchMock;
  }

  it("needs at least one part, and says so", async () => {
    await toPlan();
    button(en.planSubmit);
    expect(screen.getByRole("alert").textContent).toBe(en.planEmpty);
  });

  it("sends only which parts exist, keeps the words and the range on the phone, and re-checks", async () => {
    const fetchMock = await toPlan();
    fireEvent.change(screen.getByLabelText(en.planReason), { target: { value: "PRIVATEWORDS reason" } });
    chip(en.planHorizonOptions.days);
    fireEvent.change(screen.getByLabelText(en.planReconsider), { target: { value: "PRIVATEWORDS exit" } });
    fireEvent.change(screen.getByLabelText(en.planFrom), { target: { value: "30000" } });
    fireEvent.change(screen.getByLabelText(en.planTo), { target: { value: "50000" } });
    button(en.planSubmit);
    await screen.findByText(en.planAddedNote);
    const second = bodyOf(fetchMock, 1);
    expect(second.answers.plan).toEqual({
      reason_given: true,
      horizon: "days",
      reconsider_condition_given: true,
    });
    expect(JSON.stringify(second)).not.toContain("PRIVATEWORDS");
    const [saved] = loadProfile().plans ?? [];
    expect(saved).toMatchObject({
      product_class: "derivative",
      amount_min_inr: 30000,
      amount_max_inr: 50000,
      horizon: "days",
    });
    expect(loadMemory().planNotes[saved.id].reason).toBe("PRIVATEWORDS reason");
    expect(second.profile.plans[0].id).toBe(saved.id); // later checks can compare with it
  });

  it("rejects a range that is not two whole amounts in order", async () => {
    await toPlan();
    chip(en.planHorizonOptions.weeks);
    fireEvent.change(screen.getByLabelText(en.planFrom), { target: { value: "50000" } });
    fireEvent.change(screen.getByLabelText(en.planTo), { target: { value: "30000" } });
    button(en.planSubmit);
    expect(screen.getByRole("alert").textContent).toBe(en.planRangeInvalid);
  });

  it("plans can be seen and removed under My rules", async () => {
    const fetchMock = await toPlan();
    chip(en.planHorizonOptions.weeks);
    fireEvent.change(screen.getByLabelText(en.planFrom), { target: { value: "1000" } });
    fireEvent.change(screen.getByLabelText(en.planTo), { target: { value: "2000" } });
    button(en.planSubmit);
    await screen.findByText(en.planAddedNote);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    button(en.home);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(en.myRules) }));
    expect(screen.getByText("₹1,000 to ₹2,000")).toBeTruthy();
    button(en.planRemove);
    expect(screen.getByText(en.plansEmpty)).toBeTruthy();
    expect(loadProfile().plans).toEqual([]);
  });
});

describe("F: waiting, and being asked about it later", () => {
  async function waitOnATip() {
    stub(pauseL2);
    render(<App />);
    await share("Guaranteed 3x return in 7 days.");
    await screen.findByText(pauseL2.headline);
    button(en.thinkThrough);
    button(en.reflectSkipButton);
    chip(en.actions.delayed);
    button(en.continue);
    button(en.done);
  }

  it("a decision to wait comes back on Home, with the person's own words", async () => {
    await waitOnATip();
    expect(screen.getByText(en.waitPendingTitle)).toBeTruthy();
    expect(screen.getByText("“Guaranteed 3x return in 7 days.”")).toBeTruthy();
    expect(screen.getByText(new RegExp(en.homeBack))).toBeTruthy();
  });

  it("the wait is as long as the person's own cooling-off rule", async () => {
    window.localStorage.setItem("ruko.profile.v1", JSON.stringify({ rules: { cooling_off_minutes: 15 } }));
    const before = Date.now();
    await waitOnATip();
    const [saved] = loadMemory().waits;
    const minutes = (new Date(saved.dueAt).getTime() - before) / 60_000;
    expect(minutes).toBeGreaterThan(14);
    expect(minutes).toBeLessThan(16);
  });

  it("'Look at it again' reopens it with their words and settles the wait", async () => {
    await waitOnATip();
    button(en.waitLookAgain);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Guaranteed 3x return in 7 days.");
    expect(loadMemory().waits[0].status).toBe("revisited");
  });

  it("'I've let it go' records that they dropped it", async () => {
    await waitOnATip();
    button(en.waitLetGo);
    expect(screen.queryByText(en.waitPendingTitle)).toBeNull();
    expect(loadJournal()[0].entry.action).toBe("dropped");
  });

  it("a person who chose not to keep the note gets no follow-up", async () => {
    stub(pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL2.headline);
    button(en.thinkThrough);
    button(en.reflectSkipButton);
    chip(en.actions.delayed);
    button(en.continue);
    button(en.dontKeep);
    expect(screen.queryByText(en.waitPendingTitle)).toBeNull();
  });
});

describe("F: Home follows what the person did", () => {
  it("asks whether a plan from a few days ago was followed, and records the answer", () => {
    addJournalRecord(entry({ plan: { reason_given: true, horizon: "weeks", reconsider_condition_given: true } }));
    window.localStorage.setItem("ruko.profile.v1", JSON.stringify({ rules: { max_share_of_savings_pct: 10 } }));
    render(<App />);
    expect(screen.getByText(en.planFollowTitle)).toBeTruthy();
    button(en.planYes);
    expect(screen.queryByText(en.planFollowTitle)).toBeNull();
    expect(loadJournal()[0].entry.plan_followed).toBe(true);
  });

  it("'Not yet' only puts the question off for this visit", () => {
    addJournalRecord(entry({ plan: { reason_given: true, horizon: "weeks", reconsider_condition_given: true } }));
    window.localStorage.setItem("ruko.profile.v1", JSON.stringify({ rules: { max_share_of_savings_pct: 10 } }));
    render(<App />);
    button(en.planNotYet);
    expect(screen.queryByText(en.planFollowTitle)).toBeNull();
    expect(loadJournal()[0].entry.plan_followed).toBeUndefined();
  });

  it("suggests setting a rule once there is history, and 'Not now' is remembered", () => {
    addJournalRecord(entry());
    const { unmount } = render(<App />);
    expect(screen.getByText(en.homeRulesNudgeTitle)).toBeTruthy();
    button(en.notNow);
    expect(screen.queryByText(en.homeRulesNudgeTitle)).toBeNull();
    unmount();
    render(<App />);
    expect(screen.queryByText(en.homeRulesNudgeTitle)).toBeNull();
  });

  it("a brand-new person sees the plain welcome and no suggestions", () => {
    render(<App />);
    expect(screen.getByText(en.homeEyebrow)).toBeTruthy();
    expect(screen.queryByText(en.homeRulesNudgeTitle)).toBeNull();
  });
});

describe("F: pace", () => {
  it("someone who keeps skipping reflection is offered the decision directly, with a way back", async () => {
    updateMemory((m) => ({ ...m, reflectSkipped: [true, true, true] }));
    stub(pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL2.headline);
    expect(screen.getByText(en.paceNote)).toBeTruthy();
    expect(screen.queryByRole("button", { name: en.thinkThrough })).toBeNull();
    button(en.decideNow);
    expect(screen.getByText(en.decideTitle)).toBeTruthy();
  });

  it("the reflection is still one tap away", async () => {
    updateMemory((m) => ({ ...m, reflectSkipped: [true, true, true] }));
    stub(pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL2.headline);
    button(en.reflectOptional);
    expect(screen.getByText(en.reflectTitle)).toBeTruthy();
  });

  it("a stronger pause is never shortened, whatever the pace", async () => {
    updateMemory((m) => ({ ...m, reflectSkipped: [true, true, true, true, true] }));
    stub(pauseL3);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL3.headline);
    expect(screen.getByRole("button", { name: en.thinkThrough })).toBeTruthy();
    expect(screen.queryByText(en.paceNote)).toBeNull();
  });

  it("skipping the reflection is remembered, using it is too", async () => {
    stub(pauseL2);
    render(<App />);
    await share("a tip");
    await screen.findByText(pauseL2.headline);
    button(en.thinkThrough);
    button(en.reflectSkipButton);
    expect(loadMemory().reflectSkipped).toEqual([true]);
    chip(en.actions.dropped);
    button(en.continue);
    button(en.done);
    await share("another");
    await screen.findByText(pauseL2.headline);
    button(en.thinkThrough);
    chip(en.reflectUnderstand);
    button(en.continue);
    expect(loadMemory().reflectSkipped).toEqual([true, false]);
  });
});

describe("F: a refusal or an unknown term leads somewhere", () => {
  it("advice about a product leads to what an amount would mean for the person's own money", async () => {
    const fetchMock = stub(refusal, clarifyHints);
    render(<App />);
    await share("Should I buy Reliance?");
    await screen.findByText(refusal.message);
    button(en.bridgeMoney);
    await screen.findByText("Where would this money come from?");
    const second = bodyOf(fetchMock, 1);
    expect(second.input.content).toBe(en.moneyCheckText);
    expect(second.answers).toEqual({ stage: "consider_action" });
  });

  it("a prediction leads to the arithmetic of a fall, never to a forecast", async () => {
    stub(refusalPrediction);
    render(<App />);
    await share("What will Nifty be next year?");
    await screen.findByText(refusalPrediction.message);
    expect(screen.queryByRole("button", { name: en.bridgeMoney })).toBeNull();
    button(en.bridgeFall);
    expect(await screen.findByText(en.calcToolTitle)).toBeTruthy();
    expect(screen.getByRole("radio", { name: en.calcTools.consequence }).getAttribute("aria-checked")).toBe("true");
  });

  it("an unknown term offers the terms Ruko knows, and tapping one asks about it", async () => {
    const known = (glossaryUnknown.related as { id: string; title: string }[]).find((c) => c.id === "ipo")!;
    const fetchMock = stub(glossaryUnknown, { ...glossaryUnknown, found: true, term: "ipo", title: known.title });
    render(<App />);
    await share("What is a Bollinger band?");
    await screen.findByText(en.glossaryMore);
    fireEvent.click(screen.getByRole("button", { name: known.title }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(bodyOf(fetchMock, 1).input.content).toBe(known.title);
    expect(bodyOf(fetchMock, 1).answers).toEqual({ stage: "learn" });
  });
});
