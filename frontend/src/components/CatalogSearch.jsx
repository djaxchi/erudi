import React, { useRef } from "react";
import PropTypes from "prop-types";
import { useTranslation } from "react-i18next";
import { Search, X } from "lucide-react";

/**
 * Search box over the bundled catalog (#380). Controlled and synchronous: the
 * page owns the query, debounces it and does the matching (`searchCatalog`),
 * so this stays a plain input that works fully offline. Escape and the clear
 * button empty the query without dropping the focus, so a browse-and-refine
 * loop never leaves the keyboard.
 */
export default function CatalogSearch({ value, onChange }) {
  const { t } = useTranslation();
  const inputRef = useRef(null);

  const clear = () => {
    onChange("");
    inputRef.current?.focus();
  };

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      clear();
    }
  };

  return (
    <div className="flex items-center gap-2 rounded-xl border border-[var(--line-strong)] bg-[var(--surface)] px-3 py-2.5 focus-within:border-[var(--fit-good)] transition-colors">
      <Search className="w-4 h-4 text-[var(--ink-faint)] flex-shrink-0" />
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label={t("models:catalogSearch.label")}
        placeholder={t("models:catalogSearch.placeholder")}
        autoComplete="off"
        spellCheck={false}
        className="flex-1 min-w-0 bg-transparent border-0 text-sm text-[var(--ink)] placeholder-[var(--ink-faint)] focus:outline-none focus:ring-0 [&::-webkit-search-cancel-button]:appearance-none"
      />
      {value && (
        <button
          type="button"
          onClick={clear}
          aria-label={t("common:actions.clear")}
          className="text-[var(--ink-faint)] hover:text-[var(--ink)] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

CatalogSearch.propTypes = {
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};
