// @vitest-environment jsdom
/**
 * Connectivity as the app knows it, without asking anyone.
 *
 * The status pill used to learn whether the machine was online by having the
 * backend send an empty request to a third party every 45 seconds. That handed
 * a stranger a per-machine record of when Erudi runs, so the signal now comes
 * from the operating system's own link state plus the requests the app already
 * makes. The failure modes pinned here: a link that drops must show up at once
 * rather than up to a poll later, and a request that dies at the network layer
 * must be believed even while the OS still claims a link.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  isNetworkOnline,
  reportNetworkFailure,
  reportNetworkSuccess,
  subscribeNetworkStatus,
} from "./networkStatus";

/** Set navigator.onLine and fire the matching window event, as a browser does. */
function setLink(up) {
  Object.defineProperty(window.navigator, "onLine", { value: up, configurable: true });
  window.dispatchEvent(new window.Event(up ? "online" : "offline"));
}

let unsubscribe = null;

beforeEach(() => {
  setLink(true);
  reportNetworkSuccess();
});

afterEach(() => {
  if (unsubscribe) unsubscribe();
  unsubscribe = null;
  setLink(true);
  reportNetworkSuccess();
});

describe("networkStatus", () => {
  it("reads online from the operating system, with no request", () => {
    expect(isNetworkOnline()).toBe(true);
    setLink(false);
    expect(isNetworkOnline()).toBe(false);
  });

  it("tells subscribers the moment the link drops or comes back", () => {
    const seen = [];
    unsubscribe = subscribeNetworkStatus((online) => seen.push(online));

    setLink(false);
    setLink(true);

    expect(seen).toEqual([false, true]);
  });

  it("believes a failed request even while the machine claims a link", () => {
    const seen = [];
    unsubscribe = subscribeNetworkStatus((online) => seen.push(online));

    reportNetworkFailure();

    expect(isNetworkOnline()).toBe(false);
    expect(seen).toEqual([false]);
  });

  it("recovers once a request goes through again", () => {
    reportNetworkFailure();
    expect(isNetworkOnline()).toBe(false);

    reportNetworkSuccess();

    expect(isNetworkOnline()).toBe(true);
  });

  it("clears a past request failure when the link comes back", () => {
    reportNetworkFailure();
    setLink(false);
    setLink(true);

    expect(isNetworkOnline()).toBe(true);
  });

  it("does not repeat itself when the same signal arrives twice", () => {
    const seen = [];
    unsubscribe = subscribeNetworkStatus((online) => seen.push(online));

    reportNetworkFailure();
    reportNetworkFailure();
    reportNetworkSuccess();
    reportNetworkSuccess();

    expect(seen).toEqual([false, true]);
  });

  it("stops calling a listener that unsubscribed", () => {
    const listener = vi.fn();
    subscribeNetworkStatus(listener)();

    setLink(false);

    expect(listener).not.toHaveBeenCalled();
  });
});
