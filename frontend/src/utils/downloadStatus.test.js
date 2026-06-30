import { describe, it, expect } from "vitest";
import { downloadErrorMessage, DOWNLOAD_CANCELLED } from "./downloadStatus";

describe("downloadErrorMessage", () => {
  it("returns null for a user-initiated cancellation (a cancel is not a failure)", () => {
    expect(downloadErrorMessage(DOWNLOAD_CANCELLED)).toBeNull();
    expect(downloadErrorMessage("cancelled")).toBeNull();
  });

  it("returns a failure message for any real error reason", () => {
    expect(downloadErrorMessage("Server responded with 500")).toBe(
      "Download failed. Please try again."
    );
    expect(downloadErrorMessage(undefined)).toBe("Download failed. Please try again.");
    expect(downloadErrorMessage(null)).toBe("Download failed. Please try again.");
  });
});

describe("DOWNLOAD_CANCELLED", () => {
  it("matches the status string the poll/cancel path uses", () => {
    expect(DOWNLOAD_CANCELLED).toBe("cancelled");
  });
});
