/**
 * ScreenerBuilder Component
 *
 * Dynamic screener builder using FMP's company-screener endpoint.
 * Users can apply filters (marketCap, PE, sector, etc.) to find matching stocks.
 */

import React, { useState, useEffect } from 'react';
import { Filter, Plus, Trash2, Edit2, Save } from 'lucide-react';
import api from '@/services/api';

interface ScreenerFilters {
  marketCapMoreThan?: number;
  marketCapLowerThan?: number;
  priceMoreThan?: number;
  priceLowerThan?: number;
  betaMoreThan?: number;
  betaLowerThan?: number;
  volumeMoreThan?: number;
  volumeLowerThan?: number;
  dividendMoreThan?: number;
  dividendLowerThan?: number;
  sector?: string;
  industry?: string;
  exchange?: string;
  limit?: number;
}

interface Screener {
  id: string;
  user_id: string;
  name: string;
  type: 'screener';
  screener_filters: ScreenerFilters;
  created_at: string;
  updated_at: string;
}

interface ScreenerBuilderProps {
  onScreenerSelect?: (screenerId: string) => void;
}

export const ScreenerBuilder: React.FC<ScreenerBuilderProps> = ({ onScreenerSelect }) => {
  const [screeners, setScreeners] = useState<Screener[]>([]);
  const [selectedScreenerId, setSelectedScreenerId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [screenerName, setScreenerName] = useState('');
  const [filters, setFilters] = useState<ScreenerFilters>({
    limit: 50,
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch all screeners
  const fetchScreeners = async () => {
    setLoading(true);
    try {
      const response = await api.get<{ lists: Screener[]; total: number }>(
        '/api/user-lists',
        {
          params: { type: 'screener' },
        },
      );
      const lists = response.data?.lists || [];
      setScreeners(lists);
      if (lists.length > 0 && !selectedScreenerId) {
        setSelectedScreenerId(lists[0].id);
        setFilters(lists[0].screener_filters || { limit: 50 });
        setScreenerName(lists[0].name);
      }
    } catch (err: any) {
      console.error('Failed to fetch screeners:', err);
      setError(err.response?.data?.detail || 'Failed to load screeners');
      setScreeners([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScreeners();
  }, []);

  // Create new screener
  const handleCreateScreener = async () => {
    if (!screenerName.trim()) {
      setError('Screener name is required');
      return;
    }

    if (Object.keys(filters).length === 0 || (Object.keys(filters).length === 1 && filters.limit)) {
      setError('At least one filter is required');
      return;
    }

    try {
      const response = await api.post<Screener>(
        '/api/user-lists',
        {
          name: screenerName,
          type: 'screener',
          screener_filters: filters,
        },
      );

      setScreeners([...screeners, response.data]);
      setSelectedScreenerId(response.data.id);
      setIsCreating(false);
      setError(null);
    } catch (err: any) {
      console.error('Failed to create screener:', err);
      setError(err.response?.data?.detail || 'Failed to create screener');
    }
  };

  // Update screener filters
  const handleUpdateScreener = async () => {
    if (!selectedScreenerId) return;

    if (Object.keys(filters).length === 0 || (Object.keys(filters).length === 1 && filters.limit)) {
      setError('At least one filter is required');
      return;
    }

    try {
      await api.patch(
        `/api/user-lists/${selectedScreenerId}`,
        {
          name: screenerName,
          screener_filters: filters,
        },
      );

      setScreeners(
        screeners.map((screener) =>
          screener.id === selectedScreenerId
            ? { ...screener, name: screenerName, screener_filters: filters }
            : screener,
        ),
      );
      setIsEditing(false);
      setError(null);
    } catch (err: any) {
      console.error('Failed to update screener:', err);
      setError(err.response?.data?.detail || 'Failed to update screener');
    }
  };

  // Delete screener
  const handleDeleteScreener = async (screenerId: string) => {
    if (!confirm('Are you sure you want to delete this screener?')) return;

    try {
      await api.delete(`/api/user-lists/${screenerId}`);

      setScreeners(screeners.filter((screener) => screener.id !== screenerId));
      if (selectedScreenerId === screenerId) {
        const remaining = screeners.filter((s) => s.id !== screenerId);
        if (remaining.length > 0) {
          setSelectedScreenerId(remaining[0].id);
          setFilters(remaining[0].screener_filters);
          setScreenerName(remaining[0].name);
        } else {
          setSelectedScreenerId(null);
          setFilters({ limit: 50 });
          setScreenerName('');
        }
      }
      setError(null);
    } catch (err: any) {
      console.error('Failed to delete screener:', err);
      setError(err.response?.data?.detail || 'Failed to delete screener');
    }
  };

  // Select screener
  const handleSelectScreener = (screener: Screener) => {
    setSelectedScreenerId(screener.id);
    setFilters(screener.screener_filters);
    setScreenerName(screener.name);
    setIsEditing(false);
    onScreenerSelect?.(screener.id);
  };

  // Filter update helper
  const updateFilter = (key: keyof ScreenerFilters, value: any) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === '' ? undefined : value,
    }));
  };

  const selectedScreener = selectedScreenerId ? screeners.find((s) => s.id === selectedScreenerId) : null;

  // Reusable compact input styles
  const inputStyle = {
    width: '100%',
    padding: '4px 8px',
    background: '#FFFFFF',
    border: '1px solid var(--border-light)',
    borderRadius: '4px',
    fontSize: '12px',
    color: 'var(--text-primary)',
    outline: 'none',
    opacity: (!isCreating && !isEditing) ? 0.6 : 1,
    overflow: 'hidden', // Prevent scrollbars on number inputs
    boxSizing: 'border-box' as const,
  };

  const sectionStyle = {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '6px',
  };

  const labelStyle = {
    fontSize: '11px',
    fontWeight: '600' as const,
    color: 'var(--text-secondary)',
    marginBottom: '3px',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border-light)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--border-light)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter style={{ width: '18px', height: '18px' }} />
          Screeners
        </h2>
        <button
          onClick={() => {
            setIsCreating(true);
            setIsEditing(false);
            setScreenerName('');
            setFilters({ limit: 50 });
          }}
          style={{
            padding: '6px 12px',
            background: 'var(--accent)',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '4px',
            fontSize: '13px',
            fontWeight: '500',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#005A9E'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'var(--accent)'}
        >
          <Plus style={{ width: '14px', height: '14px' }} />
          New Screener
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div style={{ margin: '12px 16px', padding: '10px 12px', background: '#FDE7E9', border: '1px solid #F1AEB5', borderRadius: '4px', color: '#A4262C', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* Screener Tabs */}
      {screeners.length > 0 && !isCreating && (
        <div style={{ display: 'flex', gap: '8px', padding: '12px 16px', overflowX: 'auto', borderBottom: '1px solid var(--border-light)' }}>
          {screeners.map((screener) => (
            <div key={screener.id} style={{ position: 'relative' }} className="group">
              <button
                onClick={() => handleSelectScreener(screener)}
                style={{
                  padding: '6px 12px',
                  background: selectedScreenerId === screener.id ? 'var(--accent)' : '#FFFFFF',
                  color: selectedScreenerId === screener.id ? '#FFFFFF' : 'var(--text-secondary)',
                  border: '1px solid var(--border-light)',
                  borderRadius: '4px',
                  fontSize: '13px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {screener.name}
              </button>

              {/* Delete button (on hover) */}
              <button
                onClick={() => handleDeleteScreener(screener.id)}
                className="absolute -top-2 -right-2 hidden group-hover:block"
                style={{
                  padding: '4px',
                  background: '#D13438',
                  border: 'none',
                  borderRadius: '50%',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Trash2 style={{ width: '12px', height: '12px', color: '#FFFFFF' }} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Filter Form - Compact scrollable */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Screener Name */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Screener Name
          </label>
          <input
            type="text"
            value={screenerName}
            onChange={(e) => setScreenerName(e.target.value)}
            placeholder="e.g., Large Cap Tech"
            disabled={!isCreating && !isEditing}
            style={{
              width: '100%',
              padding: '6px 10px',
              background: '#FFFFFF',
              border: '1px solid var(--border-light)',
              borderRadius: '4px',
              fontSize: '13px',
              color: 'var(--text-primary)',
              outline: 'none',
              opacity: (!isCreating && !isEditing) ? 0.6 : 1,
            }}
            onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
            onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
          />
        </div>

        {/* Market Cap Filters */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Market Cap ($)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <input
              type="number"
              value={filters.marketCapMoreThan || ''}
              onChange={(e) => updateFilter('marketCapMoreThan', parseFloat(e.target.value))}
              placeholder="Min"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <input
              type="number"
              value={filters.marketCapLowerThan || ''}
              onChange={(e) => updateFilter('marketCapLowerThan', parseFloat(e.target.value))}
              placeholder="Max"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
          </div>
        </div>

        {/* Price Filters */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Price ($)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <input
              type="number"
              value={filters.priceMoreThan || ''}
              onChange={(e) => updateFilter('priceMoreThan', parseFloat(e.target.value))}
              placeholder="Min"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <input
              type="number"
              value={filters.priceLowerThan || ''}
              onChange={(e) => updateFilter('priceLowerThan', parseFloat(e.target.value))}
              placeholder="Max"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
          </div>
        </div>

        {/* Volume Filters */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Volume</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <input
              type="number"
              value={filters.volumeMoreThan || ''}
              onChange={(e) => updateFilter('volumeMoreThan', parseFloat(e.target.value))}
              placeholder="Min"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <input
              type="number"
              value={filters.volumeLowerThan || ''}
              onChange={(e) => updateFilter('volumeLowerThan', parseFloat(e.target.value))}
              placeholder="Max"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
          </div>
        </div>

        {/* Beta Filters */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Beta</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <input
              type="number"
              step="0.1"
              value={filters.betaMoreThan || ''}
              onChange={(e) => updateFilter('betaMoreThan', parseFloat(e.target.value))}
              placeholder="Min"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <input
              type="number"
              step="0.1"
              value={filters.betaLowerThan || ''}
              onChange={(e) => updateFilter('betaLowerThan', parseFloat(e.target.value))}
              placeholder="Max"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
          </div>
        </div>

        {/* Dividend Filters */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Dividend Yield (%)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <input
              type="number"
              step="0.1"
              value={filters.dividendMoreThan || ''}
              onChange={(e) => updateFilter('dividendMoreThan', parseFloat(e.target.value))}
              placeholder="Min"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <input
              type="number"
              step="0.1"
              value={filters.dividendLowerThan || ''}
              onChange={(e) => updateFilter('dividendLowerThan', parseFloat(e.target.value))}
              placeholder="Max"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
          </div>
        </div>

        {/* Sector/Industry/Exchange */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Classification</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <input
              type="text"
              value={filters.sector || ''}
              onChange={(e) => updateFilter('sector', e.target.value)}
              placeholder="Sector"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <input
              type="text"
              value={filters.industry || ''}
              onChange={(e) => updateFilter('industry', e.target.value)}
              placeholder="Industry"
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            />
            <select
              value={filters.exchange || ''}
              onChange={(e) => updateFilter('exchange', e.target.value)}
              disabled={!isCreating && !isEditing}
              style={inputStyle}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
            >
              <option value="">All Exchanges</option>
              <option value="NYSE">NYSE</option>
              <option value="NASDAQ">NASDAQ</option>
              <option value="AMEX">AMEX</option>
            </select>
          </div>
        </div>

        {/* Result Limit */}
        <div style={sectionStyle}>
          <h3 style={labelStyle}>Max Results</h3>
          <input
            type="number"
            value={filters.limit || 50}
            onChange={(e) => updateFilter('limit', parseInt(e.target.value))}
            min={1}
            max={1000}
            placeholder="50"
            disabled={!isCreating && !isEditing}
            style={inputStyle}
            onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
            onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-light)', display: 'flex', gap: '8px' }}>
        {isCreating ? (
          <>
            <button
              onClick={handleCreateScreener}
              style={{
                flex: 1,
                padding: '6px 12px',
                background: 'var(--accent)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '4px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
              }}
              onMouseOver={(e) => e.currentTarget.style.background = '#106EBE'}
              onMouseOut={(e) => e.currentTarget.style.background = 'var(--accent)'}
            >
              <Save style={{ width: '14px', height: '14px' }} />
              Create Screener
            </button>
            <button
              onClick={() => {
                setIsCreating(false);
                if (selectedScreener) {
                  setFilters(selectedScreener.screener_filters);
                  setScreenerName(selectedScreener.name);
                } else {
                  setFilters({ limit: 50 });
                  setScreenerName('');
                }
              }}
              style={{
                padding: '6px 12px',
                background: 'var(--bg-card)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-light)',
                borderRadius: '4px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
              }}
              onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseOut={(e) => e.currentTarget.style.background = 'var(--bg-card)'}
            >
              Cancel
            </button>
          </>
        ) : isEditing ? (
          <>
            <button
              onClick={handleUpdateScreener}
              style={{
                flex: 1,
                padding: '6px 12px',
                background: 'var(--accent)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '4px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
              }}
              onMouseOver={(e) => e.currentTarget.style.background = '#106EBE'}
              onMouseOut={(e) => e.currentTarget.style.background = 'var(--accent)'}
            >
              <Save style={{ width: '14px', height: '14px' }} />
              Save Changes
            </button>
            <button
              onClick={() => {
                setIsEditing(false);
                if (selectedScreener) {
                  setFilters(selectedScreener.screener_filters);
                  setScreenerName(selectedScreener.name);
                }
              }}
              style={{
                padding: '6px 12px',
                background: 'var(--bg-card)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-light)',
                borderRadius: '4px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
              }}
              onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseOut={(e) => e.currentTarget.style.background = 'var(--bg-card)'}
            >
              Cancel
            </button>
          </>
        ) : (
          selectedScreener && (
            <button
              onClick={() => setIsEditing(true)}
              style={{
                flex: 1,
                padding: '6px 12px',
                background: 'var(--accent)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '4px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
              }}
              onMouseOver={(e) => e.currentTarget.style.background = '#106EBE'}
              onMouseOut={(e) => e.currentTarget.style.background = 'var(--accent)'}
            >
              <Edit2 style={{ width: '14px', height: '14px' }} />
              Edit Filters
            </button>
          )
        )}
      </div>

      {/* Empty State */}
      {!isCreating && screeners.length === 0 && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', padding: '32px' }}>
          {loading ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ width: '32px', height: '32px', border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }}></div>
              <p style={{ fontSize: '13px' }}>Loading screeners...</p>
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <Filter style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5 }} />
              <p style={{ fontSize: '13px', marginBottom: '8px' }}>No screeners created yet</p>
              <p style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>Click "New Screener" to create one</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
