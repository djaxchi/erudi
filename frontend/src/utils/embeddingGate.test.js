import { describe, it, expect } from "vitest";
import { GATE, gateStateFromStatus, shouldPoll, isGateBlocking } from "./embeddingGate";

describe("gateStateFromStatus", () => {
  it("hides the gate when the model is present at open (not mid-download)", () => {
    expect(gateStateFromStatus({ available: true }, GATE.CHECKING)).toBe(GATE.HIDDEN);
    expect(gateStateFromStatus({ available: true }, GATE.PROMPT)).toBe(GATE.HIDDEN);
  });

  it("shows the success state only when a download just finished", () => {
    expect(gateStateFromStatus({ available: true }, GATE.DOWNLOADING)).toBe(GATE.DONE);
  });

  it("shows the spinner while a download is in flight", () => {
    expect(gateStateFromStatus({ available: false, downloading: true }, GATE.PROMPT)).toBe(
      GATE.DOWNLOADING
    );
  });

  it("enters downloading directly if a download is already running at open", () => {
    // e.g. resumed after navigating away and back.
    expect(gateStateFromStatus({ available: false, downloading: true }, GATE.CHECKING)).toBe(
      GATE.DOWNLOADING
    );
  });

  it("surfaces an error when the last download failed", () => {
    expect(
      gateStateFromStatus(
        { available: false, downloading: false, error: "network down" },
        GATE.DOWNLOADING
      )
    ).toBe(GATE.ERROR);
  });

  it("prompts when the model is absent and idle", () => {
    expect(
      gateStateFromStatus({ available: false, downloading: false, error: null }, GATE.CHECKING)
    ).toBe(GATE.PROMPT);
  });

  it("is defensive against a missing status", () => {
    expect(gateStateFromStatus(undefined, GATE.CHECKING)).toBe(GATE.PROMPT);
    expect(gateStateFromStatus(null, GATE.CHECKING)).toBe(GATE.PROMPT);
  });
});

describe("shouldPoll", () => {
  it("polls only while downloading", () => {
    expect(shouldPoll(GATE.DOWNLOADING)).toBe(true);
    for (const s of [GATE.CHECKING, GATE.PROMPT, GATE.DONE, GATE.ERROR, GATE.HIDDEN]) {
      expect(shouldPoll(s)).toBe(false);
    }
  });
});

describe("isGateBlocking", () => {
  it("blocks the page for every visible modal state", () => {
    for (const s of [GATE.PROMPT, GATE.DOWNLOADING, GATE.DONE, GATE.ERROR]) {
      expect(isGateBlocking(s)).toBe(true);
    }
  });

  it("does not block while checking or when hidden", () => {
    expect(isGateBlocking(GATE.CHECKING)).toBe(false);
    expect(isGateBlocking(GATE.HIDDEN)).toBe(false);
  });
});
