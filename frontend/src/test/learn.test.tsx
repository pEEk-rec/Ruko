// Learn and the shared word layer, through the whole app: the Learn list needs no trigger, the
// lesson page, tappable words that open a short pop-up on every kind of result, the suggestion
// on quiet results, and the Home card. Fetch returns real backend responses.

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { LearnNext } from "../components/LearnNext";
import { Paragraphs, TermsProvider, Words } from "../components/Terms";
import { copyFor } from "../copy";
import { loadProfile } from "../services/device";
import { loadMemory, updateMemory } from "../services/memory";
import { splitByTerms } from "../utils/terms";
import type { LearnHubResponse, LessonResponse, TermHit } from "../types/api";
import glossary from "../fixtures/glossary.json";
import learnHub from "../fixtures/learn_hub.json";
import learnLesson from "../fixtures/learn_lesson.json";

const en = copyFor("en");
const hub = learnHub as unknown as LearnHubResponse;
const lessonBody = learnLesson as unknown as LessonResponse;
const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

/** Answer by route, so extra requests (Home asks for a lesson) never shift the sequence. */
function route(handlers: Record<string, unknown>) {
  const fetchMock = vi.fn(async (url: string) => {
    const hit = Object.keys(handlers).find((path) => String(url).endsWith(path));
    if (!hit) throw new Error(`unexpected ${url}`);
    return json(handlers[hit]);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
const bodyOf = (fetchMock: ReturnType<typeof vi.fn>, path: string) => {
  const call = fetchMock.mock.calls.find((c) => String(c[0]).endsWith(path));
  return call ? JSON.parse((call[1] as RequestInit).body as string) : null;
};
const button = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));

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
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const TERMS: TermHit[] = [
  { id: "sip", match: "SIP", title: "SIP (systematic investment plan)", brief: "A fixed amount at regular intervals." },
  { id: "nav", match: "NAV", title: "NAV (net asset value)", brief: "The value of one unit." },
];

describe("finding the words (units)", () => {
  it("taps each term at its first occurrence only, longest wording first, never overlapping", () => {
    const terms: TermHit[] = [
      { id: "sip", match: "SIP", title: "t", brief: "b" },
      { id: "sip", match: "SIPs", title: "t", brief: "b" },
      { id: "nav", match: "NAV", title: "t", brief: "b" },
    ];
    const parts = splitByTerms("Your SIPs and a SIP use NAV. NAV again.", terms);
    expect(parts.filter((p) => p.term).map((p) => p.text)).toEqual(["SIPs", "NAV"]);
    expect(parts.map((p) => p.text).join("")).toBe("Your SIPs and a SIP use NAV. NAV again.");
  });

  it("leaves text untouched when no term applies and caps the words per text", () => {
    expect(splitByTerms("nothing here", TERMS)).toEqual([{ text: "nothing here", term: null }]);
    const many: TermHit[] = ["a", "b", "c", "d", "e"].map((x) => ({ id: x, match: x, title: x, brief: x }));
    expect(splitByTerms("a b c d e", many).filter((p) => p.term)).toHaveLength(3);
  });
});

describe("a lesson taps each word once", () => {
  it("does not turn every paragraph into links for the same word", () => {
    render(
      <TermsProvider terms={TERMS}>
        <Paragraphs text={["A SIP is regular.", "The SIP adds up. NAV is a price.", "SIP again, and NAV."].join("\n\n")} />
      </TermsProvider>,
    );
    expect(screen.getAllByRole("button", { name: "SIP" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "NAV" })).toHaveLength(1);
  });
});

describe("the word pop-up", () => {
  function mount(onAsk?: (title: string) => void) {
    return render(
      <TermsProvider terms={TERMS} onAsk={onAsk}>
        <p>
          <Words text="A SIP buys units at the NAV." />
        </p>
      </TermsProvider>,
    );
  }

  it("opens a short explanation above the tapped word and closes on Escape", () => {
    mount();
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "SIP" }));
    const pop = screen.getByRole("dialog", { name: "SIP (systematic investment plan)" });
    expect(within(pop).getByText("A fixed amount at regular intervals.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "SIP" }).getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows one pop-up at a time and closes when tapping elsewhere", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "SIP" }));
    fireEvent.click(screen.getByRole("button", { name: "NAV" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("dialog").getAttribute("aria-label")).toContain("NAV");
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("offers the full explanation only when the screen can show one", () => {
    const onAsk = vi.fn();
    const { unmount } = mount(onAsk);
    fireEvent.click(screen.getByRole("button", { name: "NAV" }));
    fireEvent.click(screen.getByRole("button", { name: en.termMore }));
    expect(onAsk).toHaveBeenCalledWith("NAV (net asset value)");
    unmount();
    mount();
    fireEvent.click(screen.getByRole("button", { name: "NAV" }));
    expect(screen.queryByRole("button", { name: en.termMore })).toBeNull();
  });

  it("renders plain text when a screen has no words", () => {
    render(
      <TermsProvider terms={[]}>
        <Words text="Plain text" />
      </TermsProvider>,
    );
    expect(screen.getByText("Plain text")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("Learn needs no trigger", () => {
  it("opens from Home, lists every lesson by topic, and features the next one", async () => {
    const fetchMock = route({ "/v1/learn": hub });
    render(<App />);
    button(new RegExp(en.learnTile));
    await screen.findByText(en.learnHubIntro);
    expect(screen.getByText(en.learnProgress(hub.read_count, hub.total))).toBeTruthy();
    const featured = screen.getByRole("region", { name: en.learnFeatured });
    expect(within(featured).getByText(hub.featured!.title)).toBeTruthy();
    for (const group of hub.topics) {
      const section = screen.getByRole("region", { name: group.title });
      expect(within(section).getAllByRole("button")).toHaveLength(group.lessons.length);
    }
    expect(bodyOf(fetchMock, "/v1/learn").locale).toBe("en");
  });

  it("sends what the person said lately, so the order adapts (the same snapshot as every request)", async () => {
    updateMemory((m) => ({ ...m, recent: { postLoss: true, trades: "6_20", at: new Date().toISOString() } }));
    const fetchMock = route({ "/v1/learn": hub });
    render(<App />);
    button(new RegExp(en.learnTile));
    await screen.findByText(en.learnHubIntro);
    expect(bodyOf(fetchMock, "/v1/learn").profile.recent).toEqual({
      post_loss: true,
      trades_this_week: "6_20",
    });
  });

  it("shows the words people hear as tappable chips with a short explanation", async () => {
    route({ "/v1/learn": hub });
    render(<App />);
    button(new RegExp(en.learnTile));
    await screen.findByText(en.learnHubIntro);
    const word = hub.words.find((w) => w.id === "nav")!;
    fireEvent.click(screen.getByRole("button", { name: word.title }));
    expect(within(screen.getByRole("dialog")).getByText(word.brief)).toBeTruthy();
  });

  it("opens a lesson with tappable words, remembers it as read, and leads to the next one", async () => {
    const fetchMock = route({ "/v1/learn": hub, "/v1/learn/lesson": lessonBody });
    render(<App />);
    button(new RegExp(en.learnTile));
    await screen.findByText(en.learnHubIntro);
    fireEvent.click(screen.getAllByRole("button", { name: new RegExp(hub.topics[0].lessons[0].title) })[0]);
    await screen.findByRole("heading", { name: lessonBody.lesson.title });
    expect(bodyOf(fetchMock, "/v1/learn/lesson").lesson_id).toBe(hub.topics[0].lessons[0].id);
    const first = lessonBody.terms![0];
    fireEvent.click(screen.getByRole("button", { name: first.match }));
    expect(within(screen.getByRole("dialog")).getByText(first.brief)).toBeTruthy();
    await waitFor(() => expect(loadProfile().seen_lesson_ids).toContain(lessonBody.lesson.id));
    expect(screen.getByText(`${en.lessonNext}: ${lessonBody.next!.title}`)).toBeTruthy();
    expect(screen.getByRole("button", { name: en.lessonNext })).toBeTruthy();
    button(en.lessonBackToLearn);
    await screen.findByText(en.learnHubIntro);
  });

  it("says so calmly when the lessons cannot be fetched, and lets the person retry", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    render(<App />);
    button(new RegExp(en.learnTile));
    await screen.findByText(en.errors.backend_unavailable);
    route({ "/v1/learn": hub });
    button(en.tryAgain);
    await screen.findByText(en.learnHubIntro);
  });
});

describe("every result explains its own words", () => {
  it("a glossary answer has tappable words, a deeper lesson and the full-explanation link", async () => {
    route({ "/v1/analyze": glossary, "/v1/learn": hub });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: en.shareSomething }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "What is an IPO?" } });
    fireEvent.click(screen.getByRole("button", { name: en.composeSubmit }));
    await screen.findByText(en.glossaryEyebrow);
    const terms = (glossary as unknown as { terms: TermHit[] }).terms;
    expect(terms.length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: terms[0].match }));
    expect(within(screen.getByRole("dialog")).getByText(terms[0].brief)).toBeTruthy();
    expect(screen.getByRole("button", { name: en.termMore })).toBeTruthy();
    expect(screen.getByRole("region", { name: en.learnNextTitle })).toBeTruthy();
  });
});

