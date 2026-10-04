// The fictional broker demo. Uses real /v1/order-intent responses captured from the backend.

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrokerApp } from "../mock-broker/BrokerApp";
import { REASON_LABELS, reasonLabel } from "../mock-broker/labels";
import { loadJournal } from "../services/device";
import orderL0 from "../fixtures/order_intent_l0.json";
import orderL3 from "../fixtures/order_intent_l3.json";

function stubIntent(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const requestBody = (fetchMock: ReturnType<typeof vi.fn>) =>
  JSON.parse(fetchMock.mock.calls[0][1].body as string);

beforeEach(() => window.localStorage.clear());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("broker demo", () => {
  it("is plainly fictional: a banner, invented names, no real broker", () => {
    render(<BrokerApp />);
    expect(screen.getByText("Demo – not a real broker")).toBeTruthy();
    expect(screen.getByRole("option", { name: "Stock A" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Index option B" })).toBeTruthy();
  });

  it("sends only class, amount band, flags and the profile: no instrument, no user ID", async () => {
    const fetchMock = stubIntent(orderL0);
    render(<BrokerApp />);
    fireEvent.change(screen.getByLabelText("Instrument"), { target: { value: "derivative" } });
    fireEvent.change(screen.getByLabelText("Amount (₹)"), { target: { value: "5,000" } });
    fireEvent.click(screen.getByLabelText("Use leverage or margin"));
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    await screen.findByText("Demo order placed.");

    expect(fetchMock.mock.calls[0][0]).toBe("/v1/order-intent");
    const body = requestBody(fetchMock);
    expect(Object.keys(body).sort()).toEqual(
      ["amount_band", "borrowed_funds", "leveraged", "product_class", "profile"].sort(),
    );
    expect(body).toMatchObject({
      product_class: "derivative",
      amount_band: { min_inr: 5000, max_inr: 5000 },
      leveraged: true,
      borrowed_funds: false,
    });
    expect(JSON.stringify(body)).not.toMatch(/Index option B|Stock A|symbol|instrument|user_id|plan_matched/);
  });

  it("L0 passes silently: no sheet, and the order is noted in the journal", async () => {
    stubIntent(orderL0);
    render(<BrokerApp />);
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    await screen.findByText("Demo order placed.");
    expect(screen.queryByRole("dialog")).toBeNull();
    const [record] = loadJournal();
    expect(record.entry).toMatchObject({
      stage: "about_to_act",
      level_shown: "L0",
      action: "went_ahead",
      overrode: false,
      pause_completed: null,
      followed_own_rules: true,
    });
    expect(record.notes.origin).toBe("broker_demo");
  });

  it("L3 shows the sheet in plain words (never raw codes), and Place order anyway always works", async () => {
    stubIntent(orderL3);
    render(<BrokerApp />);
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    const sheet = await screen.findByRole("dialog");
    for (const code of orderL3.reason_codes) {
      expect(within(sheet).getByText(reasonLabel(code))).toBeTruthy();
      expect(sheet.textContent).not.toContain(code);
    }
    fireEvent.click(within(sheet).getByRole("button", { name: "Place order anyway" }));
    await screen.findByText("Demo order placed.");
    const [record] = loadJournal();
    expect(record.entry).toMatchObject({
      level_shown: "L3",
      action: "went_ahead",
      overrode: true,
      pause_completed: true,
      // a rule reason was shown and the user went ahead
      followed_own_rules: false,
    });
    expect(record.entry.reason_codes).toEqual(orderL3.reason_codes);
  });

  it("cancelling is also noted, and counts as not overriding", async () => {
    stubIntent(orderL3);
    render(<BrokerApp />);
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel the order" }));
    await screen.findByText("Order cancelled.");
    expect(loadJournal()[0].entry).toMatchObject({ action: "dropped", overrode: false, followed_own_rules: true });
  });

  it("journal entries use only the backend's JournalEntry fields, with a plain date", async () => {
    stubIntent(orderL3);
    render(<BrokerApp />);
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    fireEvent.click(await screen.findByRole("button", { name: "Place order anyway" }));
    await screen.findByText("Demo order placed.");
    const { entry } = loadJournal()[0];
    expect(entry.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(entry.id.length).toBeLessThanOrEqual(40);
    const allowed = [
      "id", "date", "stage", "product_class", "amount_inr", "source_type", "level_shown",
      "reason_codes", "action", "overrode", "override_reason_given", "pause_completed",
      "could_state_why", "followed_own_rules",
    ]; // prettier-ignore
    expect(Object.keys(entry).every((key) => allowed.includes(key))).toBe(true);
  });

  it("a bad amount is caught before any request, and an unreachable backend is calm", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);
    render(<BrokerApp />);
    fireEvent.change(screen.getByLabelText("Amount (₹)"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    expect(screen.getByRole("alert").textContent).toContain("whole rupee amount");
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Amount (₹)"), { target: { value: "2000" } });
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));
    await screen.findByText("Ruko could not be reached.");
    expect(loadJournal()).toHaveLength(0);
  });
});

describe("reason wording", () => {
  it("every label is a statement about the user's own setup, never a verdict or advice", () => {
    for (const text of Object.values(REASON_LABELS)) {
      expect(text).not.toMatch(/\b(scam|fraud|should|must|safe|legit|buy|sell)\b/i);
    }
    expect(reasonLabel("SOMETHING_NEW")).not.toContain("SOMETHING_NEW");
  });
});
