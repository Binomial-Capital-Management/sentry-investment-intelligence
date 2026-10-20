/**
 * MarketLists Page
 *
 * Mosaic-based market analytics workspace. Every widget lives in its own
 * draggable, resizable, closeable tile. Layouts are persisted to localStorage.
 */

import { useState, useCallback, useEffect } from 'react';
import { Clock } from 'lucide-react';
import type { MosaicNode } from 'react-mosaic-component';

import MarketMosaic        from '../components/MarketLists/mosaic/MarketMosaic';
import MarketMosaicToolbar from '../components/MarketLists/mosaic/MarketMosaicToolbar';
import type { MarketTileId, MarketPresetId } from '../components/MarketLists/mosaic/types';
import { MARKET_LAYOUT_PRESETS, DEFAULT_MARKET_PRESET_ID } from '../components/MarketLists/mosaic/presets';

import 'react-mosaic-component/react-mosaic-component.css';
import '../components/Portfolio/mosaic/mosaic-overrides.css';

const LAYOUT_KEY = 'market-mosaic-layout-v1';
const PRESET_KEY  = 'market-mosaic-preset-v1';

function getMarketStatus() {
  const nyTime = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const day    = nyTime.getDay();
  const mins   = nyTime.getHours() * 60 + nyTime.getMinutes();
  if (day === 0 || day === 6)                      return { color: '#EF4444', text: 'Weekend' };
  if (mins >= 570  && mins < 960)                  return { color: '#10B981', text: 'Market Open' };
  if (mins >= 240  && mins < 570)                  return { color: '#F59E0B', text: 'Pre-Market' };
  if (mins >= 960  && mins < 1200)                 return { color: '#6366F1', text: 'After Hours' };
  return { color: '#6B7280', text: 'Market Closed' };
}

export const MarketLists: React.FC = () => {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  const [activePreset, setActivePreset] = useState<MarketPresetId>(() => {
    try {
      const s = localStorage.getItem(PRESET_KEY);
      if (s && s in MARKET_LAYOUT_PRESETS) return s as MarketPresetId;
    } catch { /* ignore */ }
    return DEFAULT_MARKET_PRESET_ID;
  });

  const [mosaicNode, setMosaicNode] = useState<MosaicNode<MarketTileId> | null>(() => {
    try {
      const s = localStorage.getItem(LAYOUT_KEY);
      if (s) return JSON.parse(s);
    } catch { /* ignore */ }
    return MARKET_LAYOUT_PRESETS[DEFAULT_MARKET_PRESET_ID].node;
  });

  const handleChange = useCallback((node: MosaicNode<MarketTileId> | null) => {
    setMosaicNode(node);
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(node)); } catch { /* ignore */ }
  }, []);

  const handlePreset = useCallback((id: MarketPresetId) => {
    setActivePreset(id);
    try { localStorage.setItem(PRESET_KEY, id); } catch { /* ignore */ }
  }, []);

  const ms = getMarketStatus();

  return (
    <div style={{
      height: '100vh', display: 'flex', flexDirection: 'column',
      overflow: 'hidden', background: '#f9fafb',
    }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{
        padding: '10px 20px', background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        display: 'flex', alignItems: 'center', gap: '14px', flexShrink: 0,
      }}>
        <span style={{ fontSize: '17px', fontWeight: '700', color: '#111827', letterSpacing: '-0.3px' }}>
          Market Analytics
        </span>

        {/* Market status badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '5px',
          padding: '3px 9px',
          background: `${ms.color}15`,
          border: `1px solid ${ms.color}30`,
          borderRadius: '20px',
        }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: ms.color }} />
          <span style={{ fontSize: '11px', fontWeight: '600', color: ms.color, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
            {ms.text}
          </span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px', color: '#9ca3af' }}>
          <Clock size={13} />
          <span style={{ fontSize: '12px' }}>
            {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>

      {/* ── Mosaic toolbar ───────────────────────────────────────────────── */}
      <MarketMosaicToolbar
        currentNode={mosaicNode}
        onNodeChange={handleChange}
        activePreset={activePreset}
        onPresetChange={handlePreset}
      />

      {/* ── Mosaic canvas ────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <MarketMosaic value={mosaicNode} onChange={handleChange} />
      </div>
    </div>
  );
};
