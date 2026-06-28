import React, { useState } from "react";
import PropTypes from "prop-types";
import { ChevronDown, ChevronRight, Blocks } from "lucide-react";
import ModelCard from "./ModelCard";
import { groupByCategory } from "../utils/modelCatalog";

/**
 * Renders Base models grouped into capability-category sections (#122):
 * General / Reasoning / Code / Vision / … Each section is collapsible; Safety
 * (moderation classifiers, not chat models) starts collapsed. Only non-empty
 * categories are shown.
 */
export default function CategorySections({ models, loading, searchQuery, onDownload, onInfo }) {
  const groups = groupByCategory(models);
  // Per-category collapsed state; defaults come from CATEGORY_META (Safety closed).
  const [collapsed, setCollapsed] = useState(() =>
    groups.reduce((acc, g) => ({ ...acc, [g.category]: g.collapsed }), {})
  );

  const toggle = (cat) => setCollapsed((c) => ({ ...c, [cat]: !(cat in c ? c[cat] : false) }));

  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-3 text-center py-8">
          <div className="flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin mr-3"></div>
            <p className="text-gray-400">Loading base models...</p>
          </div>
        </div>
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-400">
          {searchQuery ? `No base models found for "${searchQuery}"` : "No base models available"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map((group) => {
        const isCollapsed = group.category in collapsed ? collapsed[group.category] : false;
        return (
          <div key={group.category}>
            <button
              className="flex items-center gap-2 mb-4 w-full text-left group"
              onClick={() => toggle(group.category)}
            >
              {isCollapsed ? (
                <ChevronRight className="w-4 h-4 text-white/70" />
              ) : (
                <ChevronDown className="w-4 h-4 text-white/70" />
              )}
              <Blocks className="w-5 h-5 text-white" />
              <h3 className="text-lg font-semibold text-white">
                {group.label}
                <span className="text-xs text-gray-400 ml-2">({group.models.length})</span>
              </h3>
            </button>
            {!isCollapsed && (
              <div className="grid grid-cols-3 gap-4 max-h-[480px] overflow-y-auto pr-2">
                {group.models.map((model) => (
                  <ModelCard
                    key={model.id ?? model.link}
                    model={model}
                    type="base"
                    onDownload={onDownload}
                    onInfo={onInfo}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

CategorySections.propTypes = {
  models: PropTypes.array.isRequired,
  loading: PropTypes.bool,
  searchQuery: PropTypes.string,
  onDownload: PropTypes.func,
  onInfo: PropTypes.func,
};
