import { useState, useMemo } from 'react';

interface Tool {
  id: string;
  name: string;
  description: string;
  category: string;
  params_schema?: Record<string, any>;
}

interface ToolMarketplaceProps {
  tools: Tool[];
  selectedToolId: string;
  onSelect: (toolId: string) => void;
  loading?: boolean;
}

// Category config with colors
const CATEGORIES: Record<string, { label: string; color: string; bg: string }> = {
  risk: { label: 'Risk', color: '#dc2626', bg: '#fef2f2' },
  valuation: { label: 'Valuation', color: '#059669', bg: '#ecfdf5' },
  quant: { label: 'Quant', color: '#7c3aed', bg: '#f5f3ff' },
  analytics: { label: 'Analytics', color: '#0284c7', bg: '#f0f9ff' },
  structuring: { label: 'Structuring', color: '#0891b2', bg: '#ecfeff' },
  alternatives: { label: 'Alternatives', color: '#d97706', bg: '#fffbeb' },
  sentiment: { label: 'Sentiment', color: '#ec4899', bg: '#fdf2f8' },
};

// Tool-specific icons as colored SVGs
const ToolIcons: Record<string, (props: { className?: string }) => JSX.Element> = {
  // Risk tools
  monte_carlo: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <path d="M3 17L7 13L11 15L15 9L21 12" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M3 17L7 13L11 15L15 9L21 12" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.3" transform="translate(0, 2)"/>
      <path d="M3 17L7 13L11 15L15 9L21 12" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.15" transform="translate(0, 4)"/>
      <circle cx="15" cy="9" r="2" fill="#dc2626"/>
    </svg>
  ),
  optimization: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Efficient frontier curve */}
      <path d="M4 18Q8 18 10 14Q12 10 14 8Q16 6 20 4" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
      {/* Optimal point */}
      <circle cx="12" cy="11" r="3" fill="#dc2626"/>
      {/* Scattered portfolios */}
      <circle cx="6" cy="16" r="1.5" fill="#dc2626" opacity="0.3"/>
      <circle cx="8" cy="14" r="1.5" fill="#dc2626" opacity="0.4"/>
      <circle cx="16" cy="7" r="1.5" fill="#dc2626" opacity="0.4"/>
      <circle cx="18" cy="5" r="1.5" fill="#dc2626" opacity="0.3"/>
    </svg>
  ),
  stress_test: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Correlation lines spreading */}
      <path d="M12 4L12 20" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
      <path d="M12 12L4 6" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" opacity="0.7"/>
      <path d="M12 12L20 6" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" opacity="0.7"/>
      <path d="M12 12L4 18" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
      <path d="M12 12L20 18" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
      {/* Warning indicator */}
      <circle cx="12" cy="12" r="3" fill="#dc2626"/>
    </svg>
  ),
  drawdown: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Underwater area */}
      <path d="M3 8L7 6L11 10L15 4L19 7L21 5" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
      {/* Drawdown depth */}
      <path d="M3 8L3 16L7 16L7 10L11 16L11 14L15 16L15 8L19 16L19 11L21 16L21 8" fill="#dc2626" opacity="0.2"/>
      {/* Baseline */}
      <path d="M3 8L21 8" stroke="#dc2626" strokeWidth="1" strokeDasharray="2 2" opacity="0.5"/>
      {/* Arrow down */}
      <path d="M12 10L12 18M9 15L12 18L15 15" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  hedge: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Shield shape */}
      <path d="M12 3L4 7V12C4 16.4 7.3 20.3 12 21C16.7 20.3 20 16.4 20 12V7L12 3Z" fill="#dc2626" opacity="0.2" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Check inside */}
      <path d="M9 12L11 14L15 10" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  barra_factors: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="14" width="4" height="7" rx="1" fill="#7c3aed"/>
      <rect x="10" y="10" width="4" height="11" rx="1" fill="#7c3aed" opacity="0.7"/>
      <rect x="17" y="6" width="4" height="15" rx="1" fill="#7c3aed" opacity="0.4"/>
      <path d="M5 12L12 6L19 3" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
    </svg>
  ),
  vol_surface: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* 3D surface mesh */}
      <path d="M2 16L6 14L10 15L14 12L18 13L22 10" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M2 12L6 10L10 11L14 8L18 9L22 6" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
      <path d="M2 8L6 6L10 7L14 4L18 5L22 2" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" opacity="0.3"/>
      {/* Vertical grid lines */}
      <path d="M6 6L6 14" stroke="#7c3aed" strokeWidth="1" opacity="0.2"/>
      <path d="M10 7L10 15" stroke="#7c3aed" strokeWidth="1" opacity="0.2"/>
      <path d="M14 4L14 12" stroke="#7c3aed" strokeWidth="1" opacity="0.2"/>
      <path d="M18 5L18 13" stroke="#7c3aed" strokeWidth="1" opacity="0.2"/>
      {/* Smile curve at bottom */}
      <path d="M4 20Q12 17 20 20" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  correlation_matrix: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Grid cells for heatmap */}
      <rect x="3" y="3" width="5" height="5" fill="#7c3aed"/>
      <rect x="9.5" y="3" width="5" height="5" fill="#7c3aed" opacity="0.6"/>
      <rect x="16" y="3" width="5" height="5" fill="#7c3aed" opacity="0.3"/>
      <rect x="3" y="9.5" width="5" height="5" fill="#7c3aed" opacity="0.6"/>
      <rect x="9.5" y="9.5" width="5" height="5" fill="#7c3aed"/>
      <rect x="16" y="9.5" width="5" height="5" fill="#7c3aed" opacity="0.5"/>
      <rect x="3" y="16" width="5" height="5" fill="#7c3aed" opacity="0.3"/>
      <rect x="9.5" y="16" width="5" height="5" fill="#7c3aed" opacity="0.5"/>
      <rect x="16" y="16" width="5" height="5" fill="#7c3aed"/>
    </svg>
  ),
  pca_analysis: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Axes */}
      <path d="M3 21L3 3" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 21L21 21" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Scatter points with PC direction */}
      <circle cx="7" cy="15" r="2" fill="#7c3aed" opacity="0.5"/>
      <circle cx="10" cy="12" r="2" fill="#7c3aed" opacity="0.6"/>
      <circle cx="13" cy="10" r="2" fill="#7c3aed" opacity="0.7"/>
      <circle cx="16" cy="8" r="2" fill="#7c3aed" opacity="0.8"/>
      <circle cx="19" cy="6" r="2" fill="#7c3aed"/>
      {/* PC1 direction arrow */}
      <path d="M5 17L20 5" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 2"/>
      <path d="M17 4L20 5L19 8" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  var: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Bell curve / histogram */}
      <rect x="3" y="16" width="3" height="5" fill="#dc2626" opacity="0.3"/>
      <rect x="6" y="12" width="3" height="9" fill="#dc2626" opacity="0.5"/>
      <rect x="9" y="8" width="3" height="13" fill="#dc2626" opacity="0.8"/>
      <rect x="12" y="10" width="3" height="11" fill="#dc2626" opacity="0.6"/>
      <rect x="15" y="14" width="3" height="7" fill="#dc2626" opacity="0.4"/>
      <rect x="18" y="17" width="3" height="4" fill="#dc2626" opacity="0.2"/>
      {/* VaR cutoff line */}
      <path d="M5 4L5 21" stroke="#ef4444" strokeWidth="2" strokeDasharray="3 2"/>
      <text x="6" y="6" fill="#ef4444" fontSize="6" fontWeight="bold">VaR</text>
    </svg>
  ),
  cointegration: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Two intertwined price series */}
      <path d="M2 12L6 10L10 14L14 8L18 11L22 9" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      <path d="M2 14L6 12L10 16L14 10L18 13L22 11" stroke="#22c55e" strokeWidth="2" strokeLinecap="round"/>
      {/* Spread bands */}
      <path d="M2 18L22 18" stroke="#6b7280" strokeWidth="1" strokeDasharray="2 2"/>
      <path d="M2 6L22 6" stroke="#6b7280" strokeWidth="1" strokeDasharray="2 2"/>
      {/* Entry/exit markers */}
      <circle cx="10" cy="15" r="2" fill="#22c55e"/>
      <circle cx="14" cy="9" r="2" fill="#ef4444"/>
    </svg>
  ),
  systemic_risk: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Network nodes */}
      <circle cx="12" cy="12" r="3" fill="#dc2626"/>
      <circle cx="5" cy="8" r="2" fill="#dc2626" opacity="0.7"/>
      <circle cx="19" cy="8" r="2" fill="#dc2626" opacity="0.7"/>
      <circle cx="5" cy="16" r="2" fill="#dc2626" opacity="0.5"/>
      <circle cx="19" cy="16" r="2" fill="#dc2626" opacity="0.5"/>
      <circle cx="12" cy="4" r="1.5" fill="#dc2626" opacity="0.4"/>
      <circle cx="12" cy="20" r="1.5" fill="#dc2626" opacity="0.4"/>
      {/* Network edges */}
      <path d="M12 12L5 8" stroke="#dc2626" strokeWidth="1.5" opacity="0.6"/>
      <path d="M12 12L19 8" stroke="#dc2626" strokeWidth="1.5" opacity="0.6"/>
      <path d="M12 12L5 16" stroke="#dc2626" strokeWidth="1.5" opacity="0.4"/>
      <path d="M12 12L19 16" stroke="#dc2626" strokeWidth="1.5" opacity="0.4"/>
      <path d="M12 9L12 4" stroke="#dc2626" strokeWidth="1" opacity="0.3"/>
      <path d="M12 15L12 20" stroke="#dc2626" strokeWidth="1" opacity="0.3"/>
      {/* Cross-connections */}
      <path d="M5 8L19 16" stroke="#dc2626" strokeWidth="0.75" opacity="0.2"/>
      <path d="M19 8L5 16" stroke="#dc2626" strokeWidth="0.75" opacity="0.2"/>
    </svg>
  ),
  
  // Valuation tools
  reverse_dcf: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Cash flow bars going up */}
      <rect x="4" y="14" width="3" height="6" fill="#059669"/>
      <rect x="8" y="11" width="3" height="9" fill="#059669" opacity="0.8"/>
      <rect x="12" y="8" width="3" height="12" fill="#059669" opacity="0.6"/>
      <rect x="16" y="5" width="3" height="15" fill="#059669" opacity="0.4"/>
      {/* Reverse arrow */}
      <path d="M20 4L4 4M4 4L8 8M4 4L8 0" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" transform="translate(0, 2)"/>
    </svg>
  ),
  comps: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Football field bars */}
      <rect x="4" y="5" width="12" height="3" rx="1" fill="#059669"/>
      <rect x="6" y="10" width="10" height="3" rx="1" fill="#059669" opacity="0.7"/>
      <rect x="5" y="15" width="14" height="3" rx="1" fill="#059669" opacity="0.5"/>
      {/* Current price line */}
      <path d="M10 3L10 21" stroke="#dc2626" strokeWidth="2" strokeDasharray="2 2"/>
      {/* Arrow markers */}
      <circle cx="4" cy="6.5" r="1.5" fill="#059669"/>
      <circle cx="16" cy="6.5" r="1.5" fill="#059669"/>
    </svg>
  ),
  epv: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Earnings power bars */}
      <rect x="4" y="10" width="4" height="10" fill="#059669"/>
      <rect x="10" y="6" width="4" height="14" fill="#059669" opacity="0.7"/>
      <rect x="16" y="8" width="4" height="12" fill="#059669" opacity="0.5"/>
      {/* Normalized line */}
      <path d="M2 8L22 8" stroke="#059669" strokeWidth="2" strokeDasharray="3 2"/>
      {/* E label */}
      <text x="11" y="5" fill="#059669" fontSize="6" fontWeight="bold">E</text>
    </svg>
  ),
  rim: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Book value base */}
      <rect x="4" y="12" width="16" height="8" fill="#059669" opacity="0.3"/>
      {/* Residual income layers */}
      <rect x="6" y="8" width="12" height="4" fill="#059669" opacity="0.5"/>
      <rect x="8" y="4" width="8" height="4" fill="#059669" opacity="0.8"/>
      {/* Plus signs for residual */}
      <path d="M12 2L12 6M10 4L14 4" stroke="#059669" strokeWidth="1.5" strokeLinecap="round"/>
      {/* Divider line */}
      <path d="M4 12L20 12" stroke="#059669" strokeWidth="1"/>
    </svg>
  ),
  
  // Quant tools (additional)
  rolling_beta: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Rolling line */}
      <path d="M3 12L6 10L9 14L12 8L15 11L18 9L21 12" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Beta symbol */}
      <text x="10" y="20" fill="#7c3aed" fontSize="8" fontWeight="bold">β</text>
      {/* Time window brackets */}
      <path d="M5 4L5 7M19 4L19 7" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
      <path d="M5 5L19 5" stroke="#7c3aed" strokeWidth="1" strokeDasharray="2 1" opacity="0.5"/>
    </svg>
  ),
  arima_forecast: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Historical price line */}
      <path d="M2 16L5 14L8 15L11 13" stroke="#6b7280" strokeWidth="2" strokeLinecap="round"/>
      {/* Forecast line with upward trend */}
      <path d="M11 13L14 11L17 9L20 6" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 2"/>
      {/* Confidence interval cone */}
      <path d="M11 13L20 4M11 13L20 9" stroke="#7c3aed" strokeWidth="1" opacity="0.3"/>
      <path d="M11 13L20 4L20 9Z" fill="#7c3aed" opacity="0.1"/>
      {/* Current point marker */}
      <circle cx="11" cy="13" r="2.5" fill="#7c3aed"/>
      {/* Arrow head */}
      <path d="M18 5L21 5L21 8" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  greeks_surface: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* 3D surface mesh lines */}
      <path d="M2 18L6 14L10 16L14 12L18 14L22 10" stroke="#7c3aed" strokeWidth="1.5" opacity="0.3"/>
      <path d="M2 14L6 10L10 12L14 8L18 10L22 6" stroke="#7c3aed" strokeWidth="1.5" opacity="0.5"/>
      <path d="M2 10L6 6L10 8L14 4L18 6L22 2" stroke="#7c3aed" strokeWidth="2"/>
      {/* Greek letter delta Δ */}
      <path d="M4 21L7 15L10 21H4Z" fill="#7c3aed" opacity="0.8"/>
      {/* Greek letter gamma Γ */}
      <path d="M14 21V16H18" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Surface highlight */}
      <circle cx="14" cy="8" r="1.5" fill="#7c3aed"/>
    </svg>
  ),
  mean_reversion: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Mean line (center) */}
      <line x1="2" y1="12" x2="22" y2="12" stroke="#7c3aed" strokeWidth="2" strokeDasharray="4 2"/>
      {/* Oscillating price wave around mean */}
      <path d="M2 12Q5 6 8 12T14 12T20 12Q22 8 22 12" stroke="#7c3aed" strokeWidth="2" fill="none"/>
      {/* Upper band */}
      <line x1="2" y1="6" x2="22" y2="6" stroke="#7c3aed" strokeWidth="1" opacity="0.3"/>
      {/* Lower band */}
      <line x1="2" y1="18" x2="22" y2="18" stroke="#7c3aed" strokeWidth="1" opacity="0.3"/>
      {/* Entry arrows (reverting to mean) */}
      <path d="M6 7L6 10" stroke="#10b981" strokeWidth="2" strokeLinecap="round" markerEnd="url(#arrow)"/>
      <path d="M18 17L18 14" stroke="#ef4444" strokeWidth="2" strokeLinecap="round"/>
      {/* Signal dots */}
      <circle cx="6" cy="6" r="2" fill="#10b981"/>
      <circle cx="18" cy="18" r="2" fill="#ef4444"/>
    </svg>
  ),
  iv_rv_screener: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Two bars representing IV and RV */}
      <rect x="4" y="8" width="6" height="12" rx="1" fill="#8b5cf6" opacity="0.8"/>
      <rect x="14" y="12" width="6" height="8" rx="1" fill="#10b981" opacity="0.8"/>
      {/* Labels */}
      <text x="7" y="6" textAnchor="middle" fontSize="5" fill="#8b5cf6" fontWeight="bold">IV</text>
      <text x="17" y="10" textAnchor="middle" fontSize="5" fill="#10b981" fontWeight="bold">RV</text>
      {/* Comparison arrow */}
      <path d="M11 14L13 14" stroke="#1f2937" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M12 12L14 14L12 16" stroke="#1f2937" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      {/* Ratio indicator */}
      <circle cx="12" cy="3" r="2" fill="#f59e0b"/>
      <text x="12" y="4" textAnchor="middle" fontSize="3" fill="white" fontWeight="bold">%</text>
    </svg>
  ),
  squeeze_detector: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Compressed spring/squeeze visualization */}
      <path d="M4 12L6 8L8 16L10 8L12 16L14 8L16 16L18 8L20 12" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Arrows showing squeeze pressure from both sides */}
      <path d="M2 12L5 12" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round"/>
      <path d="M4 10L2 12L4 14" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      <path d="M19 12L22 12" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round"/>
      <path d="M20 10L22 12L20 14" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      {/* Explosion/breakout indicator */}
      <circle cx="12" cy="4" r="2" fill="#f59e0b"/>
      <path d="M12 6L12 2" stroke="#f59e0b" strokeWidth="1.5"/>
      <path d="M10 4L14 4" stroke="#f59e0b" strokeWidth="1.5"/>
    </svg>
  ),
  network_risk: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Network nodes */}
      <circle cx="12" cy="4" r="2.5" fill="#3b82f6"/>
      <circle cx="5" cy="12" r="2.5" fill="#8b5cf6"/>
      <circle cx="19" cy="12" r="2.5" fill="#8b5cf6"/>
      <circle cx="8" cy="20" r="2.5" fill="#10b981"/>
      <circle cx="16" cy="20" r="2.5" fill="#10b981"/>
      {/* Network edges */}
      <path d="M12 6.5L5.5 10" stroke="#64748b" strokeWidth="1.5"/>
      <path d="M12 6.5L18.5 10" stroke="#64748b" strokeWidth="1.5"/>
      <path d="M5.5 14L8 17.5" stroke="#64748b" strokeWidth="1.5"/>
      <path d="M18.5 14L16 17.5" stroke="#64748b" strokeWidth="1.5"/>
      <path d="M10.5 20L13.5 20" stroke="#64748b" strokeWidth="1.5"/>
      {/* Central connection (bridge) */}
      <path d="M7 12L17 12" stroke="#ef4444" strokeWidth="2" strokeDasharray="2 2"/>
    </svg>
  ),
  earnings_pattern: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Calendar/earnings grid */}
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="#7c3aed" strokeWidth="2" fill="none"/>
      <path d="M3 9H21" stroke="#7c3aed" strokeWidth="1.5"/>
      {/* Beat bars (green) */}
      <rect x="5" y="11" width="3" height="3" fill="#22c55e"/>
      <rect x="10" y="11" width="3" height="4" fill="#22c55e"/>
      <rect x="15" y="11" width="3" height="2" fill="#22c55e"/>
      {/* Miss indicator */}
      <rect x="5" y="16" width="3" height="2" fill="#ef4444"/>
      {/* Vol crush arrow */}
      <path d="M17 15L19 17L17 19" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  vanna_charm: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Greek letter vanna (V with tilde) */}
      <path d="M4 6L8 18L12 6" stroke="#7c3aed" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6 4Q8 6 10 4" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round"/>
      {/* Greek letter chi for charm */}
      <path d="M15 6L21 18M21 6L15 18" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" opacity="0.7"/>
      {/* Delta change indicator */}
      <path d="M11 21L13 21" stroke="#22c55e" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="12" cy="21" r="1" fill="#22c55e"/>
    </svg>
  ),
  hedge_path: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Path nodes */}
      <circle cx="4" cy="12" r="3" fill="#7c3aed"/>
      <circle cx="12" cy="6" r="2.5" fill="#7c3aed" opacity="0.7"/>
      <circle cx="12" cy="18" r="2.5" fill="#7c3aed" opacity="0.7"/>
      <circle cx="20" cy="12" r="3" fill="#22c55e"/>
      {/* Dijkstra path edges */}
      <path d="M7 12L9.5 7.5" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      <path d="M14.5 7.5L17 12" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      <path d="M7 12L9.5 16.5" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" opacity="0.4"/>
      <path d="M14.5 16.5L17 12" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" opacity="0.4"/>
      {/* Optimal path highlight */}
      <path d="M4 12L12 6L20 12" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeDasharray="0"/>
    </svg>
  ),
  instanton: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Potential well / crash path curve */}
      <path d="M3 8Q6 4 12 12Q18 20 21 16" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Instanton path (dashed) */}
      <path d="M3 16Q6 12 12 12Q18 12 21 8" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 2"/>
      {/* Probability markers */}
      <circle cx="12" cy="12" r="3" fill="#7c3aed"/>
      <text x="10.5" y="14" fill="white" fontSize="6" fontWeight="bold">P</text>
      {/* Tail event indicator */}
      <path d="M19 18L21 20L19 22" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  recession_field: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Phase transition curve */}
      <path d="M3 18C6 18 8 6 12 6C16 6 18 18 21 18" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
      {/* Critical point marker */}
      <circle cx="12" cy="6" r="2.5" fill="#dc2626"/>
      {/* Warning divergence arrows */}
      <path d="M9 10L7 8M15 10L17 8" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round"/>
      {/* Field lines */}
      <path d="M4 14H8M16 14H20" stroke="#6b7280" strokeWidth="1" strokeDasharray="2 1"/>
      {/* Susceptibility indicator */}
      <path d="M11 20L12 22L13 20" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  geodesic: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Manifold surface */}
      <ellipse cx="12" cy="12" rx="9" ry="5" stroke="#7c3aed" strokeWidth="2" fill="none"/>
      {/* Geodesic path */}
      <path d="M5 12Q8 7 12 9Q16 11 19 12" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Portfolio points */}
      <circle cx="5" cy="12" r="2.5" fill="#3b82f6"/>
      <circle cx="19" cy="12" r="2.5" fill="#f59e0b"/>
    </svg>
  ),
  herding: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Aligned spins/arrows showing herding (all pointing same direction) */}
      <path d="M4 8L8 8L6 5" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M10 8L14 8L12 5" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M16 8L20 8L18 5" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Second row - also aligned */}
      <path d="M4 14L8 14L6 11" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.7"/>
      <path d="M10 14L14 14L12 11" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.7"/>
      <path d="M16 14L20 14L18 11" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.7"/>
      {/* Magnetization indicator bar */}
      <rect x="3" y="18" width="18" height="3" rx="1.5" fill="#7c3aed" opacity="0.3"/>
      <rect x="3" y="18" width="14" height="3" rx="1.5" fill="#ef4444"/>
    </svg>
  ),
  // Structuring tools
  dispersion: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Index bar (tall, center) */}
      <rect x="10" y="4" width="4" height="12" rx="1" fill="#0891b2"/>
      {/* Constituent bars diverging outward */}
      <rect x="3" y="10" width="3" height="8" rx="0.5" fill="#0891b2" opacity="0.6"/>
      <rect x="18" y="10" width="3" height="8" rx="0.5" fill="#0891b2" opacity="0.6"/>
      <rect x="6" y="12" width="2" height="6" rx="0.5" fill="#0891b2" opacity="0.4"/>
      <rect x="16" y="12" width="2" height="6" rx="0.5" fill="#0891b2" opacity="0.4"/>
      {/* Divergence arrows */}
      <path d="M5 8L3 6" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M19 8L21 6" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round"/>
      {/* Baseline */}
      <path d="M2 20L22 20" stroke="#0891b2" strokeWidth="1" opacity="0.3"/>
    </svg>
  ),
  var_swap: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Variance wave pattern */}
      <path d="M3 12C5 8 7 16 9 12C11 8 13 16 15 12C17 8 19 16 21 12" stroke="#0891b2" strokeWidth="2" strokeLinecap="round"/>
      {/* Sigma squared symbol */}
      <text x="7" y="8" fontSize="6" fontWeight="bold" fill="#0891b2">σ²</text>
      {/* Strike line */}
      <path d="M3 18L21 18" stroke="#0891b2" strokeWidth="1.5" strokeDasharray="3 2" opacity="0.5"/>
      {/* Swap arrows */}
      <path d="M5 20L5 16M8 16L5 16L5 20L8 20" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.6"/>
      <path d="M19 16L19 20M16 20L19 20L19 16L16 16" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.6"/>
    </svg>
  ),
  exotic_pricing: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Barrier line (horizontal) */}
      <path d="M3 6L21 6" stroke="#0891b2" strokeWidth="1.5" strokeDasharray="4 2" opacity="0.6"/>
      {/* Price path hitting/bouncing off barrier */}
      <path d="M3 14C5 14 6 10 8 8C9 7 10 6.5 11 8C12 10 13 12 15 10C17 8 18 6.5 19 7C20 8 21 10 21 10" stroke="#0891b2" strokeWidth="2" strokeLinecap="round"/>
      {/* Strike level */}
      <path d="M3 16L21 16" stroke="#0891b2" strokeWidth="1" opacity="0.4"/>
      {/* Star burst for exotic */}
      <circle cx="18" cy="6" r="2.5" fill="#0891b2" opacity="0.3"/>
      <path d="M18 3.5L18 4.5M18 7.5L18 8.5M15.5 6L16.5 6M19.5 6L20.5 6" stroke="#0891b2" strokeWidth="1" strokeLinecap="round"/>
      {/* Asian averaging dots */}
      <circle cx="5" cy="13" r="1" fill="#0891b2" opacity="0.5"/>
      <circle cx="9" cy="9" r="1" fill="#0891b2" opacity="0.5"/>
      <circle cx="13" cy="11" r="1" fill="#0891b2" opacity="0.5"/>
    </svg>
  ),
  option_pricing: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Call/Put payoff curve */}
      <path d="M3 18L10 18L14 8L21 8" stroke="#0891b2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Strike line */}
      <path d="M10 5L10 20" stroke="#0891b2" strokeWidth="1.5" strokeDasharray="3 2" opacity="0.5"/>
      {/* Greek delta symbol */}
      <text x="16" y="17" fontSize="8" fontWeight="bold" fill="#0891b2" opacity="0.8">Δ</text>
      {/* Premium dot */}
      <circle cx="10" cy="18" r="2" fill="#0891b2"/>
    </svg>
  ),
  nope: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* NOPE rising line */}
      <path d="M3 16L8 14L12 10L16 8" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Price falling line (divergence) */}
      <path d="M8 10L12 14L16 16L21 18" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Divergence arrows */}
      <path d="M16 6L16 10" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M14.5 8L16 6L17.5 8" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M20 16L20 20" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M18.5 18L20 20L21.5 18" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      {/* N label */}
      <text x="3" y="8" fontSize="7" fontWeight="bold" fill="#0891b2">N</text>
    </svg>
  ),
  // Alternatives tools
  commodity_ratio: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Two commodity bars */}
      <rect x="3" y="10" width="6" height="10" rx="1" fill="#0891b2" opacity="0.8"/>
      <rect x="15" y="6" width="6" height="14" rx="1" fill="#d97706" opacity="0.8"/>
      {/* Ratio symbol */}
      <path d="M11 8L13 8" stroke="#6b7280" strokeWidth="2" strokeLinecap="round"/>
      <path d="M11 12L13 12" stroke="#6b7280" strokeWidth="2" strokeLinecap="round"/>
      <path d="M11 16L13 16" stroke="#6b7280" strokeWidth="2" strokeLinecap="round"/>
      {/* Bidirectional arrows */}
      <path d="M10 10L8 10" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M14 10L16 10" stroke="#d97706" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  crypto_beta: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Bitcoin symbol */}
      <circle cx="8" cy="10" r="6" fill="#F7931A" opacity="0.8"/>
      <text x="8" y="13" fontSize="7" fontWeight="bold" fill="white" textAnchor="middle">₿</text>
      {/* Correlation line */}
      <path d="M14 6L20 6L20 18L14 18" stroke="#2E86AB" strokeWidth="2" fill="none"/>
      <path d="M14 12L20 12" stroke="#8E44AD" strokeWidth="2" strokeDasharray="2,1"/>
      {/* Regime indicator */}
      <circle cx="20" cy="6" r="2" fill="#27AE60"/>
      <circle cx="20" cy="18" r="2" fill="#E74C3C"/>
    </svg>
  ),
  commodity_momentum: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Momentum bars (ascending) */}
      <rect x="3" y="16" width="3" height="5" rx="0.5" fill="#d97706" opacity="0.4"/>
      <rect x="7" y="13" width="3" height="8" rx="0.5" fill="#d97706" opacity="0.6"/>
      <rect x="11" y="10" width="3" height="11" rx="0.5" fill="#d97706" opacity="0.8"/>
      <rect x="15" y="7" width="3" height="14" rx="0.5" fill="#d97706"/>
      <rect x="19" y="4" width="3" height="17" rx="0.5" fill="#d97706"/>
      {/* Trend line */}
      <path d="M4 15L8 12L12 9L16 6L21 3" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 2"/>
      {/* Arrow tip */}
      <path d="M19 5L21 3L19 1" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  // Additional tools - unique icons for each
  arimax: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* ARIMA line with X factors */}
      <path d="M2 14L6 12L10 15L14 10L18 8L22 6" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* X factor indicators */}
      <circle cx="6" cy="6" r="2" fill="#ef4444"/>
      <circle cx="12" cy="4" r="2" fill="#22c55e"/>
      <circle cx="18" cy="5" r="2" fill="#3b82f6"/>
      {/* Connection lines */}
      <path d="M6 8L6 12" stroke="#ef4444" strokeWidth="1" strokeDasharray="2 1"/>
      <path d="M12 6L11 15" stroke="#22c55e" strokeWidth="1" strokeDasharray="2 1"/>
      <path d="M18 7L18 8" stroke="#3b82f6" strokeWidth="1" strokeDasharray="2 1"/>
    </svg>
  ),
  dealer_gamma: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Gamma curve */}
      <path d="M3 18Q8 18 12 6Q16 18 21 18" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Dealer position bars */}
      <rect x="5" y="14" width="3" height="6" fill="#22c55e" opacity="0.8"/>
      <rect x="16" y="14" width="3" height="6" fill="#ef4444" opacity="0.8"/>
      {/* Zero line */}
      <path d="M3 12L21 12" stroke="#6b7280" strokeWidth="1" strokeDasharray="2 2"/>
      {/* Γ symbol */}
      <text x="11" y="22" fontSize="6" fontWeight="bold" fill="#7c3aed">Γ</text>
    </svg>
  ),
  confluence: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Multiple signal lines converging */}
      <path d="M3 6L12 12" stroke="#ef4444" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 12L12 12" stroke="#22c55e" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 18L12 12" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round"/>
      {/* Confluence point */}
      <circle cx="12" cy="12" r="3" fill="#7c3aed"/>
      {/* Output arrow */}
      <path d="M15 12L21 12M19 10L21 12L19 14" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  implied_corr: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Two overlapping circles for correlation */}
      <circle cx="9" cy="12" r="6" stroke="#dc2626" strokeWidth="2" fill="#dc2626" fillOpacity="0.1"/>
      <circle cx="15" cy="12" r="6" stroke="#dc2626" strokeWidth="2" fill="#dc2626" fillOpacity="0.1"/>
      {/* Intersection highlight */}
      <path d="M12 8C13.5 9.5 13.5 14.5 12 16C10.5 14.5 10.5 9.5 12 8Z" fill="#dc2626" opacity="0.5"/>
      {/* ρ symbol */}
      <text x="10.5" y="13.5" fontSize="6" fontWeight="bold" fill="#dc2626">ρ</text>
    </svg>
  ),
  fft_denoise: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Noisy signal */}
      <path d="M2 12L4 10L5 14L6 8L7 15L8 11L9 13L10 9L11 14L12 10" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" opacity="0.4"/>
      {/* Clean signal after FFT */}
      <path d="M12 12L14 10L16 14L18 8L20 12L22 10" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
      {/* FFT wave */}
      <path d="M4 20Q8 16 12 20Q16 24 20 20" stroke="#dc2626" strokeWidth="1.5" opacity="0.5"/>
    </svg>
  ),
  rolling_corr: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Rolling window bracket */}
      <path d="M6 4L6 8M18 4L18 8M6 6L18 6" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round"/>
      {/* Two correlated lines */}
      <path d="M3 14L7 12L11 16L15 10L19 14L22 12" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 16L7 14L11 18L15 12L19 16L22 14" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
      {/* ρ indicator */}
      <circle cx="12" cy="20" r="2" fill="#dc2626"/>
    </svg>
  ),
  dcf_monte_carlo: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Multiple simulation paths */}
      <path d="M3 16L7 14L11 12L15 10L19 8" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" opacity="0.3"/>
      <path d="M3 14L7 12L11 14L15 10L19 6" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
      <path d="M3 12L7 10L11 11L15 8L19 5" stroke="#059669" strokeWidth="2" strokeLinecap="round"/>
      {/* Distribution at end */}
      <ellipse cx="21" cy="8" rx="1.5" ry="4" fill="#059669" opacity="0.3"/>
      {/* $ symbol */}
      <text x="3" y="8" fontSize="6" fontWeight="bold" fill="#059669">$</text>
    </svg>
  ),
  dcf_traditional: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Cash flow bars declining */}
      <rect x="3" y="8" width="3" height="12" fill="#059669"/>
      <rect x="7" y="10" width="3" height="10" fill="#059669" opacity="0.8"/>
      <rect x="11" y="12" width="3" height="8" fill="#059669" opacity="0.6"/>
      <rect x="15" y="14" width="3" height="6" fill="#059669" opacity="0.4"/>
      {/* Terminal value */}
      <rect x="19" y="6" width="3" height="14" fill="#059669" opacity="0.3"/>
      {/* Discount arrow */}
      <path d="M12 4L4 4M4 4L7 1M4 4L7 7" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  finbert_sentiment: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Sentiment gauge */}
      <path d="M4 18A8 8 0 0 1 20 18" stroke="#ec4899" strokeWidth="2" fill="none"/>
      {/* Gauge needle pointing positive */}
      <path d="M12 18L16 10" stroke="#22c55e" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="12" cy="18" r="2" fill="#ec4899"/>
      {/* Sentiment indicators */}
      <circle cx="6" cy="14" r="1.5" fill="#ef4444"/>
      <circle cx="12" cy="10" r="1.5" fill="#f59e0b"/>
      <circle cx="18" cy="14" r="1.5" fill="#22c55e"/>
    </svg>
  ),
  sector_rotation: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Circular rotation */}
      <circle cx="12" cy="12" r="8" stroke="#7c3aed" strokeWidth="2" fill="none" opacity="0.3"/>
      {/* Sector dots */}
      <circle cx="12" cy="4" r="2" fill="#ef4444"/>
      <circle cx="19" cy="9" r="2" fill="#f59e0b"/>
      <circle cx="17" cy="17" r="2" fill="#22c55e"/>
      <circle cx="7" cy="17" r="2" fill="#3b82f6"/>
      <circle cx="5" cy="9" r="2" fill="#7c3aed"/>
      {/* Rotation arrow */}
      <path d="M16 5L18 3L20 5" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  gex: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Gamma exposure bars */}
      <rect x="4" y="6" width="3" height="8" fill="#22c55e"/>
      <rect x="8" y="4" width="3" height="10" fill="#22c55e"/>
      <rect x="12" y="14" width="3" height="6" fill="#ef4444"/>
      <rect x="16" y="12" width="3" height="8" fill="#ef4444"/>
      {/* Zero line */}
      <path d="M3 14L21 14" stroke="#6b7280" strokeWidth="1" strokeDasharray="2 2"/>
      {/* GEX label */}
      <text x="18" y="8" fontSize="5" fontWeight="bold" fill="#7c3aed">GEX</text>
    </svg>
  ),
  corr_swap: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Correlation wave */}
      <path d="M3 12C5 8 7 16 9 12C11 8 13 16 15 12C17 8 19 16 21 12" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Swap arrows */}
      <path d="M6 4L10 4M10 4L8 2M10 4L8 6" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M18 20L14 20M14 20L16 18M14 20L16 22" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Strike line */}
      <path d="M3 18L21 18" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="3 2"/>
    </svg>
  ),
  hedge_ratio: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Scatter plot with regression */}
      <circle cx="6" cy="16" r="1.5" fill="#7c3aed" opacity="0.5"/>
      <circle cx="8" cy="14" r="1.5" fill="#7c3aed" opacity="0.6"/>
      <circle cx="11" cy="11" r="1.5" fill="#7c3aed" opacity="0.7"/>
      <circle cx="14" cy="9" r="1.5" fill="#7c3aed" opacity="0.8"/>
      <circle cx="18" cy="6" r="1.5" fill="#7c3aed"/>
      {/* Regression line */}
      <path d="M4 18L20 4" stroke="#ef4444" strokeWidth="2" strokeLinecap="round"/>
      {/* β symbol */}
      <text x="16" y="18" fontSize="8" fontWeight="bold" fill="#7c3aed">β</text>
    </svg>
  ),
  dynamic_hedge: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Multi-Greek lines */}
      <path d="M3 8L7 6L11 10L15 4L19 8" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 14L7 12L11 16L15 10L19 14" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round" opacity="0.7"/>
      {/* Rebalance markers */}
      <circle cx="11" cy="10" r="2" fill="#ef4444"/>
      <circle cx="15" cy="4" r="2" fill="#ef4444"/>
      {/* Shield */}
      <path d="M19 16L21 17V20C21 21 20 22 19 22C18 22 17 21 17 20V17L19 16Z" fill="#7c3aed" opacity="0.3" stroke="#7c3aed" strokeWidth="1"/>
    </svg>
  ),
  cross_greeks: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Cross pattern */}
      <path d="M12 3L12 21" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 12L21 12" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round"/>
      {/* Greek letters at corners */}
      <text x="4" y="8" fontSize="5" fill="#ef4444" fontWeight="bold">V</text>
      <text x="17" y="8" fontSize="5" fill="#22c55e" fontWeight="bold">Λ</text>
      <text x="4" y="20" fontSize="5" fill="#3b82f6" fontWeight="bold">χ</text>
      <text x="17" y="20" fontSize="5" fill="#f59e0b" fontWeight="bold">η</text>
      {/* Center point */}
      <circle cx="12" cy="12" r="2" fill="#7c3aed"/>
    </svg>
  ),
  greek_exposure: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Greek exposure bars */}
      <rect x="3" y="10" width="4" height="10" fill="#3b82f6"/>
      <rect x="8" y="6" width="4" height="14" fill="#22c55e"/>
      <rect x="13" y="8" width="4" height="12" fill="#f59e0b"/>
      <rect x="18" y="12" width="4" height="8" fill="#ef4444"/>
      {/* Greek labels */}
      <text x="4" y="8" fontSize="4" fill="#3b82f6" fontWeight="bold">Δ</text>
      <text x="9" y="4" fontSize="4" fill="#22c55e" fontWeight="bold">Γ</text>
      <text x="14" y="6" fontSize="4" fill="#f59e0b" fontWeight="bold">V</text>
      <text x="19" y="10" fontSize="4" fill="#ef4444" fontWeight="bold">Θ</text>
    </svg>
  ),
  swaption: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Rate curve */}
      <path d="M3 16C6 14 10 10 14 9C18 8 21 9 21 9" stroke="#0891b2" strokeWidth="2" strokeLinecap="round"/>
      {/* Option payoff */}
      <path d="M10 16L10 20L18 20" stroke="#0891b2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Swap arrows */}
      <path d="M5 5L9 5" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M7 3L9 5L7 7" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="14" cy="9" r="2" fill="#0891b2"/>
    </svg>
  ),
  irs: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Two rate lines */}
      <path d="M3 8L21 8" stroke="#22c55e" strokeWidth="2" strokeLinecap="round"/>
      <path d="M3 16C7 16 10 12 14 14C18 16 21 14 21 14" stroke="#ef4444" strokeWidth="2" strokeLinecap="round"/>
      {/* Swap arrows */}
      <path d="M10 10L10 14M8 12L10 14L12 12" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 14L14 10M12 12L14 10L16 12" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Fixed/Float labels */}
      <text x="3" y="6" fontSize="4" fill="#22c55e" fontWeight="bold">FIX</text>
      <text x="16" y="20" fontSize="4" fill="#ef4444" fontWeight="bold">FLT</text>
    </svg>
  ),
  cds: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Credit default indicator */}
      <circle cx="12" cy="10" r="6" stroke="#0891b2" strokeWidth="2" fill="none"/>
      <path d="M9 10L11 12L15 8" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Premium flows */}
      <path d="M4 18L8 18" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M16 18L20 18" stroke="#0891b2" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M7 17L8 18L7 19" stroke="#0891b2" strokeWidth="1" strokeLinecap="round"/>
      <path d="M17 17L16 18L17 19" stroke="#0891b2" strokeWidth="1" strokeLinecap="round"/>
      {/* Default X */}
      <path d="M10 20L14 20M12 18L12 22" stroke="#ef4444" strokeWidth="1" opacity="0.5"/>
    </svg>
  ),
  commodity_seasonal: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Seasonal wave */}
      <path d="M2 12C4 8 6 8 8 12C10 16 12 16 14 12C16 8 18 8 20 12C22 16 22 12 22 12" stroke="#d97706" strokeWidth="2" strokeLinecap="round"/>
      {/* Month markers */}
      <circle cx="4" cy="10" r="1.5" fill="#d97706" opacity="0.4"/>
      <circle cx="8" cy="12" r="1.5" fill="#d97706" opacity="0.6"/>
      <circle cx="12" cy="14" r="1.5" fill="#d97706" opacity="0.8"/>
      <circle cx="16" cy="12" r="1.5" fill="#d97706" opacity="0.6"/>
      <circle cx="20" cy="10" r="1.5" fill="#d97706" opacity="0.4"/>
      {/* Calendar icon */}
      <rect x="3" y="17" width="6" height="5" rx="1" stroke="#d97706" strokeWidth="1" fill="none"/>
      <path d="M5 17L5 16M7 17L7 16" stroke="#d97706" strokeWidth="1"/>
    </svg>
  ),
  fx_carry: ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      {/* Currency symbols */}
      <circle cx="7" cy="10" r="5" stroke="#d97706" strokeWidth="2" fill="#d97706" fillOpacity="0.1"/>
      <text x="7" y="12" fontSize="6" fontWeight="bold" fill="#d97706" textAnchor="middle">$</text>
      <circle cx="17" cy="10" r="5" stroke="#22c55e" strokeWidth="2" fill="#22c55e" fillOpacity="0.1"/>
      <text x="17" y="12" fontSize="6" fontWeight="bold" fill="#22c55e" textAnchor="middle">€</text>
      {/* Carry arrow */}
      <path d="M10 16L14 16" stroke="#d97706" strokeWidth="2" strokeLinecap="round"/>
      <path d="M12 14L14 16L12 18" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Interest differential */}
      <text x="12" y="22" fontSize="5" fill="#6b7280" textAnchor="middle">+%</text>
    </svg>
  ),
};

