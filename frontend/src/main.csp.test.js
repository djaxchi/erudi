/**
 * The window's Content-Security-Policy, pinned as text.
 *
 * Two copies ship: the response header main.js installs (dev, http://) and the
 * <meta http-equiv> webpack injects into index.html (prod, file://, where
 * onHeadersReceived never fires). Both must agree, and neither may allow
 * `https:` images: a model that writes a markdown image link into an answer, or
 * a knowledge-base document that contains one, would make the window fetch that
 * image and hand the user's IP address to a host they never chose. Nothing in
 * the interface needs remote images -- the logo is bundled and attachments are
 * `data:` URLs -- so the scheme is absent on purpose and this test fails if it
 * comes back.
 *
 * main.js runs in the Electron main process and cannot be imported here, so the
 * policy is read from the source text, the same way QA would read it.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const read = (relative) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

/**
 * Every `img-src` directive declared in a source file. Matching requires the
 * quoted source list that starts a real directive, so prose about `img-src` in
 * a comment is not mistaken for policy.
 */
function imgSrcDirectives(source) {
  const found = Array.from(source.matchAll(/img-src\s+'[^;]*/g), (m) => m[0].trim());
  expect(found.length, "no img-src directive found").toBeGreaterThan(0);
  return found;
}

describe("Content-Security-Policy", () => {
  const header = read("./main.js");
  const meta = read("../webpack.config.js");

  it("does not let the main-process header load images from remote hosts", () => {
    expect(imgSrcDirectives(header)).toEqual(["img-src 'self' data:"]);
  });

  it("does not let the packaged document load images from remote hosts", () => {
    expect(imgSrcDirectives(meta)).toEqual(["img-src 'self' data:"]);
  });

  it("still allows the bundled logo and data: attachments in both copies", () => {
    for (const directive of [...imgSrcDirectives(header), ...imgSrcDirectives(meta)]) {
      expect(directive).toContain("'self'");
      expect(directive).toContain("data:");
    }
  });
});
