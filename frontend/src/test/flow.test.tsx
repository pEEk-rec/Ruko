// End-to-end flow tests with fetch mocked to return real backend responses.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { analyze, AppError } from "../services/api";
import { loadJournal } from "../services/device";
import { readSharedContent } from "../share/readSharedContent";
import clarifyFields from "../fixtures/clarify_fields.json";
import errorInvalid from "../fixtures/error_invalid.json";
import pauseL2 from "../fixtures/pause_l2.json";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const request = {
  input: { type: "text" as const, content: "x" },
  locale: "en" as const,
  profile: {},
  answers: {},
};

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(
    "ruko.settings.v1",
    JSON.stringify({ onboarded: true, locale: "en", largeText: false, style: "balanced" })
  );
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("api errors", () => {
  it("network failure becomes backend_unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    await expect(analyze(request)).rejects.toMatchObject({ kind: "backend_unavailable" });
  });

  it("the backend's error envelope maps to a calm category", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(errorInvalid, 422)));
    await expect(analyze(request)).rejects.toMatchObject({ kind: "invalid_request", code: "INVALID_REQUEST" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "OCR_UNAVAILABLE", message_key: "x", retryable: true } }, 503),
      ),
    );
    await expect(analyze(request)).rejects.toMatchObject({ kind: "reading_unavailable" });
  });

  it("a malformed 200 response is rejected, not rendered", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ kind: "pause", level: "L9" })));
    await expect(analyze(request)).rejects.toMatchObject({ kind: "invalid_response" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>oops</html>", { status: 200 })));
    await expect(analyze(request)).rejects.toMatchObject({ kind: "invalid_response" });
  });

  it("a slow backend times out", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      ),
    );
    await expect(analyze(request, 10)).rejects.toBeInstanceOf(AppError);
    await expect(analyze(request, 10)).rejects.toMatchObject({ kind: "timeout" });
  });
});

describe("full flow", () => {
  it("share → clarify → L2 pause → reflect → decide → journal", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(clarifyFields))
      .mockResolvedValueOnce(jsonResponse(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Share something" }));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Guaranteed 3x return in 7 days. Join our Telegram group, act today!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));

    // Clarify: all three questions on one screen, answered in any order, then sent together.
    await screen.findByText("How much are you thinking of putting in? (in rupees)");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "20000" } });
    fireEvent.click(screen.getByRole("radio", { name: "My emergency money" }));
    fireEvent.click(screen.getByRole("radio", { name: "A scheme, app or platform" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await screen.findByText(pauseL2.headline);
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(secondBody.answers).toEqual({
      amount_inr: 20000,
      funding_source: "emergency_fund",
      product_class: "scheme_or_app",
    });
    expect(secondBody.input.content).toContain("Guaranteed 3x");

    fireEvent.click(screen.getByRole("button", { name: "Think this through" }));
    // The reflection choices are picked for this decision (guaranteed pitch, unknown sender).
    expect(screen.queryByRole("radio", { name: "I want quick returns" })).toBeNull();
    expect(screen.getByRole("radio", { name: "Someone I don't know sent it" })).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "The promised return is tempting" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("radio", { name: "Wait for now" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await screen.findByText("Decision recorded.");
    expect(screen.getByText("I chose to wait.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));

    const journal = loadJournal();
    expect(journal).toHaveLength(1);
    expect(journal[0].entry).toMatchObject({
      level_shown: "L2",
      action: "delayed",
      overrode: false,
      pause_completed: true,
      could_state_why: true,
      product_class: "scheme_or_app",
      amount_inr: 20000,
    });
    expect(journal[0].entry.reason_codes).toContain("EMERGENCY_FUNDS");
    expect(screen.getByText("Before you act, take a moment.")).toBeTruthy();
  });

  it("continue anyway records an override; the note can be discarded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(pauseL2)));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Share something" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "some tip" } });
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));
    fireEvent.click(await screen.findByRole("button", { name: pauseL2.override_label }));
    await screen.findByText("I chose to go ahead.");
    fireEvent.click(screen.getByRole("button", { name: "Don't keep this note" }));
    expect(loadJournal()).toHaveLength(0);
  });

  it("the journal takes product class and source from the pause's event summary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(pauseL2)));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Share something" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "some tip" } });
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));
    fireEvent.click(await screen.findByRole("button", { name: pauseL2.override_label }));
    fireEvent.click(await screen.findByRole("button", { name: "Done" }));
    expect(loadJournal()[0].entry).toMatchObject({
      product_class: pauseL2.event.product_class,
      source_type: pauseL2.event.source_type,
      overrode: true,
    });
  });

  it("empty input is caught before any request", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Share something" }));
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));
    expect(screen.getByRole("alert").textContent).toContain("Paste a message");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("backend down shows a calm error with retry, never raw details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("ECONNREFUSED 127.0.0.1")));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Share something" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));
    await screen.findByText(/can't be reached right now/);
    expect(document.body.textContent).not.toContain("ECONNREFUSED");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("the 'think through a decision' entry tells the backend the stage", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Think through a decision" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Put 20k in an IPO" } });
    fireEvent.click(screen.getByRole("button", { name: "Look at this" }));
    await screen.findByText(pauseL2.headline);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string).answers).toEqual({ stage: "consider_action" });
  });

  it("shared content from the share target goes straight to analysis", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(pauseL2));
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/?text=Guaranteed%203x%20return");
    render(<App />);
    await screen.findByText(pauseL2.headline);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(window.location.search).toBe("");
  });
});

describe("share target parsing", () => {
  it("combines title, text and url without duplicates", () => {
    expect(readSharedContent("")).toBeNull();
    expect(readSharedContent("?text=hi&url=https://x.in")).toEqual({ type: "text", content: "hi\nhttps://x.in" });
    expect(readSharedContent("?url=https://x.in")).toEqual({ type: "link", content: "https://x.in" });
    expect(readSharedContent("?title=a&text=a")).toEqual({ type: "text", content: "a" });
  });
});
