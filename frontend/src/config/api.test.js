import { describe, it, expect } from "vitest";
import { API_BASE_URL, setBackendPort, getApiBaseUrl } from "./api.js";

// The renderer follows the backend's actually-resolved port: setBackendPort
// swaps the live binding, and bogus/no-op ports are ignored.

describe("config/api setBackendPort", () => {
  it("defaults to the canonical 27182 port", () => {
    expect(API_BASE_URL).toBe("http://127.0.0.1:27182/erudi");
    expect(getApiBaseUrl()).toBe(API_BASE_URL);
  });

  it("ignores a non-numeric port", () => {
    setBackendPort("not-a-port");
    expect(getApiBaseUrl()).toContain(":27182/");
  });

  it("adopts a resolved port and stays put on a same-port repeat", () => {
    setBackendPort(27185);
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:27185/erudi");

    setBackendPort("27185"); // same port again, as a string -> no change path
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:27185/erudi");

    setBackendPort(27186);
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:27186/erudi");
  });
});
