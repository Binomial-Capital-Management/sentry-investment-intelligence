import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Wrench, Check } from 'lucide-react';
import type { AgentMode } from '@/types';

interface ToolPrioritySelectorProps {
  agentMode: AgentMode;
  selectedTools: string[];
  onToolsChange: (tools: string[]) => void;
  disabled?: boolean;
  direction?: 'up' | 'down';
}

// Custom analysis/calculation tools only - excludes MCP data-fetching tools
const customToolsMap: Record<string, { id: string; name: string }[]> = {
  risk: [
    { id: 'calculate_var', name: 'VaR & CVaR Calculator' },
    { id: 'run_monte_carlo', name: 'Monte Carlo Simulation' },
    { id: 'optimize_portfolio', name: 'Portfolio Optimizer' },
    { id: 'analyze_barra_factors', name: 'Barra Factor Analysis' },
    { id: 'create_hedge_portfolio', name: 'Hedge Construction' },
    { id: 'compute_optimal_hedge_path', name: 'Dijkstra Hedge Pathfinder' },
    { id: 'analyze_fft_trends', name: 'FFT Trend Analysis' },
    { id: 'calculate_rolling_correlation', name: 'Rolling Correlation' },
    { id: 'calculate_implied_correlation', name: 'Implied Correlation' },
    { id: 'price_correlation_swap', name: 'Correlation Swap Pricing' },
    { id: 'stress_test_correlation', name: 'Correlation Stress Test' },
    { id: 'analyze_correlation_matrix', name: 'Correlation Matrix' },
    { id: 'analyze_graph_theory_risk', name: 'Graph Theory Network Risk' },
    { id: 'analyze_systemic_risk_score', name: 'Systemic Risk Score' },
    { id: 'detect_squeeze_setup', name: 'Squeeze Early Warning' },
    { id: 'calculate_delta_exposure', name: 'Delta Exposure' },
    { id: 'calculate_gamma_exposure', name: 'Gamma Exposure' },
    { id: 'calculate_vega_exposure', name: 'Vega Exposure' },
    { id: 'calculate_cross_greeks', name: 'Cross-Greeks Analysis' },
    { id: 'calculate_theta_decay', name: 'Theta Decay Profile' },
    { id: 'construct_dynamic_hedge', name: 'Dynamic Hedge Builder' },
    { id: 'analyze_pca_eigen_portfolios', name: 'PCA Eigen Portfolio' },
    { id: 'model_volatility_surface', name: 'Vol Surface Modeling' },
    { id: 'model_greeks_surface', name: 'Greeks Surface Modeling' },
    { id: 'analyze_dealer_gamma_regime', name: 'Dealer Gamma Regime' },
    { id: 'analyze_vanna_charm_flow', name: 'Vanna & Charm Flow' },
    { id: 'analyze_iv_rv_vs_peers', name: 'IV vs RV Screener' },
    { id: 'analyze_gex_levels', name: 'GEX Alpha Signals' },
    { id: 'analyze_herding_regime', name: 'Herding Regime Detector' },
    { id: 'analyze_instanton_crash', name: 'Instanton Crash Analyzer' },
  ],
  structuring: [
    { id: 'price_interest_rate_swap', name: 'Interest Rate Swap' },
    { id: 'price_swaption', name: 'Swaption Pricing' },
    { id: 'price_credit_default_swap', name: 'Credit Default Swap' },
    { id: 'price_variance_swap', name: 'Variance Swap' },
    { id: 'price_dispersion_trade', name: 'Dispersion Trade' },
    { id: 'price_exotic_derivatives', name: 'Exotic Derivatives' },
    { id: 'price_equity_options', name: 'Equity Options Pricing' },
    { id: 'model_volatility_surface', name: 'Vol Surface Modeling' },
    { id: 'model_greeks_surface', name: 'Greeks Surface Modeling' },
    { id: 'calculate_delta_exposure', name: 'Delta Exposure' },
    { id: 'calculate_gamma_exposure', name: 'Gamma Exposure' },
    { id: 'calculate_vega_exposure', name: 'Vega Exposure' },
    { id: 'calculate_cross_greeks', name: 'Cross-Greeks Analysis' },
    { id: 'analyze_dealer_gamma_regime', name: 'Dealer Gamma Regime' },
  ],
  quant: [
    { id: 'forecast_arima', name: 'ARIMA Forecasting' },
    { id: 'forecast_arimax_macro', name: 'ARIMAX Macro Forecast' },
    { id: 'analyze_recession_field', name: 'Recession Field Theory' },
    { id: 'analyze_pca_eigen_portfolios', name: 'PCA Factor Analysis' },
    { id: 'analyze_feature_importance', name: 'ML Feature Importance' },
    { id: 'identify_cointegrated_pairs', name: 'Cointegration Finder' },
    { id: 'calculate_hedge_ratio', name: 'Optimal Hedge Ratio' },
    { id: 'compute_optimal_hedge_path', name: 'Dijkstra Hedge Pathfinder' },
    { id: 'generate_mean_reversion_signals', name: 'Mean Reversion Signals' },
    { id: 'price_correlation_swap', name: 'Correlation Swap' },
    { id: 'analyze_correlation_matrix', name: 'Correlation Analysis' },
    { id: 'analyze_graph_theory_risk', name: 'Graph Theory Network Risk' },
    { id: 'analyze_systemic_risk_score', name: 'Systemic Risk Score' },
    { id: 'detect_squeeze_setup', name: 'Squeeze Early Warning' },
    { id: 'calculate_delta_exposure', name: 'Delta Exposure' },
    { id: 'calculate_gamma_exposure', name: 'Gamma Exposure' },
    { id: 'calculate_vega_exposure', name: 'Vega Exposure' },
    { id: 'calculate_cross_greeks', name: 'Cross-Greeks' },
    { id: 'calculate_theta_decay', name: 'Theta Decay' },
    { id: 'construct_dynamic_hedge', name: 'Dynamic Hedging' },
    { id: 'price_equity_options', name: 'Options Pricing' },
    { id: 'model_volatility_surface', name: 'Vol Surface Modeling' },
    { id: 'model_greeks_surface', name: 'Greeks Surface Modeling' },
    { id: 'analyze_dealer_gamma_regime', name: 'Dealer Gamma Regime' },
    { id: 'analyze_vanna_charm_flow', name: 'Vanna & Charm Flow' },
    { id: 'analyze_iv_rv_vs_peers', name: 'IV vs RV Screener' },
    { id: 'analyze_gex_levels', name: 'GEX Alpha Signals' },
    { id: 'detect_signal_confluence', name: 'Signal Confluence' },
    { id: 'scan_universe_confluence', name: 'Universe Confluence Scan' },
    { id: 'analyze_earnings_patterns', name: 'Earnings Pattern Analyzer' },
    { id: 'scan_nope_divergences', name: 'NOPE Divergence Scanner' },
    { id: 'analyze_sector_rotation_flow', name: 'Sector Rotation Flow' },
    { id: 'analyze_herding_regime', name: 'Herding Regime Detector' },
    { id: 'analyze_instanton_crash', name: 'Instanton Crash Analyzer' },
    { id: 'analyze_portfolio_geodesic_distance', name: 'Portfolio Geodesic Distance' },
  ],
  dcf: [
    { id: 'gather_dcf_data_sources', name: 'Gather DCF Inputs' },
    { id: 'analyze_three_stage_dcf', name: '3-Stage Growth DCF' },
    { id: 'analyze_two_stage_dcf', name: '2-Stage Growth DCF' },
    { id: 'analyze_stable_stage_dcf', name: 'Stable Growth DCF' },
    { id: 'analyze_reverse_dcf', name: 'Reverse DCF (Implied Growth)' },
    { id: 'analyze_epv', name: 'EPV (Earnings Power Value)' },
    { id: 'analyze_monte_carlo_dcf', name: 'Monte Carlo DCF (Probabilistic)' },
    { id: 'dcf_sensitivity_analysis', name: 'Sensitivity Analysis' },
  ],
  multiples: [
    { id: 'analyze_comparable_companies', name: 'Peer Comp Analysis' },
  ],
  options: [
    { id: 'price_equity_options', name: 'Options Pricing (BS/Binomial)' },
    { id: 'detect_squeeze_setup', name: 'Squeeze Early Warning' },
    { id: 'calculate_delta_exposure', name: 'Portfolio Delta' },
    { id: 'calculate_gamma_exposure', name: 'Portfolio Gamma' },
    { id: 'calculate_vega_exposure', name: 'Portfolio Vega' },
    { id: 'calculate_theta_decay', name: 'Theta Decay Analysis' },
    { id: 'calculate_cross_greeks', name: 'Cross-Greeks Matrix' },
    { id: 'construct_dynamic_hedge', name: 'Dynamic Delta Hedge' },
    { id: 'model_volatility_surface', name: 'Vol Surface (SABR/SVI)' },
    { id: 'model_greeks_surface', name: 'Greeks Surface Modeling' },
    { id: 'analyze_dealer_gamma_regime', name: 'Dealer Gamma Levels' },
    { id: 'analyze_vanna_charm_flow', name: 'Vanna & Charm Analysis' },
    { id: 'analyze_iv_rv_vs_peers', name: 'IV/RV Peer Comparison' },
    { id: 'analyze_gex_levels', name: 'GEX Alpha Signals' },
    { id: 'detect_signal_confluence', name: 'Signal Confluence' },
    { id: 'analyze_earnings_patterns', name: 'Earnings Pattern Analyzer' },
    { id: 'scan_nope_divergences', name: 'NOPE Divergence Scanner' },
  ],
  alternatives: [
    { id: 'analyze_crypto_equity_beta_regime', name: 'Crypto-Equity Beta Regime' },
    { id: 'analyze_commodity_ratio', name: 'Commodity Ratio Analysis' },
    { id: 'screen_forex_carry_trades', name: 'FX Carry Trade Screener' },
    { id: 'analyze_commodity_seasonality', name: 'Commodity Seasonality' },
    { id: 'screen_commodity_momentum', name: 'Commodity Momentum Screener' },
  ],
  funds_products: [
    { id: 'forecast_tearsheet_returns', name: 'Tearsheet ARIMA Forecast' },
    { id: 'forecast_tearsheet_with_macro', name: 'Tearsheet ARIMAX + Macro' },
    { id: 'compare_fund_returns', name: 'Multi-Fund Comparison' },
  ],
  screener: [
    { id: 'screen_stocks', name: 'Stock Screener' },
  ],
  generalist: [
    { id: 'analyze_news_sentiment', name: 'FinBERT Sentiment Analysis' },
  ],
};

