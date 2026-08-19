import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Pure renderer logic uses the default `node` environment; component tests opt
// into jsdom per-file with a `// @vitest-environment jsdom` pragma (jsdom +
// @testing-library/react — the follow-up from issue #116). Static image imports
// are aliased to a stub so components that `require(png)` or `import png` render
// in tests. The regex must swallow the WHOLE id: Vite applies a RegExp alias as
// `id.replace(find, replacement)`, so matching only the extension would leave the
// original path prefixed to the stub and break static ESM imports.
const assetStub = fileURLToPath(new URL("./src/test/assetStub.js", import.meta.url));

export default defineConfig({
  resolve: {
    alias: [{ find: /^.*\.(png|jpe?g|gif|svg|webp|avif)$/, replacement: assetStub }],
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{js,jsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{js,jsx}"],
      exclude: [
        // Test files and their shared helpers/stubs are not product code.
        "src/**/*.test.{js,jsx}",
        "src/test/**",
        // Electron process-level entrypoints: main.js and preload.js run in the
        // Electron main/preload processes (app lifecycle, window management,
        // IPC wiring, auto-update plumbing) and cannot be meaningfully
        // unit-tested under jsdom/node. Their risky logic is extracted into
        // src/utils/backend*.js (tested); the wiring itself is covered by the
        // full-app build+boot smoke gate in CI. renderer.js is the webpack
        // bootstrap that only mounts <App /> into the DOM.
        "src/main.js",
        "src/preload.js",
        "src/renderer.js",
      ],
      reporter: ["text", "text-summary"],
    },
  },
});
