import { describe, it, expect } from "vitest";
import {
  downloadErrorMessage,
  DOWNLOAD_CANCELLED,
  DOWNLOAD_STALLED,
  DOWNLOAD_STALLED_MESSAGE,
} from "./downloadStatus";

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

describe("DOWNLOAD_STALLED (#315)", () => {
  it("is a distinct client-side status, never one of the backend terminal states", () => {
    expect(DOWNLOAD_STALLED).toBe("stalled");
    expect(DOWNLOAD_STALLED).not.toBe(DOWNLOAD_CANCELLED);
  });

  it("maps to the finalizing message, NOT the generic download-failed one", () => {
    // The bytes are on disk; only the finalization bookkeeping did not finish
    // (#291). Reporting "Download failed. Please try again." would be wrong and
    // would push the user into re-downloading gigabytes they already have.
    expect(downloadErrorMessage(DOWNLOAD_STALLED)).toBe(DOWNLOAD_STALLED_MESSAGE);
    expect(downloadErrorMessage(DOWNLOAD_STALLED)).not.toBe("Download failed. Please try again.");
    expect(DOWNLOAD_STALLED_MESSAGE).toMatch(/files have been saved/i);
  });
});
