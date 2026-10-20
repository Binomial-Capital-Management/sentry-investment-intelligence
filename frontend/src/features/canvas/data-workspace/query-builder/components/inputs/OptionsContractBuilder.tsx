/**
 * OptionsContractBuilder - Options contract builder UI
 *
 * Builds an options ticker from underlying, type, expiry, and strike.
 * Extracted from SingleObjectForm for reuse in AddDatasetPanel sidebar.
 */
interface OptionsContractBuilderProps {
  optionsUnderlying: string;
  optionsType: 'C' | 'P';
  onSetOptionsType: (type: 'C' | 'P') => void;
  optionsExpiry: string;
  onSetOptionsExpiry: (expiry: string) => void;
  optionsExpirations: string[];
  loadingExpirations: boolean;
  optionsStrike: string;
  onSetOptionsStrike: (strike: string) => void;
  optionsExpiryDropdownOpen: boolean;
  onSetOptionsExpiryDropdownOpen: (open: boolean) => void;
  onCloseOtherDropdowns?: () => void;
}

const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.375rem',
  padding: '0.3rem 0.625rem',
  backgroundColor: `hsl(${BORDER_200} / 3%)`,
  border: `0.5px solid hsl(${BORDER_200} / 12%)`,
  borderRadius: '0.5rem',
  fontFamily: FONT_UI,
  height: 30,
};

const labelStyle: React.CSSProperties = {
  fontSize: '0.5rem',
  fontWeight: 600,
  color: `hsl(${TEXT_200} / 30%)`,
  width: 36,
  flexShrink: 0,
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  fontSize: '0.688rem',
  fontWeight: 500,
  fontFamily: FONT_UI,
  backgroundColor: 'transparent',
  border: 'none',
  outline: 'none',
  color: `hsl(${TEXT_200})`,
};

export default function OptionsContractBuilder({
  optionsUnderlying,
  optionsType,
  onSetOptionsType,
  optionsExpiry,
  onSetOptionsExpiry,
  optionsExpirations,
  loadingExpirations,
  optionsStrike,
  onSetOptionsStrike,
  optionsExpiryDropdownOpen,
  onSetOptionsExpiryDropdownOpen,
  onCloseOtherDropdowns,
}: OptionsContractBuilderProps) {
  const toggleStyle = (active: boolean): React.CSSProperties => ({
    flex: 1,
    padding: '0.175rem 0',
    fontSize: '0.625rem',
    fontFamily: FONT_UI,
    fontWeight: active ? 500 : 400,
    borderRadius: '0.375rem',
    transition: 'all 0.1s ease',
    border: active ? `0.5px solid hsl(${BORDER_200} / 15%)` : '0.5px solid transparent',
    backgroundColor: active ? `hsl(${BORDER_200} / 8%)` : 'transparent',
    color: active ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 40%)`,
    cursor: 'pointer',
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem' }}>
      {/* Type Toggle */}
      <div style={rowStyle}>
        <span style={labelStyle}>Type</span>
        <div style={{ flex: 1, display: 'flex', gap: '0.25rem' }}>
          <button type="button" onClick={() => onSetOptionsType('C')} style={toggleStyle(optionsType === 'C')}>Call</button>
          <button type="button" onClick={() => onSetOptionsType('P')} style={toggleStyle(optionsType === 'P')}>Put</button>
        </div>
      </div>

      {/* Expiry */}
      <div className="relative">
        <button
          type="button"
          onClick={() => {
            if (!optionsUnderlying) return;
            const opening = !optionsExpiryDropdownOpen;
            onSetOptionsExpiryDropdownOpen(opening);
            if (opening) onCloseOtherDropdowns?.();
          }}
          style={{
            ...rowStyle,
            width: '100%',
            cursor: optionsUnderlying ? 'pointer' : 'default',
            opacity: optionsUnderlying ? 1 : 0.5,
          }}
        >
          <span style={labelStyle}>Expiry</span>
          <span style={{
            flex: 1,
            fontSize: '0.688rem',
            fontFamily: FONT_UI,
            fontWeight: 500,
            textAlign: 'left',
            color: optionsExpiry ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 30%)`,
          }}>
            {loadingExpirations ? '...' : optionsExpiry || 'Select'}
          </span>
          <svg
            style={{ width: 10, height: 10, color: `hsl(${TEXT_200} / 35%)`, flexShrink: 0, transition: 'transform 0.15s ease', transform: optionsExpiryDropdownOpen ? 'rotate(180deg)' : 'none' }}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {optionsExpiryDropdownOpen && optionsExpirations.length > 0 && (
          <div
            className="absolute left-0 right-0 z-20 mt-1 flex flex-col"
            style={{
              backgroundColor: 'white',
              borderRadius: '0.75rem',
              border: `0.5px solid hsl(${BORDER_200} / 15%)`,
              boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
              maxHeight: 220,
              overflowY: 'auto',
              padding: '0.375rem',
              fontFamily: FONT_UI,
            }}
          >
            {optionsExpirations.slice(0, 12).map(exp => {
              const isSelected = optionsExpiry === exp;
              return (
                <button
                  key={exp}
                  type="button"
                  onClick={() => { onSetOptionsExpiry(exp); onSetOptionsExpiryDropdownOpen(false); }}
                  className="w-full text-left"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.4rem 0.625rem',
                    margin: '1px 0',
                    fontSize: '0.688rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    border: isSelected ? `0.5px solid hsl(${BORDER_200} / 18%)` : '0.5px solid transparent',
                    borderRadius: '0.5rem',
                    backgroundColor: isSelected ? `hsl(${BORDER_200} / 6%)` : 'transparent',
                    color: isSelected ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 65%)`,
                    transition: 'all 0.1s ease',
                    fontFamily: 'inherit',
                  }}
                  onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = `hsl(${BORDER_200} / 4%)`; }}
                  onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                >
                  <span style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    flexShrink: 0,
                    backgroundColor: isSelected ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 20%)`,
                    transition: 'background-color 0.15s ease',
                  }} />
                  <span>{exp}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Strike */}
      <div style={rowStyle}>
        <span style={labelStyle}>Strike</span>
        <span style={{ color: `hsl(${TEXT_200} / 30%)`, fontSize: '0.688rem' }}>$</span>
        <input
          type="text"
          inputMode="decimal"
          value={optionsStrike}
          onChange={e => {
            const v = e.target.value;
            if (v === '' || /^\d*\.?\d*$/.test(v)) onSetOptionsStrike(v);
          }}
          placeholder="150"
          style={inputStyle}
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flexShrink: 0 }}>
          <button
            type="button"
            onClick={() => onSetOptionsStrike(String(Math.round((parseFloat(optionsStrike || '0') + 0.5) * 100) / 100))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: `hsl(${TEXT_200} / 30%)`, lineHeight: 1 }}
            onMouseEnter={e => { e.currentTarget.style.color = `hsl(${TEXT_200} / 60%)`; }}
            onMouseLeave={e => { e.currentTarget.style.color = `hsl(${TEXT_200} / 30%)`; }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"><path d="M18 15l-6-6-6 6"/></svg>
          </button>
          <button
            type="button"
            onClick={() => onSetOptionsStrike(String(Math.max(0, Math.round((parseFloat(optionsStrike || '0') - 0.5) * 100) / 100)))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: `hsl(${TEXT_200} / 30%)`, lineHeight: 1 }}
            onMouseEnter={e => { e.currentTarget.style.color = `hsl(${TEXT_200} / 60%)`; }}
            onMouseLeave={e => { e.currentTarget.style.color = `hsl(${TEXT_200} / 30%)`; }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
