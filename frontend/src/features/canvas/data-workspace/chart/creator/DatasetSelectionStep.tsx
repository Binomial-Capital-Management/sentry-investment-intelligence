import { C, sectionHeader, mono } from './tokens';
import { ChartSource } from './types';

interface Props {
  selectedSource: ChartSource;
  selectedDatasets: any[];
  setSelectedDatasets: React.Dispatch<React.SetStateAction<any[]>>;
  onBack: () => void;
}

export default function DatasetSelectionStep({
  selectedSource,
  selectedDatasets,
  setSelectedDatasets,
  onBack,
}: Props) {
  const selectedEndpoint = selectedDatasets.length > 0 ? selectedDatasets[0].endpoint : null;

  const datasetsByEndpoint: Record<string, any[]> = {};
  (selectedSource.sheet?.datasets || []).forEach((ds: any) => {
    const key = ds.endpoint || 'unknown';
    if (!datasetsByEndpoint[key]) datasetsByEndpoint[key] = [];
    datasetsByEndpoint[key].push(ds);
  });

  const getDatasetKey = (ds: any) => ds.id || ds.endpoint + ds.symbol;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Back + source name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
        <button
          onClick={onBack}
          style={{
            background: 'none', border: 'none', padding: 0,
            fontSize: '0.563rem', color: C.textMuted, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '0.125rem',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = C.text; }}
          onMouseLeave={e => { e.currentTarget.style.color = C.textMuted; }}
        >
          <svg style={{ width: 8, height: 8 }} fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          {selectedSource.sheet?.name}
        </button>
      </div>

      <div style={sectionHeader}>Datasets</div>

      {selectedSource.sheet?.datasets?.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {Object.entries(datasetsByEndpoint).map(([endpoint, datasets]) => {
            const isCompatible = !selectedEndpoint || endpoint === selectedEndpoint;

            return (
              <div key={endpoint} style={{ opacity: isCompatible ? 1 : 0.35 }}>
                <div style={{ ...sectionHeader, fontSize: '0.5rem', marginBottom: '0.125rem', color: C.textGhost, display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                  <span>{endpoint.replace(/-/g, ' ')}</span>
                  <span style={{ color: C.textGhost }}>·</span>
                  <span style={{ fontWeight: 400, textTransform: 'none' as const }}>{datasets.length} dataset{datasets.length !== 1 ? 's' : ''}</span>
                  {!isCompatible && <span style={{ color: 'hsl(40 80% 50%)', textTransform: 'none' as const }}>(different schema)</span>}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem' }}>
                  {datasets.map((ds: any, idx: number) => {
                    const isSelected = selectedDatasets.some((d: any) => getDatasetKey(d) === getDatasetKey(ds));
                    const isDisabled = !isCompatible;

                    return (
                      <button
                        key={ds.id || `${endpoint}-${idx}`}
                        type="button"
                        onClick={() => {
                          if (isDisabled) return;
                          if (isSelected) {
                            setSelectedDatasets((prev) => prev.filter((d: any) => getDatasetKey(d) !== getDatasetKey(ds)));
                          } else {
                            setSelectedDatasets((prev) => [...prev, ds]);
                          }
                        }}
                        style={{
                          width: '100%', textAlign: 'left' as const,
                          padding: '0.375rem 0.5rem', fontSize: '0.688rem',
                          borderRadius: '0.5rem', border: 'none',
                          backgroundColor: isSelected ? C.bgActive : 'transparent',
                          opacity: isSelected ? 0.5 : isDisabled ? 0.4 : 1,
                          color: C.textMuted,
                          cursor: isDisabled ? 'default' : 'pointer',
                          display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', gap: '0.5rem',
                          transition: 'all 0.1s ease',
                        }}
                        onMouseEnter={e => { if (!isDisabled && !isSelected) e.currentTarget.style.backgroundColor = C.bgHover; }}
                        onMouseLeave={e => { e.currentTarget.style.backgroundColor = isSelected ? C.bgActive : 'transparent'; }}
                      >
                        <span style={{ fontWeight: 500, fontFamily: mono, color: C.text }}>
                          {ds.symbol !== '_MARKET_' ? ds.symbol : 'Market'}
                        </span>
                        <span style={{ fontSize: '0.563rem', color: C.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                          {ds.fields?.length || 0} fields
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ fontSize: '0.563rem', color: C.textFaint, fontStyle: 'italic', padding: '0.5rem 0', textAlign: 'center' }}>
          No datasets in this sheet
        </div>
      )}
    </div>
  );
}
