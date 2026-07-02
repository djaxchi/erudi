import React, { useState, useMemo } from "react";
import PropTypes from "prop-types";
import { Search } from "lucide-react";
import ExploreModelCard from "./ExploreModelCard";
import { rankByFit } from "../utils/hardwareFit";
import apiClient from "../services/api/client";
import { createLogger } from "../utils/logger";

const log = createLogger("HuggingFaceSearch");

// Starting points that map to real capabilities people look for.
const SUGGESTIONS = ["coding", "reasoning", "vision", "tiny", "uncensored", "multilingual"];

/**
 * Live Hugging Face search, reframed as a first-class discovery tool (#122):
 * it searches all of HF — beyond the curated catalog — but only for models that
 * run on this machine's engine, and ranks hits by how well they fit the hardware
 * budget. Empty and error states give direction rather than mood.
 */
export default function HuggingFaceSearchPanel({ range, onDownload, onInfo }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null); // null = not searched yet
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchedTerm, setSearchedTerm] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [sortBy, setSortBy] = useState("fit");

  const SORT_OPTIONS = [
    { value: "fit", label: "Best fit" },
    { value: "downloads", label: "Most downloads" },
    { value: "likes", label: "Most liked" },
    { value: "smallest", label: "Smallest" },
    { value: "largest", label: "Largest" },
  ];

  const sortedResults = useMemo(() => {
    if (!results) return results;
    const r = [...results];
    if (sortBy === "fit") return r; // already ranked by fit from rankByFit
    if (sortBy === "downloads") return r.sort((a, b) => (b.downloads || 0) - (a.downloads || 0));
    if (sortBy === "likes") return r.sort((a, b) => (b.likes || 0) - (a.likes || 0));
    if (sortBy === "smallest")
      return r.sort((a, b) => (a.param_size || Infinity) - (b.param_size || Infinity));
    if (sortBy === "largest") return r.sort((a, b) => (b.param_size || 0) - (a.param_size || 0));
    return r;
  }, [results, sortBy]);

  const clear = () => {
    setResults(null);
    setError("");
    setSearchedTerm("");
  };

  const runSearch = async (term) => {
    const q = (term ?? query).trim();
    if (!q) {
      return;
    }
    setCollapsed(false);
    setQuery(q);
    setSearchedTerm(q);
    setError("");
    setSortBy("fit");
    // Offline guard: searching Hugging Face needs the internet, so say so plainly
    // instead of returning an empty "no matches" or throwing.
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setResults([]);
      setError("No internet connection for the moment.");
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.get(`/llms/search/huggingface?q=${encodeURIComponent(q)}`);
      const mapped = data.map((m) => ({
        name: m.name,
        link: m.link,
        category: m.category,
        param_size: m.param_size,
        quantized: m.quantized,
        gated: m.gated,
        runnable: true,
        // Details-modal fields, from the search hit.
        parameters: m.param_size ? `${m.param_size}B` : "Unknown",
        downloads: m.downloads ? String(m.downloads) : "Unknown",
        likes: m.likes ? String(m.likes) : "Unknown",
        pipeline: m.pipeline_tag || "Unknown",
      }));
      setResults(rankByFit(mapped, range));
    } catch (err) {
      log.error("HF search failed:", err);
      setError("No internet connection for the moment.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5">
      <span className="eyebrow !text-[var(--fit-good)]">Search Hugging Face</span>
      <p className="text-[13px] text-[var(--ink-dim)] mt-1.5 mb-4 max-w-xl">
        Look beyond the curated list. We search every model that runs on your engine and rank them
        by how well they fit your machine.
      </p>

      {/* Search field */}
      <div className="flex items-center gap-2 rounded-xl border border-[var(--line-strong)] bg-[var(--canvas)] px-3 py-2.5 focus-within:border-[var(--fit-good)] transition-colors">
        <Search className="w-4 h-4 text-[var(--ink-faint)] flex-shrink-0" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
          placeholder={'Try "qwen coder", "a tiny model", "vision"…'}
          className="flex-1 bg-transparent border-0 text-sm text-[var(--ink)] placeholder-[var(--ink-faint)] focus:outline-none focus:ring-0"
        />
        <button
          onClick={() => runSearch()}
          disabled={!query.trim() || loading}
          className="rounded-lg bg-[var(--fit-good)] text-[#07241d] px-4 py-1.5 text-[13px] font-medium transition-[filter] hover:brightness-110 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </div>

      {/* Suggestion chips */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="mono text-[11px] text-[var(--ink-faint)] mr-1">try</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => runSearch(s)}
            className="mono text-[11px] rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--ink-dim)] hover:text-[var(--ink)] hover:border-[var(--line-strong)] transition-colors"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Results */}
      {(loading || results !== null) && (
        <div className="mt-5 pt-5 border-t border-[var(--line)]">
          {loading ? (
            <div className="flex items-center gap-2 text-[var(--ink-faint)] mono text-xs py-6 justify-center">
              <span className="w-2 h-2 rounded-full bg-[var(--fit-good)] animate-pulse" />
              searching hugging face for &ldquo;{query}&rdquo;…
            </div>
          ) : error ? (
            <p className="text-[var(--fit-tight)] text-sm py-3">{error}</p>
          ) : results.length > 0 ? (
            <>
              <div className="flex items-center gap-3 mb-3 flex-wrap">
                <span className="eyebrow">
                  {results.length} results for &ldquo;{searchedTerm}&rdquo;
                </span>
                <span className="h-px flex-1 bg-white/10" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="mono text-[11px] rounded-lg border border-[var(--line)] bg-[var(--canvas)] text-[var(--ink-dim)] px-2 py-1 focus:outline-none focus:border-[var(--fit-good)] transition-colors cursor-pointer"
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setCollapsed((c) => !c)}
                  className="mono text-[11px] text-[var(--ink-dim)] hover:text-[var(--fit-good)] transition-colors"
                >
                  {collapsed ? "Show" : "Collapse"}
                </button>
                <button
                  onClick={clear}
                  className="mono text-[11px] text-[var(--ink-dim)] hover:text-[var(--ink)] transition-colors"
                >
                  Clear
                </button>
              </div>
              {!collapsed && (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 max-h-[560px] overflow-y-auto custom-scroll pr-1">
                  {sortedResults.map((model) => (
                    <ExploreModelCard
                      key={`hf-${model.link}`}
                      model={model}
                      range={range}
                      onDownload={onDownload}
                      onInfo={onInfo}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="text-[var(--ink-dim)] text-sm py-3">
              Nothing runnable matched &ldquo;{searchedTerm}&rdquo;. Try a broader term, or a family
              name like &ldquo;qwen&rdquo; or &ldquo;llama&rdquo;.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

HuggingFaceSearchPanel.propTypes = {
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
  onDownload: PropTypes.func,
  onInfo: PropTypes.func,
};
