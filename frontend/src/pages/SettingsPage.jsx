import React from "react";
import { Globe } from "lucide-react";
import Sidebar from "../components/Sidebar";
import ToggleSwitch from "../components/ToggleSwitch";
import { useUserSettings } from "../shared/hooks/api";
import { createLogger } from "../utils/logger";

const log = createLogger("SettingsPage");

/**
 * App-wide settings page (gear icon in the sidebar rail).
 *
 * First section: the global Web Search default. Enabling it lets tool-capable
 * models search the web; the searched query is sent to external search
 * engines, so it ships OFF by default and new conversations inherit whatever
 * the user picks here (each conversation then owns its own toggle).
 */
export default function SettingsPage() {
  const { settings, loading, updateSettings } = useUserSettings();
  const webSearchEnabled = settings?.web_search_enabled ?? false;

  const handleWebSearchToggle = async (next) => {
    try {
      await updateSettings({ web_search_enabled: next });
    } catch (error) {
      log.error("Failed to update the web search setting", error);
    }
  };

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />
      <main className="flex-1 bg-[var(--canvas)] relative custom-scroll overflow-auto">
        <div className="mx-auto max-w-3xl px-8 py-10 space-y-9">
          <header className="rise">
            <span className="eyebrow">Application</span>
            <h1 className="text-2xl font-semibold text-[var(--ink)] tracking-tight mt-1.5">
              Settings
            </h1>
            <p className="text-[13px] text-[var(--ink-dim)] mt-1.5">
              Preferences that apply across the whole app.
            </p>
          </header>

          <section className="relative overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--surface)] rise">
            <div
              className="pointer-events-none absolute -right-24 -top-24 w-72 h-72 rounded-full blur-3xl"
              style={{
                background: "radial-gradient(circle, rgba(52,214,165,0.10), transparent 70%)",
              }}
            />
            <div className="relative p-6">
              <div className="flex items-start justify-between gap-6">
                <div className="flex items-start gap-3.5">
                  <div className="mt-0.5 rounded-xl border border-[var(--line)] bg-[var(--surface-2)] p-2.5">
                    <Globe className="w-5 h-5 text-[var(--fit-good)]" />
                  </div>
                  <div>
                    <h2 className="text-[15px] font-semibold text-[var(--ink)] tracking-tight">
                      Web Search
                    </h2>
                    <p className="text-[13px] text-[var(--ink-dim)] mt-1.5 max-w-md leading-relaxed">
                      Let models that support tools search the web when a question needs current or
                      external facts. When the model decides to search, the searched query is sent
                      to external search engines — nothing else leaves your machine.
                    </p>
                    <p className="text-[12px] text-[var(--ink-faint)] mt-2.5 leading-relaxed">
                      Off by default. New conversations inherit this setting; each conversation
                      keeps its own toggle afterwards.
                    </p>
                  </div>
                </div>
                <div className="pt-1">
                  <ToggleSwitch
                    checked={webSearchEnabled}
                    onChange={handleWebSearchToggle}
                    label="Web search"
                    disabled={loading}
                  />
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
