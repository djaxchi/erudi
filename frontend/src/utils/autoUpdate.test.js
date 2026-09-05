// @vitest-environment jsdom
/**
 * Handing the persisted automatic-update preference to the Electron main
 * process.
 *
 * Main owns electron-updater but has no database; the renderer owns the
 * setting. If the preference never reaches main, one of two failures follows:
 * a user who refused updates keeps getting them, or -- worse for everyone else
 * -- a hiccup reading the setting silently strands the app on its current
 * version. So the bridge is told something on every path, and "enabled" is what
 * an unreadable setting resolves to.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { syncAutoUpdateWithMain } from "./autoUpdate";

let setAutoUpdateEnabled;

beforeEach(() => {
  setAutoUpdateEnabled = vi.fn();
  window.updaterAPI = { setAutoUpdateEnabled };
});

afterEach(() => {
  delete window.updaterAPI;
  vi.clearAllMocks();
});

describe("syncAutoUpdateWithMain", () => {
  it("lets updates through when the user has not refused them", async () => {
    const client = { get: vi.fn().mockResolvedValue({ auto_update_enabled: true }) };

    await expect(syncAutoUpdateWithMain(client)).resolves.toBe(true);

    expect(client.get).toHaveBeenCalledWith("/user_settings/");
    expect(setAutoUpdateEnabled).toHaveBeenCalledWith(true);
  });

  it("tells main to stop when the user refused them", async () => {
    const client = { get: vi.fn().mockResolvedValue({ auto_update_enabled: false }) };

    await expect(syncAutoUpdateWithMain(client)).resolves.toBe(false);

    expect(setAutoUpdateEnabled).toHaveBeenCalledWith(false);
  });

  it("keeps updates on when the settings request fails", async () => {
    const client = { get: vi.fn().mockRejectedValue(new Error("backend down")) };

    await expect(syncAutoUpdateWithMain(client)).resolves.toBe(true);

    expect(setAutoUpdateEnabled).toHaveBeenCalledWith(true);
  });

  it("keeps updates on when the backend answers without the field", async () => {
    const client = { get: vi.fn().mockResolvedValue({ language: "en" }) };

    await expect(syncAutoUpdateWithMain(client)).resolves.toBe(true);

    expect(setAutoUpdateEnabled).toHaveBeenCalledWith(true);
  });

  it("does not throw outside Electron, where there is no bridge", async () => {
    delete window.updaterAPI;
    const client = { get: vi.fn().mockResolvedValue({ auto_update_enabled: false }) };

    await expect(syncAutoUpdateWithMain(client)).resolves.toBe(false);
  });
});
