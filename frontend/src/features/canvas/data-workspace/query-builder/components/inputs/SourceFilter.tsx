/**
 * SourceFilter - Reusable filter tabs for data source selection (All/FMP/Polygon/UW)
 */

interface SourceFilterProps {
  /** Current selected source filter */
  sourceFilter: string;
  /** Callback when source filter changes */
  onSourceFilterChange: (source: string) => void;
  /** Endpoint counts by source */
  endpointsBySource: Record<string, number>;
}

const SOURCE_CONFIG = [
  { key: 'all', label: 'All' },
  { key: 'fmp', label: 'FMP' },
  { key: 'polygon', label: 'Poly' },
  { key: 'uw', label: 'UW' },
] as const;

const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';

export default function SourceFilter({
  sourceFilter,
  onSourceFilterChange,
  endpointsBySource,
}: SourceFilterProps) {
  const totalCount = endpointsBySource['all'] || 0;
  if (totalCount === 0) return null;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
      {SOURCE_CONFIG.map(({ key, label }) => {
        const isActive = sourceFilter === key;
        const count = endpointsBySource[key] || 0;

        if (key !== 'all' && count === 0) return null;

        return (
          <button
            key={key}
            onClick={() => onSourceFilterChange(key)}
            style={{
              padding: '0.2rem 0.5rem',
              fontSize: '0.563rem',
              fontWeight: 500,
              fontFamily: FONT_UI,
              borderRadius: '0.375rem',
              transition: 'all 0.1s ease',
              border: isActive ? `0.5px solid hsl(${BORDER_200} / 20%)` : '0.5px solid transparent',
              backgroundColor: isActive ? `hsl(${BORDER_200} / 8%)` : 'transparent',
              color: isActive ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 40%)`,
              cursor: 'pointer',
            }}
            title={`${label}: ${count} endpoints`}
          >
            {label}
            <span style={{ marginLeft: 2, opacity: 0.7 }}>{count}</span>
          </button>
        );
      })}
    </div>
  );
}
