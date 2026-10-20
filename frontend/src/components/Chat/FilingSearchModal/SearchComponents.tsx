/**
 * Search components for FilingSearchModal - Ticker and Institution search
 */

import React from 'react';
import { searchStyles, getCompanyLogoUrl, InstitutionResult } from '../../Filings';
import { CloseIcon } from './icons';

// =============================================================================
// Ticker Search Components
// =============================================================================

interface TickerChipProps {
  ticker: { symbol: string; exchange: string };
  onClear: () => void;
}

export const TickerChip: React.FC<TickerChipProps> = ({ ticker, onClear }) => (
  <div style={searchStyles.tickerChip}>
    <img 
      src={getCompanyLogoUrl(ticker.symbol)} 
      alt="" 
      style={{ width: '14px', height: '14px', objectFit: 'contain' }} 
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} 
    />
    <span style={{ fontSize: '13px', fontWeight: 600 }}>{ticker.symbol}</span>
    <span style={{ fontSize: '12px', color: '#777' }}>{ticker.exchange}</span>
    <button 
      onClick={onClear} 
      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: '#999' }}
    >
      <CloseIcon size={12} />
    </button>
  </div>
);

interface TickerDropdownProps {
  results: Array<{ symbol: string; name: string; exchange: string }>;
  onSelect: (ticker: any) => void;
}

export const TickerDropdown: React.FC<TickerDropdownProps> = ({ results, onSelect }) => (
  <div style={searchStyles.dropdown}>
    {results.map((t) => (
      <button 
        key={t.symbol} 
        onClick={() => onSelect(t)} 
        style={{ 
          width: '100%', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '10px', 
          padding: '10px 12px', 
          border: 'none', 
          background: 'none', 
          cursor: 'pointer', 
          textAlign: 'left' 
        }} 
        onMouseEnter={(e) => e.currentTarget.style.background = '#f5f5f5'} 
        onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
      >
        <div style={{ width: '26px', height: '26px', background: '#f0f0f0', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <img 
            src={getCompanyLogoUrl(t.symbol)} 
            alt="" 
            style={{ width: '18px', height: '18px', objectFit: 'contain' }} 
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} 
          />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', fontWeight: 600 }}>{t.symbol}</div>
          <div style={{ fontSize: '11px', color: '#777' }}>{t.name}</div>
        </div>
        <span style={{ fontSize: '11px', color: '#999' }}>{t.exchange}</span>
      </button>
    ))}
  </div>
);

// =============================================================================
// Institution Search Components
// =============================================================================

interface InstitutionChipProps {
  institution: InstitutionResult;
  onClear: () => void;
}

export const InstitutionChip: React.FC<InstitutionChipProps> = ({ institution, onClear }) => (
  <div style={searchStyles.tickerChip}>
    <span style={{ fontSize: '13px', fontWeight: 600 }}>
      {institution.name.length > 30 ? institution.name.slice(0, 30) + '...' : institution.name}
    </span>
    <button 
      onClick={onClear} 
      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: '#999' }}
    >
      <CloseIcon size={12} />
    </button>
  </div>
);

interface InstitutionDropdownProps {
  results: InstitutionResult[];
  onSelect: (inst: InstitutionResult) => void;
}

export const InstitutionDropdown: React.FC<InstitutionDropdownProps> = ({ results, onSelect }) => (
  <div style={searchStyles.dropdown}>
    {results.map((inst) => (
      <button 
        key={inst.cik} 
        onClick={() => onSelect(inst)} 
        style={{ 
          width: '100%', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '10px', 
          padding: '10px 12px', 
          border: 'none', 
          background: 'none', 
          cursor: 'pointer', 
          textAlign: 'left' 
        }} 
        onMouseEnter={(e) => e.currentTarget.style.background = '#f5f5f5'} 
        onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
      >
        <div style={{ width: '26px', height: '26px', background: '#e8f5e9', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, color: '#2e7d32' }}>13F</span>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', fontWeight: 500 }}>{inst.name}</div>
          <div style={{ fontSize: '11px', color: '#777' }}>CIK: {inst.cik}</div>
        </div>
      </button>
    ))}
  </div>
);
