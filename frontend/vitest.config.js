import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Pure renderer logic uses the default `node` environment; component tests opt
// into jsdom per-file with a `// @vitest-environment jsdom` pragma (jsdom +
// @testing-library/react — the follow-up from issue #116). Static image imports
// are aliased to a stub so components that `require(png)` render in tests.
const assetStub = fileURLToPath(new URL("./src/test/assetStub.js", import.meta.url));

export default defineConfig({
  resolve: {
    alias: [{ find: /\.(png|jpe?g|gif|svg|webp|avif)$/, replacement: assetStub }],
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{js,jsx}"],
  },
});
