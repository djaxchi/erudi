import { describe, it, expect } from "vitest";
import { isSupportedKbFile, SUPPORTED_KB_EXTENSIONS, KB_ACCEPT_ATTR } from "./kbFormats";

describe("isSupportedKbFile", () => {
  it("accepts every document format the ingestion pipeline extracts", () => {
    ["report.pdf", "notes.txt", "contract.docx", "data.xlsx", "table.csv", "readme.md"].forEach(
      (f) => expect(isSupportedKbFile(f)).toBe(true)
    );
  });

  it("is case-insensitive", () => {
    expect(isSupportedKbFile("REPORT.PDF")).toBe(true);
    expect(isSupportedKbFile("Notes.Md")).toBe(true);
  });

  it("rejects unsupported or extensionless files", () => {
    ["photo.png", "archive.zip", "binary.exe", "noext"].forEach((f) =>
      expect(isSupportedKbFile(f)).toBe(false)
    );
  });

  it("rejects empty/nullish names", () => {
    expect(isSupportedKbFile("")).toBe(false);
    expect(isSupportedKbFile(undefined)).toBe(false);
    expect(isSupportedKbFile(null)).toBe(false);
  });
});

describe("KB_ACCEPT_ATTR", () => {
  it("lists every supported extension for the file picker", () => {
    SUPPORTED_KB_EXTENSIONS.forEach((ext) => expect(KB_ACCEPT_ATTR).toContain(ext));
  });
});
