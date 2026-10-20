import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import type { MosaicNode } from 'react-mosaic-component';

import { CompanyDetailContext } from '../components/Company/mosaic/CompanyDetailContext';
import CompanyMosaic from '../components/Company/mosaic/CompanyMosaic';
import CompanyMosaicToolbar from '../components/Company/mosaic/CompanyMosaicToolbar';
import type { CompanyTileId, CompanyPresetId } from '../components/Company/mosaic/types';
import { COMPANY_LAYOUT_PRESETS, DEFAULT_COMPANY_PRESET_ID } from '../components/Company/mosaic/presets';

import 'react-mosaic-component/react-mosaic-component.css';
import '../components/Portfolio/mosaic/mosaic-overrides.css';

const LAYOUT_KEY = 'company-mosaic-layout-v1';
const PRESET_KEY  = 'company-mosaic-preset-v1';

export const CompanyDetail: React.FC = () => {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate   = useNavigate();

  const [activePreset, setActivePreset] = useState<CompanyPresetId>(() => {
    try {
      const s = localStorage.getItem(PRESET_KEY);
      if (s && s in COMPANY_LAYOUT_PRESETS) return s as CompanyPresetId;
    } catch { /* ignore */ }
    return DEFAULT_COMPANY_PRESET_ID;
  });

  const [mosaicNode, setMosaicNode] = useState<MosaicNode<CompanyTileId> | null>(() => {
    try {
      const s = localStorage.getItem(LAYOUT_KEY);
      if (s) return JSON.parse(s);
    } catch { /* ignore */ }
    return COMPANY_LAYOUT_PRESETS[DEFAULT_COMPANY_PRESET_ID].node;
  });

  const handleMosaicChange = useCallback((node: MosaicNode<CompanyTileId> | null) => {
    setMosaicNode(node);
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(node)); } catch { /* ignore */ }
  }, []);

  const handlePresetChange = useCallback((id: CompanyPresetId) => {
    setActivePreset(id);
    try { localStorage.setItem(PRESET_KEY, id); } catch { /* ignore */ }
  }, []);

  if (!ticker) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-base)' }}>
        <p style={{ color: 'var(--text-secondary)' }}>No ticker specified</p>
      </div>
    );
  }

  return (
    <CompanyDetailContext.Provider value={{ ticker }}>
      <div style={{ height: '100vh', background: '#f9fafb', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <div style={{
          padding: '12px 20px',
          borderBottom: '1px solid #e5e7eb',
          background: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          flexShrink: 0,
        }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              background: 'transparent', border: 'none', color: '#6b7280',
              fontSize: '13px', cursor: 'pointer', padding: '4px 8px',
              borderRadius: '6px', transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#f3f4f6'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            <ArrowLeft size={15} />
            Back
          </button>

          <div style={{ width: '1px', height: '20px', background: '#e5e7eb' }} />

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
            <span style={{ fontSize: '18px', fontWeight: '700', color: '#111827', letterSpacing: '-0.3px' }}>
              {ticker}
            </span>
            <span style={{ fontSize: '12px', color: '#9ca3af', fontWeight: '500' }}>
              Company Analysis
            </span>
          </div>
        </div>

        {/* ── Mosaic toolbar ───────────────────────────────────────────────────── */}
        <CompanyMosaicToolbar
          currentNode={mosaicNode}
          onNodeChange={handleMosaicChange}
          activePreset={activePreset}
          onPresetChange={handlePresetChange}
        />

        {/* ── Mosaic canvas ────────────────────────────────────────────────────── */}
        <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
          <CompanyMosaic value={mosaicNode} onChange={handleMosaicChange} />
        </div>
      </div>
    </CompanyDetailContext.Provider>
  );
};
