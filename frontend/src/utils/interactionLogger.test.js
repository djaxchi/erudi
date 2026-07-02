// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { describeTarget, buildInteractionEntry, truncateValue } from "./interactionLogger";

describe("truncateValue", () => {
  it("returns short values unchanged", () => {
    expect(truncateValue("hello")).toBe("hello");
    expect(truncateValue("", 10)).toBe("");
  });

  it("truncates long values with an overflow marker", () => {
    const long = "a".repeat(250);
    const out = truncateValue(long, 200);
    expect(out.startsWith("a".repeat(200))).toBe(true);
    expect(out.endsWith("… [+50]")).toBe(true);
  });

  it("coerces non-string values without throwing", () => {
    expect(truncateValue(42)).toBe("42");
    expect(truncateValue(null)).toBe("");
    expect(truncateValue(undefined)).toBe("");
  });
});

describe("describeTarget", () => {
  it("prefers aria-label over title over text over tag", () => {
    const button = document.createElement("button");
    button.setAttribute("aria-label", "Aria");
    button.setAttribute("title", "Title");
    button.textContent = "Text";
    expect(describeTarget(button).label).toBe("Aria");

    button.removeAttribute("aria-label");
    expect(describeTarget(button).label).toBe("Title");

    button.removeAttribute("title");
    expect(describeTarget(button).label).toBe("Text");

    button.textContent = "";
    button.id = "save";
    expect(describeTarget(button).label).toBe("button#save");
  });

  it("normalizes whitespace and caps text labels at 60 chars", () => {
    const button = document.createElement("button");
    button.textContent = `  spaced\n  out  ${"x".repeat(100)}`;
    const { label } = describeTarget(button);
    expect(label.startsWith("spaced out")).toBe(true);
    expect(label.length).toBe(60);
  });

  it("climbs to the nearest actionable ancestor", () => {
    const button = document.createElement("button");
    button.setAttribute("aria-label", "Send message");
    const span = document.createElement("span");
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    span.appendChild(icon);
    button.appendChild(span);
    document.body.appendChild(button);

    const described = describeTarget(icon);
    expect(described.label).toBe("Send message");
    expect(described.tag).toBe("button");
    expect(described.kind).toBe("button");
    document.body.removeChild(button);
  });

  it("stops climbing after the hop cap and falls back to the target", () => {
    // Actionable ancestor sits 7 parent hops above the clicked node — beyond the cap.
    const root = document.createElement("div");
    root.setAttribute("aria-label", "Too far");
    let parent = root;
    for (let i = 0; i < 7; i += 1) {
      const child = document.createElement("div");
      parent.appendChild(child);
      parent = child;
    }
    const described = describeTarget(parent);
    expect(described.label).toBe("div");
    expect(described.tag).toBe("div");
  });

  it("reports element kinds for inputs and links", () => {
    const input = document.createElement("input");
    input.type = "checkbox";
    expect(describeTarget(input).kind).toBe("input:checkbox");

    const link = document.createElement("a");
    link.textContent = "Docs";
    expect(describeTarget(link).kind).toBe("link");

    const div = document.createElement("div");
    div.setAttribute("role", "button");
    expect(describeTarget(div).kind).toBe("button");
  });

  it("never throws on detached nodes, text nodes, or nullish input", () => {
    const detached = document.createElement("span");
    expect(describeTarget(detached)).toEqual({ label: "span", tag: "span", kind: "element" });
    expect(describeTarget(document.createTextNode("x"))).toEqual({
      label: "unknown",
      tag: "unknown",
      kind: "unknown",
    });
    expect(describeTarget(null)).toEqual({ label: "unknown", tag: "unknown", kind: "unknown" });
    expect(describeTarget(undefined)).toEqual({
      label: "unknown",
      tag: "unknown",
      kind: "unknown",
    });
  });
});

describe("buildInteractionEntry", () => {
  it("builds a timestamped entry with route, target, and extra fields", () => {
    const button = document.createElement("button");
    button.setAttribute("aria-label", "Apply");
    const entry = buildInteractionEntry("click", button, "/erudi/models", { key: "Enter" });
    expect(entry.ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    expect(entry.type).toBe("click");
    expect(entry.route).toBe("/erudi/models");
    expect(entry.target.label).toBe("Apply");
    expect(entry.key).toBe("Enter");
  });
});
