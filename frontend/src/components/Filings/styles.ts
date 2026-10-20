/**
 * Shared styles for SEC filings components
 */

import { CSSProperties } from 'react';

export const modalStyles = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    zIndex: 50,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modal: {
    backgroundColor: '#fff',
    width: '95vw',
    maxWidth: '1300px',
    height: '85vh',
    maxHeight: '800px',
    borderRadius: '8px',
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden',
    boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '10px 16px',
    borderBottom: '1px solid #eee',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 16px',
    borderTop: '1px solid #eee',
  },
};

export const searchStyles = {
  wrap: {
    position: 'relative' as const,
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  input: {
    flex: 1,
    border: 'none',
    outline: 'none',
    fontSize: '13px',
    background: 'transparent',
  },
  dropdown: {
    position: 'absolute' as const,
    top: '100%',
    left: 0,
    right: 0,
    marginTop: '4px',
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    zIndex: 100,
    maxHeight: '220px',
    overflowY: 'auto' as const,
  },
  tickerChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 8px',
    background: '#f3f3f3',
    borderRadius: '4px',
    border: '1px solid #e0e0e0',
  },
};

export const listStyles = {
  container: {
    width: '480px',
    flexShrink: 0,
    overflow: 'auto',
    borderRight: '1px solid #eee',
  },
  sectionHeader: {
    padding: '8px 14px',
    fontSize: '11px',
    fontWeight: 500,
    color: '#888',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.3px',
    background: '#fafafa',
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '9px 14px',
    cursor: 'pointer',
    borderBottom: '1px solid #f5f5f5',
  },
  checkbox: {
    width: '18px',
    height: '18px',
    accentColor: '#4caf50',
    cursor: 'pointer',
  },
};

export const previewStyles = {
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 14px',
    borderBottom: '1px solid #eee',
    background: '#fafafa',
  },
  content: {
    flex: 1,
    overflow: 'hidden',
  },
};

export const buttonStyles = {
  primary: (enabled: boolean): CSSProperties => ({
    padding: '8px 16px',
    background: enabled ? '#1976d2' : '#f0f0f0',
    color: enabled ? '#fff' : '#999',
    border: 'none',
    borderRadius: '4px',
    fontSize: '13px',
    fontWeight: 500,
    cursor: enabled ? 'pointer' : 'not-allowed',
  }),
  secondary: {
    background: 'none',
    border: '1px solid #ddd',
    borderRadius: '4px',
    padding: '4px 8px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '12px',
    color: '#555',
  },
  icon: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px',
    display: 'flex',
    alignItems: 'center',
    color: '#999',
  },
};

export const expandedModalStyles = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    zIndex: 100,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px',
  },
  container: {
    width: '90%',
    maxWidth: '1200px',
    height: '85%',
    maxHeight: '900px',
    background: '#fff',
    borderRadius: '12px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 20px',
    borderBottom: '1px solid #eee',
    flexShrink: 0,
  },
};
