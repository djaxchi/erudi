import { describe, it, expect } from "vitest";
import { createMainTranslator } from "./mainTranslator";

describe("createMainTranslator (Electron main process)", () => {
  it("starts in the requested language and resolves keys from the main namespace", () => {
    const tr = createMainTranslator("fr");
    expect(tr.language).toBe("fr");
    expect(tr.t("menu.help.clearAllData")).toBe("Effacer toutes les données…");
  });

  it("defaults to English for unknown initial codes", () => {
    const tr = createMainTranslator("de");
    expect(tr.language).toBe("en");
    expect(tr.t("menu.help.clearAllData")).toBe("Clear All Data...");
  });

  it("switches language and reports whether anything changed", () => {
    const tr = createMainTranslator("en");
    expect(tr.setLanguage("es")).toBe(true);
    expect(tr.language).toBe("es");
    expect(tr.setLanguage("es")).toBe(false);
    expect(tr.setLanguage("nope")).toBe(false);
    expect(tr.language).toBe("es");
  });

  it("interpolates {{variables}}", () => {
    const tr = createMainTranslator("en");
    expect(tr.t("dialogs.openDataFolderFailed", { error: "EACCES" })).toBe(
      "Failed to open data folder: EACCES"
    );
  });

  it("falls back to English for a missing key, then to the key itself", () => {
    const tr = createMainTranslator("zh");
    expect(tr.t("menu.help.learnMore")).toBe("了解更多");
    expect(tr.t("does.not.exist")).toBe("does.not.exist");
  });
});