// Default icon based on category - each category has a distinct shape
const DefaultIcon = ({ category, className }: { category: string; className?: string }) => {
  const color = CATEGORIES[category]?.color || '#6b7280';
  
  // Risk: Warning triangle
  if (category === 'risk') {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <path d="M12 3L22 20H2L12 3Z" fill={color} opacity="0.2" stroke={color} strokeWidth="2"/>
        <path d="M12 10L12 14" stroke={color} strokeWidth="2" strokeLinecap="round"/>
        <circle cx="12" cy="17" r="1" fill={color}/>
      </svg>
    );
  }
  
  // Valuation: Dollar/chart
  if (category === 'valuation') {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="4" y="8" width="4" height="12" fill={color} opacity="0.4"/>
        <rect x="10" y="4" width="4" height="16" fill={color} opacity="0.6"/>
        <rect x="16" y="10" width="4" height="10" fill={color} opacity="0.8"/>
        <path d="M2 20L22 20" stroke={color} strokeWidth="2"/>
      </svg>
    );
  }
  
  // Quant: Wave/formula
  if (category === 'quant') {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <path d="M2 12C4 8 6 16 8 12C10 8 12 16 14 12C16 8 18 16 20 12C22 8 22 12 22 12" stroke={color} strokeWidth="2" strokeLinecap="round"/>
        <circle cx="8" cy="12" r="2" fill={color}/>
        <circle cx="14" cy="12" r="2" fill={color}/>
        <circle cx="20" cy="12" r="2" fill={color}/>
      </svg>
    );
  }
  
  // Default: Grid
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="7" height="7" rx="1.5" fill={color} opacity="0.8"/>
      <rect x="14" y="3" width="7" height="7" rx="1.5" fill={color} opacity="0.5"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5" fill={color} opacity="0.5"/>
      <rect x="14" y="14" width="7" height="7" rx="1.5" fill={color} opacity="0.3"/>
    </svg>
  );
};

