import React from "react";
import PropTypes from "prop-types";
import ModelCarousel from "./ModelCarousel";
import { groupByCategory } from "../utils/modelCatalog";

/**
 * Base models grouped into capability carousels (#122): General / Reasoning /
 * Code / Vision / … Each is a scannable row that expands to a full grid. Cards
 * carry a hardware-fit gauge, so the benchmark's verdict travels with every model.
 */
export default function CategorySections({
  models,
  range,
  loading,
  searchQuery,
  onDownload,
  onInfo,
}) {
  const groups = groupByCategory(models);

  if (loading) {
    return (
      <div className="text-[var(--ink-faint)] mono text-xs py-10 text-center">
        building catalog…
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <p className="text-[var(--ink-dim)] text-sm py-8 text-center">
        {searchQuery ? `No base models found for “${searchQuery}”` : "No base models available"}
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {groups.map((group) => (
        <ModelCarousel
          key={group.category}
          id={`cat-${group.category}`}
          label={group.label}
          models={group.models}
          range={range}
          onDownload={onDownload}
          onInfo={onInfo}
        />
      ))}
    </div>
  );
}

CategorySections.propTypes = {
  models: PropTypes.array.isRequired,
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
  loading: PropTypes.bool,
  searchQuery: PropTypes.string,
  onDownload: PropTypes.func,
  onInfo: PropTypes.func,
};
