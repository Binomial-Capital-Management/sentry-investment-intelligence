/**
 * TrackerListManager Component
 *
 * Manual tracker list management (like Yahoo Finance watchlist).
 * Users can add/remove tickers manually with search functionality.
 */

import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit2, X } from 'lucide-react';
import api from '@/services/api';
import { TickerSearch } from './TickerSearch';

interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

interface TrackerList {
  id: string;
  user_id: string;
  name: string;
  type: 'tracker';
  tickers: string[];
  created_at: string;
  updated_at: string;
}

interface TrackerListManagerProps {
  onListSelect?: (listId: string) => void;
}

export const TrackerListManager: React.FC<TrackerListManagerProps> = ({ onListSelect }) => {
  const [lists, setLists] = useState<TrackerList[]>([]);
  const [selectedListId, setSelectedListId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState<string | null>(null);
  const [newListName, setNewListName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch all tracker lists
  const fetchLists = async () => {
    setLoading(true);
    try {
      const response = await api.get<{ lists: TrackerList[]; total: number }>(
        '/api/user-lists',
        {
          params: { type: 'tracker' },
        },
      );
      const lists = response.data?.lists || [];
      setLists(lists);
      if (lists.length > 0 && !selectedListId) {
        setSelectedListId(lists[0].id);
      }
    } catch (err: any) {
      console.error('Failed to fetch tracker lists:', err);
      setError(err.response?.data?.detail || 'Failed to load tracker lists');
      setLists([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLists();
  }, []);

  // Create new tracker list
  const handleCreateList = async () => {
    if (!newListName.trim()) {
      setError('List name is required');
      return;
    }

    try {
      const response = await api.post<TrackerList>(
        '/api/user-lists',
        {
          name: newListName,
          type: 'tracker',
          tickers: [], // Start with empty list
        },
      );

      setLists([...lists, response.data]);
      setSelectedListId(response.data.id);
      setNewListName('');
      setIsCreating(false);
      setError(null);
    } catch (err: any) {
      console.error('Failed to create tracker list:', err);
      setError(err.response?.data?.detail || 'Failed to create list');
    }
  };

  // Add ticker to list
  const handleAddTicker = async (ticker: TickerSearchResult) => {
    if (!selectedListId) return;

    try {
      await api.post(
        `/api/user-lists/${selectedListId}/tickers/${ticker.symbol}`,
      );

      // Update local state
      setLists(
        lists.map((list) =>
          list.id === selectedListId
            ? { ...list, tickers: [...list.tickers, ticker.symbol] }
            : list,
        ),
      );
      setError(null);
    } catch (err: any) {
      console.error('Failed to add ticker:', err);
      setError(err.response?.data?.detail || 'Failed to add ticker');
    }
  };

  // Remove ticker from list
  const handleRemoveTicker = async (ticker: string) => {
    if (!selectedListId) return;

    try {
      await api.delete(
        `/api/user-lists/${selectedListId}/tickers/${ticker}`,
      );

      // Update local state
      setLists(
        lists.map((list) =>
          list.id === selectedListId
            ? { ...list, tickers: list.tickers.filter((t) => t !== ticker) }
            : list,
        ),
      );
      setError(null);
    } catch (err: any) {
      console.error('Failed to remove ticker:', err);
      setError(err.response?.data?.detail || 'Failed to remove ticker');
    }
  };

  // Delete list
  const handleDeleteList = async (listId: string) => {
    if (!confirm('Are you sure you want to delete this list?')) return;

    try {
      await api.delete(`/api/user-lists/${listId}`);

      setLists(lists.filter((list) => list.id !== listId));
      if (selectedListId === listId) {
        setSelectedListId(lists.length > 1 ? lists[0].id : null);
      }
      setError(null);
    } catch (err: any) {
      console.error('Failed to delete list:', err);
      setError(err.response?.data?.detail || 'Failed to delete list');
    }
  };

  // Rename list
  const handleRenameList = async (listId: string, newName: string) => {
    if (!newName.trim()) return;

    try {
      await api.patch(
        `/api/user-lists/${listId}`,
        { name: newName },
      );

      setLists(
        lists.map((list) =>
          list.id === listId ? { ...list, name: newName } : list,
        ),
      );
      setIsEditing(null);
      setError(null);
    } catch (err: any) {
      console.error('Failed to rename list:', err);
      setError(err.response?.data?.detail || 'Failed to rename list');
    }
  };

  const selectedList = selectedListId ? lists.find((list) => list.id === selectedListId) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border-light)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--border-light)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)' }}>Tracker Lists</h2>
        <button
          onClick={() => setIsCreating(true)}
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
          New List
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div style={{ margin: '12px 16px', padding: '10px 12px', background: '#FDE7E9', border: '1px solid #F1AEB5', borderRadius: '4px', color: '#A4262C', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* Create New List Form */}
      {isCreating && (
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-light)', background: '#F3F2F1' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={newListName}
              onChange={(e) => setNewListName(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleCreateList()}
              placeholder="List name (e.g., Tech Stocks)"
              style={{
                flex: 1,
                padding: '6px 10px',
                background: '#FFFFFF',
                border: '1px solid var(--border-light)',
                borderRadius: '4px',
                fontSize: '13px',
                color: 'var(--text-primary)',
                outline: 'none',
              }}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
              autoFocus
            />
            <button
              onClick={handleCreateList}
              style={{
                padding: '6px 14px',
                background: 'var(--accent)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '4px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
              }}
            >
              Create
            </button>
            <button
              onClick={() => {
                setIsCreating(false);
                setNewListName('');
              }}
              style={{
                padding: '6px 14px',
                background: '#FFFFFF',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-light)',
                borderRadius: '4px',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* List Tabs */}
      {lists.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', padding: '12px 16px', overflowX: 'auto', borderBottom: '1px solid var(--border-light)' }}>
          {lists.map((list) => (
            <div key={list.id} style={{ position: 'relative' }} className="group">
              {isEditing === list.id ? (
                <input
                  type="text"
                  defaultValue={list.name}
                  onBlur={(e) => handleRenameList(list.id, e.target.value)}
                  onKeyPress={(e) =>
                    e.key === 'Enter' && handleRenameList(list.id, (e.target as HTMLInputElement).value)
                  }
                  style={{
                    padding: '6px 10px',
                    background: '#FFFFFF',
                    border: '1px solid var(--accent)',
                    borderRadius: '4px',
                    fontSize: '13px',
                    color: 'var(--text-primary)',
                    outline: 'none',
                  }}
                  autoFocus
                />
              ) : (
                <button
                  onClick={() => {
                    setSelectedListId(list.id);
                    onListSelect?.(list.id);
                  }}
                  style={{
                    padding: '6px 12px',
                    background: selectedListId === list.id ? 'var(--accent)' : '#FFFFFF',
                    color: selectedListId === list.id ? '#FFFFFF' : 'var(--text-secondary)',
                    border: '1px solid var(--border-light)',
                    borderRadius: '4px',
                    fontSize: '13px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {list.name}
                  <span style={{ fontSize: '11px', opacity: 0.8 }}>({list.tickers.length})</span>
                </button>
              )}

              {/* Edit/Delete buttons (on hover) */}
              <div className="absolute -top-2 -right-2 hidden group-hover:flex gap-1">
                <button
                  onClick={() => setIsEditing(list.id)}
                  style={{
                    padding: '4px',
                    background: 'var(--accent)',
                    border: 'none',
                    borderRadius: '50%',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Edit2 style={{ width: '12px', height: '12px', color: '#FFFFFF' }} />
                </button>
                <button
                  onClick={() => handleDeleteList(list.id)}
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
            </div>
          ))}
        </div>
      )}

      {/* Selected List Content */}
      {selectedList ? (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Ticker Search */}
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-light)' }}>
            <TickerSearch onSelect={handleAddTicker} />
          </div>

          {/* Tickers List */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
            {selectedList.tickers.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 16px', color: 'var(--text-secondary)' }}>
                <p style={{ fontSize: '14px' }}>No tickers added yet</p>
                <p style={{ fontSize: '12px', marginTop: '8px' }}>Use the search above to add tickers</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {selectedList.tickers.map((ticker) => (
                  <div
                    key={ticker}
                    className="group"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      background: '#FFFFFF',
                      border: '1px solid var(--border-light)',
                      borderRadius: '4px',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#F3F2F1'}
                    onMouseLeave={(e) => e.currentTarget.style.background = '#FFFFFF'}
                  >
                    <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>{ticker}</span>
                    <button
                      onClick={() => handleRemoveTicker(ticker)}
                      className="opacity-0 group-hover:opacity-100"
                      style={{
                        padding: '4px',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#D13438',
                        transition: 'opacity 0.2s',
                      }}
                    >
                      <X style={{ width: '16px', height: '16px' }} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
          {loading ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ width: '32px', height: '32px', border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }}></div>
              <p style={{ fontSize: '13px' }}>Loading tracker lists...</p>
            </div>
          ) : (
            <p style={{ fontSize: '14px' }}>Create a new tracker list to get started</p>
          )}
        </div>
      )}
    </div>
  );
};
