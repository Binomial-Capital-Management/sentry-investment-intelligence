import React, { useState } from 'react';
import { useOntologyStore } from '@/stores/ontologyStore';
import type { ObjectType } from '@/types/ontology';
import RelationshipGraph from './RelationshipGraph';
import './ontology-redesign.css';

export default function OntologyExplorer() {
  const { objects, viewState, setObjectTypeFilters, setSearchQuery, setSelectedObject, getObject } = useOntologyStore();
  const [searchValue, setSearchValue] = useState('');

  // Count objects
  const totalObjects = objects.size;
  const totalCompanies = Array.from(objects.values()).filter(o => o.type === 'company').length;

  // Handle search
  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchValue(value);
    setSearchQuery(value);
  };

  // Get selected object
  const selectedObject = viewState.selected_object_id ? getObject(viewState.selected_object_id) : null;

  return (
    <div className="ontology-explorer">
      {/* Simple Header */}
      <div className="ontology-header">
        <div className="ontology-header-left">
          <h1 className="ontology-header-title">Ontology</h1>
        </div>
        <div className="ontology-header-right">
          <span className="ontology-header-subtitle">{totalObjects} objects</span>
        </div>
      </div>

      {/* 3-Column Layout */}
      <div className="ontology-content">

        {/* Left: Simple Filters */}
        <div className="ontology-navigator">
          <div className="ontology-search-container">
            <div className="ontology-search-wrapper">
              <svg className="ontology-search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                className="ontology-search-input"
                placeholder="Search..."
                value={searchValue}
                onChange={handleSearch}
              />
            </div>
          </div>

          <div className="ontology-stats-section">
            <div className="ontology-stats-grid">
              <div className="ontology-stat-card">
                <div className="ontology-stat-value">{totalObjects}</div>
                <div className="ontology-stat-label">Objects</div>
              </div>
              <div className="ontology-stat-card">
                <div className="ontology-stat-value">{totalCompanies}</div>
                <div className="ontology-stat-label">Companies</div>
              </div>
            </div>
          </div>
        </div>

        {/* Center: Graph Only */}
        <div className="ontology-canvas">
          <RelationshipGraph />
        </div>

        {/* Right: Simple Detail Panel */}
        {selectedObject ? (
          <div className="ontology-detail-panel">
            <div className="ontology-detail-header">
              <div className="ontology-detail-title-section">
                <h3 className="ontology-detail-title">
                  {selectedObject.name || selectedObject.ticker || selectedObject.id}
                </h3>
                <div className="ontology-detail-subtitle">{selectedObject.type}</div>
              </div>
              <button
                className="ontology-detail-close"
                onClick={() => setSelectedObject(null, null)}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="ontology-detail-content">
              <div className="ontology-detail-section">
                <h4 className="ontology-detail-section-title">Properties</h4>
                <div className="ontology-property-grid">
                  {Object.entries(selectedObject)
                    .filter(([key]) => !['id', 'type', 'name', 'ticker'].includes(key))
                    .slice(0, 8)
                    .map(([key, value]) => (
                      <div key={key} className="ontology-property">
                        <div className="ontology-property-label">{key}</div>
                        <div className="ontology-property-value">
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="ontology-detail-panel">
            <div className="ontology-detail-empty">
              <svg className="ontology-detail-empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="ontology-detail-empty-text">No Selection</div>
              <div className="ontology-detail-empty-subtext">Click a node to view details</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
