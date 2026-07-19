import React from "react";
import PropTypes from "prop-types";
import { Globe } from "lucide-react";
import { groupByCategory } from "../utils/modelCatalog";

/**
 * Left-rail index for the explore panel. With discovery living in the main panel,
 * this is its table of contents: Recommended, Search Hugging Face, every capability
 * with a live count, and Community. Each row scrolls the panel to that section, so
 * the rail navigates the page instead of duplicating it. Header styled to match the
 * Local Models section above it.
 */
function Row({ label, count, onClick, accent }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm text-left transition-colors hover:bg-gray-700/20 ${
        accent ? "text-emerald-300 hover:text-emerald-200" : "text-gray-300 hover:text-white"
      }`}
    >
      <span className="flex-1 truncate">{label}</span>
      {typeof count === "number" && <span className="text-xs text-gray-500">{count}</span>}
    </button>
  );
}

Row.propTypes = {
  label: PropTypes.string.isRequired,
  count: PropTypes.number,
  onClick: PropTypes.func,
  accent: PropTypes.bool,
};

export default function ExploreIndex({
  models,
  communityCount,
  hasTested,
  hasRecommended,
  loading,
  onJump,
}) {
  const groups = groupByCategory(models);

  return (
    <div className="text-gray-200">
      {/* Header matches the Local Models section header (icon + bold title) */}
      <div className="flex items-center gap-3 px-4 py-3">
        <Globe className="w-5 h-5 text-white" />
        <span className="font-bold text-lg text-gray-200">Explore</span>
      </div>

      {loading ? (
        <div className="px-6 py-2 text-sm text-gray-500">Building catalog...</div>
      ) : (
        <nav className="px-4 pb-3 space-y-0.5">
          {hasTested && (
            <Row label="Tested by the team" accent onClick={() => onJump("explore-tested")} />
          )}
          {hasRecommended && (
            <Row label="Recommended for you" accent onClick={() => onJump("explore-recommended")} />
          )}
          <Row label="Search Hugging Face" accent onClick={() => onJump("explore-search")} />

          {groups.length > 0 && <div className="h-px bg-white/10 my-2 mx-2" />}

          {groups.map((g) => (
            <Row
              key={g.category}
              label={g.label}
              count={g.models.length}
              onClick={() => onJump(`cat-${g.category}`)}
            />
          ))}

          {communityCount > 0 && (
            <Row
              label="Community"
              count={communityCount}
              onClick={() => onJump("explore-community")}
            />
          )}
        </nav>
      )}
    </div>
  );
}

ExploreIndex.propTypes = {
  models: PropTypes.array,
  communityCount: PropTypes.number,
  hasTested: PropTypes.bool,
  hasRecommended: PropTypes.bool,
  loading: PropTypes.bool,
  onJump: PropTypes.func.isRequired,
};
