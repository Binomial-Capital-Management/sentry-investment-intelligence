/**
 * Shared UI components for FilingSearchModal
 */

import React from 'react';

export const EmptyState: React.FC<{ message: string; icon: React.ReactNode }> = ({ message, icon }) => (
  <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#bbb' }}>
    <div style={{ marginBottom: '10px', color: '#ddd' }}>{icon}</div>
    <p style={{ fontSize: '13px', margin: 0 }}>{message}</p>
  </div>
);

export const LoadingSpinner: React.FC = () => (
  <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{ width: '18px', height: '18px', border: '2px solid #e0e0e0', borderTopColor: '#888', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
  </div>
);