describe("a lesson is offered even when nothing triggers one", () => {
  const topic = hub.featured!;

  it("shows the suggested lesson as a compact card that opens it", () => {
    const onOpen = vi.fn();
    render(<LearnNext topic={topic} onOpen={onOpen} />);
    expect(screen.getByText(topic.title)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: en.learnRead }));
    expect(onOpen).toHaveBeenCalledWith(topic.id);
  });

  it("renders nothing without a suggestion or without a way to open it", () => {
    const { container, rerender } = render(<LearnNext topic={null} onOpen={() => undefined} />);
    expect(container.textContent).toBe("");
    rerender(<LearnNext topic={topic} />);
    expect(container.textContent).toBe("");
  });
});

describe("Home suggests a lesson, gently", () => {
  it("shows one after a moment, and 'not now' hides it for the rest of today only", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    route({ "/v1/learn": hub });
    render(<App />);
    expect(screen.queryByRole("region", { name: en.homeLearnTitle })).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(1000));
    const card = await screen.findByRole("region", { name: en.homeLearnTitle });
    expect(within(card).getByText(hub.featured!.title)).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: en.notNow }));
    expect(screen.queryByRole("region", { name: en.homeLearnTitle })).toBeNull();
    const today = new Date().toISOString().slice(0, 10);
    expect(loadMemory().dismissed).toContain(`learn:${today}`);
  });

  it("asks for nothing if the person leaves Home straight away (no wasted request)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = route({ "/v1/learn": hub });
    render(<App />);
    button(new RegExp(en.workOutNumber));
    await act(() => vi.advanceTimersByTimeAsync(1500));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stays quiet when something the person did is waiting on them", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    updateMemory((m) => ({
      ...m,
      waits: [{
        id: "w1", entryId: "e1", createdAt: new Date().toISOString(), dueAt: new Date(Date.now() - 1000).toISOString(),
        note: "a tip", level: "L2", productClass: "scheme_or_app", status: "waiting",
      }],
    }));
    route({ "/v1/learn": hub });
    render(<App />);
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.queryByRole("region", { name: en.homeLearnTitle })).toBeNull();
    expect(screen.getByRole("region", { name: en.waitDueTitle })).toBeTruthy();
  });
});

describe("signals read as what a message is doing", () => {
  const signal = (code: string, role: string | null, label: string | null) =>
    ({ code, role, role_label: label, certainty: "likely", severity: "medium", text: code, reason_text: code, certainty_label: "Likely", quote: null }) as never;

  it("groups three or more signals under the backend's headings, in order of first appearance", async () => {
    const { groupSignals } = await import("../utils/signals");
    const groups = groupSignals([
      signal("A", "pressure", "Pushes you to act"),
      signal("B", "claims", "Makes promises or claims"),
      signal("C", "pressure", "Pushes you to act"),
    ]);
    expect(groups.map((g) => [g.label, g.signals.length])).toEqual([
      ["Pushes you to act", 2],
      ["Makes promises or claims", 1],
    ]);
  });

  it("keeps a short list, or a list with one role, as one plain list", async () => {
    const { groupSignals } = await import("../utils/signals");
    const two = [signal("A", "pressure", "P"), signal("B", "claims", "C")];
    expect(groupSignals(two)).toEqual([{ label: null, signals: two }]);
    const same = [signal("A", "pressure", "P"), signal("B", "pressure", "P"), signal("C", "pressure", "P")];
    expect(groupSignals(same)).toEqual([{ label: null, signals: same }]);
  });
});
