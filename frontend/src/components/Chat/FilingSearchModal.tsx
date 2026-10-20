/**
 * FilingSearchModal - SEC filings browser
 * 
 * Re-exports from refactored module structure.
 * The main implementation is now in ./FilingSearchModal/
 */

export { default } from './FilingSearchModal/FilingSearchModal';

// Also re-export sub-components for consumers who need them directly
export * from './FilingSearchModal/icons';
export * from './FilingSearchModal/UIComponents';
export * from './FilingSearchModal/SearchComponents';
export * from './FilingSearchModal/FilterPanel';
export * from './FilingSearchModal/FilingSections';
export * from './FilingSearchModal/PreviewComponents';
export * from './FilingSearchModal/TranscriptViewer';
export * from './FilingSearchModal/ExpandedModals';