// Agent colors for styling
const agentColors: Record<string, string> = {
  risk: '#ef4444',
  structuring: '#6366f1',
  quant: '#ec4899',
  dcf: '#059669',
  multiples: '#8b5cf6',
  options: '#f97316',
  alternatives: '#f59e0b',
  funds_products: '#10b981',
  screener: '#3b82f6',
  generalist: '#6b7280',
};

const ToolPrioritySelector: React.FC<ToolPrioritySelectorProps> = ({
  agentMode,
  selectedTools,
  onToolsChange,
  disabled = false,
  direction = 'up',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const availableTools = customToolsMap[agentMode] || [];
  const hasTools = availableTools.length > 0;
  const agentColor = agentColors[agentMode] || '#6b7280';

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleTool = (toolId: string) => {
    if (selectedTools.includes(toolId)) {
      onToolsChange(selectedTools.filter(t => t !== toolId));
    } else {
      onToolsChange([...selectedTools, toolId]);
    }
  };

  const hasSelections = selectedTools.length > 0;
  const isDisabled = disabled || !hasTools || agentMode === 'auto';

  // Split tools into two columns
  const midpoint = Math.ceil(availableTools.length / 2);
  const leftColumn = availableTools.slice(0, midpoint);
  const rightColumn = availableTools.slice(midpoint);

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={isDisabled}
        onClick={() => !isDisabled && setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '2px',
          padding: '6px 8px',
          background: hasSelections ? `${agentColor}15` : 'transparent',
          border: 'none',
          borderRadius: '6px',
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          opacity: isDisabled ? 0.4 : 1,
          transition: 'all 0.2s',
        }}
        onMouseEnter={(e) => {
          if (!isDisabled) e.currentTarget.style.background = hasSelections ? `${agentColor}25` : '#f3f4f6';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = hasSelections ? `${agentColor}15` : 'transparent';
        }}
        title={
          agentMode === 'auto' ? 'Select an agent to prioritize tools'
            : !hasTools ? 'No custom tools for this agent'
            : hasSelections ? `${selectedTools.length} tool(s) prioritized`
            : 'Prioritize specific tools'
        }
      >
        <Wrench size={18} style={{ color: hasSelections ? agentColor : '#6b7280' }} />
        {hasSelections && (
          <span style={{
            fontSize: '0.625rem',
            background: agentColor,
            color: '#fff',
            borderRadius: '0.25rem',
            padding: '0 0.25rem',
            minWidth: '0.875rem',
            textAlign: 'center',
            fontWeight: 600,
          }}>
            {selectedTools.length}
          </span>
        )}
        <ChevronDown size={12} style={{ opacity: 0.4, transform: direction === 'up' ? 'rotate(180deg)' : 'none' }} />
      </button>

      {isOpen && !disabled && (
        <div
          style={{
            position: 'absolute',
            ...(direction === 'up' ? { bottom: '100%', marginBottom: '0.5rem' } : { top: '100%', marginTop: '0.5rem' }),
            right: 0,
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '0.5rem',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 1000,
            minWidth: '280px',
            maxHeight: '320px',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '0.5rem 0.75rem',
            borderBottom: '1px solid #e5e7eb',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#f9fafb',
          }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#374151' }}>
              Prioritize Tools
            </span>
            {hasSelections && (
              <button
                type="button"
                onClick={() => onToolsChange([])}
                style={{
                  fontSize: '0.6875rem',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#6b7280',
                  padding: '0.125rem 0.375rem',
                  borderRadius: '0.25rem',
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                onMouseLeave={(e) => e.currentTarget.style.color = '#6b7280'}
              >
                Clear
              </button>
            )}
          </div>

          {/* Two Column List */}
          <div style={{
            display: 'flex',
            gap: '0',
            padding: '0.5rem',
            maxHeight: '260px',
            overflowY: 'auto',
          }}>
            {/* Left Column */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              {leftColumn.map((tool) => {
                const isSelected = selectedTools.includes(tool.id);
                return (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={() => toggleTool(tool.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.375rem 0.5rem',
                      fontSize: '0.75rem',
                      fontWeight: isSelected ? 600 : 400,
                      background: 'transparent',
                      border: 'none',
                      borderRadius: '0.25rem',
                      cursor: 'pointer',
                      color: isSelected ? agentColor : '#4b5563',
                      textAlign: 'left',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#f3f4f6'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <div style={{
                      width: '14px',
                      height: '14px',
                      borderRadius: '3px',
                      border: isSelected ? `2px solid ${agentColor}` : '1.5px solid #d1d5db',
                      background: isSelected ? agentColor : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      {isSelected && <Check size={10} style={{ color: '#fff' }} />}
                    </div>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {tool.name}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Right Column */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              {rightColumn.map((tool) => {
                const isSelected = selectedTools.includes(tool.id);
                return (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={() => toggleTool(tool.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.375rem 0.5rem',
                      fontSize: '0.75rem',
                      fontWeight: isSelected ? 600 : 400,
                      background: 'transparent',
                      border: 'none',
                      borderRadius: '0.25rem',
                      cursor: 'pointer',
                      color: isSelected ? agentColor : '#4b5563',
                      textAlign: 'left',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#f3f4f6'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <div style={{
                      width: '14px',
                      height: '14px',
                      borderRadius: '3px',
                      border: isSelected ? `2px solid ${agentColor}` : '1.5px solid #d1d5db',
                      background: isSelected ? agentColor : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      {isSelected && <Check size={10} style={{ color: '#fff' }} />}
                    </div>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {tool.name}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolPrioritySelector;
