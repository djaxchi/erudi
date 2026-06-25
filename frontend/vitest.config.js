import { defineConfig } from "vitest/config";

// Unit tests for pure renderer logic (no DOM needed yet). Component-level testing
// (jsdom + @testing-library/react) is tracked as a follow-up — see issue #116.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.{js,jsx}"],
  },
});