// Search icon
const SearchIcon = () => (
  <svg className="w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

// Check icon
const CheckIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="10" fill="#0051cc"/>
    <path d="M8 12l3 3 5-6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

interface ToolCardProps {
  tool: Tool;
  isSelected: boolean;
  onSelect: () => void;
}

function ToolCard({ tool, isSelected, onSelect }: ToolCardProps) {
  const IconComponent = ToolIcons[tool.id];
  
  return (
    <div
      onClick={onSelect}
      className={`
        group flex items-center gap-2.5 px-3 py-2.5 rounded-md border cursor-pointer transition-all duration-150
        ${isSelected
          ? 'border-[#0051cc] bg-[#0051cc]/5'
          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}
      `}
    >
      {/* Icon - no background */}
      <div className="w-5 h-5 shrink-0">
        {IconComponent ? (
          <IconComponent className="w-5 h-5" />
        ) : (
          <DefaultIcon category={tool.category} className="w-5 h-5" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className={`text-[12px] font-medium truncate ${
          isSelected ? 'text-[#0051cc]' : 'text-gray-900'
        }`}>
          {tool.name}
        </div>
        <div className="text-[10px] text-gray-500 truncate">
          {tool.description}
        </div>
      </div>

      {/* Selected indicator */}
      {isSelected && <CheckIcon />}
    </div>
  );
}

export default function ToolMarketplace({ tools, selectedToolId, onSelect, loading }: ToolMarketplaceProps) {
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredTools = useMemo(() => {
    return tools.filter(tool => {
      const matchesTab = activeTab === 'all' || tool.category === activeTab;
      const matchesSearch = tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            tool.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesTab && matchesSearch;
    });
  }, [tools, activeTab, searchQuery]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: tools.length };
    tools.forEach(t => { counts[t.category] = (counts[t.category] || 0) + 1; });
    return counts;
  }, [tools]);

  // Get unique categories from tools
  const availableCategories = useMemo(() => {
    const cats = new Set(tools.map(t => t.category));
    return ['all', ...Array.from(cats)];
  }, [tools]);

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="w-6 h-6 border-2 border-gray-200 border-t-[#0051cc] rounded-full animate-spin" />
      </div>
    );
  }

  if (tools.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mb-2">
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
        </div>
        <div className="text-sm text-gray-500">No tools available</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header: Tabs + Search */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-gray-100">
        <div className="flex flex-wrap items-center gap-1">
          {availableCategories.map((catId) => {
            const count = categoryCounts[catId] || 0;
            const config = CATEGORIES[catId];
            const isAll = catId === 'all';
            
            return (
              <button
                key={catId}
                onClick={() => setActiveTab(catId)}
                className={`
                  px-3 py-1.5 text-xs font-medium rounded-md transition-all
                  ${activeTab === catId
                    ? 'bg-gray-900 text-white'
                    : 'text-gray-600 hover:bg-gray-100'}
                `}
              >
                <span className="flex items-center gap-1.5">
                  {!isAll && config && (
                    <span 
                      className="w-2 h-2 rounded-full" 
                      style={{ backgroundColor: config.color }}
                    />
                  )}
                  {isAll ? 'All' : config?.label || catId}
                  <span className={`text-[10px] ${activeTab === catId ? 'text-gray-400' : 'text-gray-400'}`}>
                    {count}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="relative">
          <div className="absolute left-2.5 top-1/2 -translate-y-1/2">
            <SearchIcon />
          </div>
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-3 py-1.5 bg-white border border-gray-200 rounded-md text-xs focus:ring-1 focus:ring-[#0051cc]/30 focus:border-[#0051cc] transition-all w-36"
          />
        </div>
      </div>

      {/* Tool Grid - 4 columns for narrower cards */}
      {filteredTools.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          {filteredTools.map((tool) => (
            <ToolCard
              key={tool.id}
              tool={tool}
              isSelected={selectedToolId === tool.id}
              onSelect={() => onSelect(tool.id)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="text-xs text-gray-500">No tools match "{searchQuery}"</div>
          <button
            onClick={() => { setActiveTab('all'); setSearchQuery(''); }}
            className="mt-2 text-xs text-[#0051cc] hover:underline"
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}
