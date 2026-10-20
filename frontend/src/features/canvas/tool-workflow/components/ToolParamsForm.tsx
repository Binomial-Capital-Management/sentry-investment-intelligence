/**
 * SchemaForm - Dynamic form renderer based on tool params_schema
 * 
 * Renders form inputs automatically based on the schema returned by /api/canvas/tools.
 * No more hardcoding config UIs per tool.
 */

import { useState, useEffect, useRef } from 'react';
import { TickerPicker } from '@/features/canvas/shared/symbol-search';

// Schema types from backend
interface ParamSchema {
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required?: boolean;
  default?: any;
  description?: string;
  enum?: string[];
  min?: number;
  max?: number;
  items?: string | { type: string; properties?: any; required?: string[] };
  example?: any;
  use_ticker_search?: boolean;
}

interface Portfolio {
  id: string;
  name: string;
  tickers: string[];
  weights: number[];
}

interface SchemaFormProps {
  schema: Record<string, ParamSchema>;
  values: Record<string, any>;
  onChange: (values: Record<string, any>) => void;
  excludeFields?: string[]; // Fields handled elsewhere (e.g., tickers, portfolio_id)
  portfolios?: Portfolio[]; // For rendering portfolio dropdowns
}

// Conditional display rules: field → condition
const CONDITIONAL_FIELDS: Record<string, (values: Record<string, any>) => boolean> = {
  'custom_factors': (values) => values.factor_set === 'custom',
  'n_regimes': (values) => values.use_hmm === true,
  // Hide auto-ARIMA search params when manual order is specified
  'max_p': (values) => !values.arima_order || values.arima_order.trim() === '',
  'max_q': (values) => !values.arima_order || values.arima_order.trim() === '',
  'stepwise': (values) => !values.arima_order || values.arima_order.trim() === '',
  // Exotic derivatives: show params based on derivative_type
  'barrier_type': (values) => values.derivative_type === 'barrier',
  'barrier_level': (values) => values.derivative_type === 'barrier',
  'averaging_type': (values) => values.derivative_type === 'asian',
  'averaging_frequency': (values) => values.derivative_type === 'asian',
  'lookback_type': (values) => values.derivative_type === 'lookback',
  'digital_payoff': (values) => values.derivative_type === 'digital',
  // Option pricing: show params based on pricing_model OR Correlation Swap forward pricing
  'num_simulations': (values) => values.pricing_model === 'monte_carlo' || values.pricing_mode === 'forward',
  'american': (values) => values.pricing_model === 'binomial',
  // NOPE: show params based on screener (check for undefined = default to custom)
  'tickers': (values) => !values.screener || values.screener === 'custom',
  'etf_ticker': (values) => values.screener === 'etf_holdings',
  'sector': (values) => values.screener === 'sector',
  // ARIMAX: show stock_symbol/macro_indicator based on forecast_mode (no default, user must choose)
  'stock_symbol': (values) => values.forecast_mode === 'stock',
  'macro_indicator': (values) => values.forecast_mode === 'macro',
  // Rolling Correlation: show ticker_x when input_type_x is 'ticker'
  'ticker_x': (values) => values.input_type_x === 'ticker',
  // Rolling Correlation: show x_portfolio_id when input_type_x is 'portfolio'
  'x_portfolio_id': (values) => values.input_type_x === 'portfolio',
  // Rolling Correlation: show ticker_y when input_type_y is 'ticker'
  'ticker_y': (values) => values.input_type_y === 'ticker',
  // Rolling Correlation / Correlation Swap: show y_portfolio_id when input_type_y is 'portfolio'
  'y_portfolio_id': (values) => values.input_type_y === 'portfolio',
  // Correlation Swap: show asset_x when input_type_x is 'ticker'
  'asset_x': (values) => values.input_type_x === 'ticker',
  // Correlation Swap: show asset_y when input_type_y is 'ticker'
  'asset_y': (values) => values.input_type_y === 'ticker',
  // Correlation Swap: show days_remaining when pricing_mode is 'forward'
  'days_remaining': (values) => values.pricing_mode === 'forward',
  // Greek Exposure: show days_forward only when greek_type is 'theta'
  'days_forward': (values) => values.greek_type === 'theta',
  // Traditional DCF: show stage1_years only for 2-stage and 3-stage
  'stage1_years': (values) => values.stages === '2' || values.stages === '3',
  // Traditional DCF: show stage2_years only when stages is '3'
  'stage2_years': (values) => values.stages === '3',
  // Hedge Ratio: show window only when method is not 'tls' (TLS doesn't support rolling windows)
  'window': (values) => values.method !== 'tls',
  // Hedge Ratio: show primary_asset when input_type_primary is 'ticker'
  'primary_asset': (values) => values.input_type_primary === 'ticker',
  // Hedge Ratio: show primary_portfolio_id when input_type_primary is 'portfolio'
  'primary_portfolio_id': (values) => values.input_type_primary === 'portfolio',
  // Hedge Ratio: show hedge_asset when input_type_hedge is 'ticker'
  'hedge_asset': (values) => values.input_type_hedge === 'ticker',
  // Hedge Ratio: show hedge_portfolio_id when input_type_hedge is 'portfolio'
  'hedge_portfolio_id': (values) => values.input_type_hedge === 'portfolio',
};

export default function SchemaForm({ schema, values, onChange, excludeFields = [], portfolios = [] }: SchemaFormProps) {
  // Initialize values from defaults
  useEffect(() => {
    const defaults: Record<string, any> = {};
    let hasChanges = false;
    
    Object.entries(schema).forEach(([key, param]) => {
      if (excludeFields.includes(key)) return;
      if (values[key] === undefined && param.default !== undefined) {
        defaults[key] = param.default;
        hasChanges = true;
      }
    });
    
    if (hasChanges) {
      onChange({ ...values, ...defaults });
    }
  }, [schema]);

  const updateValue = (key: string, value: any) => {
    onChange({ ...values, [key]: value });
  };

  // Filter out excluded fields and conditionally hidden fields
  const visibleFields = Object.entries(schema).filter(([key]) => {
    if (excludeFields.includes(key)) return false;
    // Check conditional display rules
    const condition = CONDITIONAL_FIELDS[key];
    if (condition && !condition(values)) return false;
    return true;
  });

  if (visibleFields.length === 0) {
    return (
      <div style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 30%)', padding: '1rem 0', textAlign: 'center' }}>
        No configuration options
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {visibleFields.map(([key, param]) => (
        <FieldRenderer
          key={key}
          name={key}
          param={param}
          value={values[key]}
          onChange={(val) => updateValue(key, val)}
          portfolios={portfolios}
        />
      ))}
    </div>
  );
}

// Custom Dropdown Component
interface DropdownProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

function Dropdown({ options, value, onChange, placeholder = 'Select...' }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          padding: '0.325rem 0.5rem',
          fontSize: '0.688rem',
          fontWeight: 500,
          textAlign: 'left' as const,
          border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
          borderRadius: '0.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.25rem',
          color: value ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
          backgroundColor: 'white',
          cursor: 'pointer',
          transition: 'all 0.1s ease',
        }}
      >
        <span>{value ? formatLabel(value) : placeholder}</span>
        <svg
          className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
          style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0 }}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div
          className="absolute z-50 w-full mt-0.5 overflow-auto"
          style={{
            backgroundColor: 'white',
            border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
            borderRadius: '0.5rem',
            boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
            maxHeight: 180,
            padding: '0.125rem',
          }}
        >
          {options.map((opt) => {
            const isSelected = value === opt;
            return (
              <button
                key={opt}
                type="button"
                onClick={() => { onChange(opt); setIsOpen(false); }}
                style={{
                  width: '100%',
                  padding: '0.25rem 0.5rem',
                  fontSize: '0.625rem',
                  fontWeight: isSelected ? 500 : 400,
                  textAlign: 'left' as const,
                  borderRadius: '0.375rem',
                  border: 'none',
                  backgroundColor: isSelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                  color: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 60%)',
                  cursor: 'pointer',
                  transition: 'background-color 0.1s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
                onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'hsl(210 10% 87% / 50%)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = isSelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent'; }}
              >
                <span>{formatLabel(opt)}</span>
                {isSelected && (
                  <svg style={{ width: 10, height: 10 }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Individual field renderer
interface FieldRendererProps {
  name: string;
  param: ParamSchema;
  value: any;
  onChange: (value: any) => void;
  portfolios?: Portfolio[];
}

function FieldRenderer({ name, param, value, onChange, portfolios = [] }: FieldRendererProps) {
  const label = formatLabel(name);
  
  // Portfolio dropdown for *_portfolio_id fields (e.g., compare_to_portfolio_id)
  if (name.endsWith('_portfolio_id') && portfolios.length > 0) {
    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center', marginBottom: '0.25rem' }}>
          {label}
          <InfoTooltip fieldName={name} />
        </label>
        <div className="relative">
          <select
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value || undefined)}
            style={{
              width: '100%',
              padding: '0.325rem 1.5rem 0.325rem 0.5rem',
              fontSize: '0.688rem',
              fontWeight: 500,
              border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
              borderRadius: '0.5rem',
              appearance: 'none' as const,
              cursor: 'pointer',
              color: 'hsl(60 2.5% 23.3%)',
              backgroundColor: 'white',
            }}
          >
            <option value="">None</option>
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.tickers?.length || 0})
              </option>
            ))}
          </select>
          <svg style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', pointerEvents: 'none' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }
  
  // Enum dropdown - use custom dropdown
  if (param.enum && param.type === 'string') {
    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center', marginBottom: '0.25rem' }}>
          {label}
          <InfoTooltip fieldName={name} />
        </label>
        <Dropdown
          options={param.enum}
          value={value ?? param.default ?? ''}
          onChange={onChange}
        />
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }

  // Boolean toggle (chip style)
  if (param.type === 'boolean') {
    const isOn = value ?? param.default ?? false;
    return (
      <div style={{ border: '0.5px solid hsl(30 3.3% 11.8% / 12%)', borderRadius: '0.5rem', padding: '0.375rem 0.5rem' }}>
        <div className="flex items-start justify-between gap-2">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.688rem', fontWeight: 500, color: 'hsl(60 2.5% 23.3%)', display: 'flex', alignItems: 'center' }}>
              {label}
              <InfoTooltip fieldName={name} />
            </div>
            {param.description && (
              <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 35%)', marginTop: 1 }}>{param.description}</div>
            )}
          </div>
          <button
            type="button"
            onClick={() => onChange(!isOn)}
            style={{
              padding: '0.125rem 0.5rem',
              fontSize: '0.5rem',
              fontWeight: 500,
              borderRadius: '0.375rem',
              border: isOn ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
              backgroundColor: isOn ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
              color: isOn ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 45%)',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              flexShrink: 0,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            {isOn ? 'On' : 'Off'}
          </button>
        </div>
      </div>
    );
  }

  // Number with range slider (if min/max defined)
  if (param.type === 'number' && param.min !== undefined && param.max !== undefined) {
    const val = value ?? param.default ?? param.min;
    const step = getStep(param.min, param.max);
    const presets = FIELD_PRESETS[name];

    return (
      <div>
        <div className="flex justify-between items-center" style={{ marginBottom: '0.25rem' }}>
          <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center' }}>
            {label}
            <InfoTooltip fieldName={name} />
          </label>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: 'hsl(60 2.5% 23.3%)', backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {formatNumberValue(val, name)}
          </span>
        </div>
        <input
          type="range"
          min={param.min}
          max={param.max}
          step={step}
          value={val}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-1 rounded-full appearance-none cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-3
            [&::-webkit-slider-thumb]:h-3
            [&::-webkit-slider-thumb]:bg-gray-900
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div className="flex justify-between" style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>{formatNumberValue(param.min, name)}</span>
          <span>{formatNumberValue(param.max, name)}</span>
        </div>
        {presets && (
          <div className="flex flex-wrap gap-1" style={{ marginTop: '0.375rem' }}>
            {presets.map((preset) => (
              <button
                key={preset.value}
                type="button"
                onClick={() => onChange(preset.value)}
                style={{
                  padding: '0.125rem 0.375rem',
                  fontSize: '0.5rem',
                  fontWeight: 500,
                  borderRadius: '0.375rem',
                  border: val === preset.value ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                  backgroundColor: val === preset.value ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                  color: val === preset.value ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 45%)',
                  cursor: 'pointer',
                  transition: 'all 0.1s ease',
                }}
              >
                {preset.label}
              </button>
            ))}
          </div>
        )}
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }

  // Number input (no range)
  if (param.type === 'number') {
    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center', marginBottom: '0.25rem' }}>
          {label}
          <InfoTooltip fieldName={name} />
        </label>
        <input
          type="number"
          value={value ?? param.default ?? ''}
          onChange={(e) => onChange(Number(e.target.value))}
          min={param.min}
          max={param.max}
          className="focus:outline-none"
          style={{
            width: '100%',
            padding: '0.325rem 0.5rem',
            fontSize: '0.688rem',
            fontFamily: 'monospace',
            border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
            borderRadius: '0.5rem',
            color: 'hsl(60 2.5% 23.3%)',
          }}
        />
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }

  // Object input (JSON editor for custom factors, etc.)
  if (param.type === 'object') {
    return (
      <ObjectFieldRenderer
        name={name}
        param={param}
        value={value}
        onChange={onChange}
      />
    );
  }

  // Array with enum = multi-select checkboxes
  if (param.type === 'array' && param.enum) {
    const selectedValues = Array.isArray(value) ? value : (param.default || []);
    
    // Human-readable labels for FMP field names
    const fieldLabels: Record<string, string> = {
      'priceToEarningsRatio': 'P/E Ratio',
      'priceToEarningsRatioTTM': 'P/E Ratio (TTM)',
      'evToEBITDA': 'EV/EBITDA',
      'evToEBITDATTM': 'EV/EBITDA (TTM)',
      'evToSales': 'EV/Sales',
      'evToSalesTTM': 'EV/Sales (TTM)',
      'evToFreeCashFlow': 'EV/FCF',
      'evToFreeCashFlowTTM': 'EV/FCF (TTM)',
      'priceToBookRatio': 'P/Book',
      'priceToBookRatioTTM': 'P/Book (TTM)',
      'priceToSalesRatio': 'P/Sales',
      'priceToSalesRatioTTM': 'P/Sales (TTM)',
      'priceToFreeCashFlowRatio': 'P/FCF',
      'priceToFreeCashFlowRatioTTM': 'P/FCF (TTM)',
      'priceToOperatingCashFlowRatio': 'P/OCF',
      'priceToOperatingCashFlowRatioTTM': 'P/OCF (TTM)',
      'priceToEarningsGrowthRatio': 'PEG Ratio',
      'dividendYield': 'Dividend Yield',
      'dividendYieldTTM': 'Dividend Yield (TTM)',
      'earningsYield': 'Earnings Yield',
      'earningsYieldTTM': 'Earnings Yield (TTM)',
      'roe': 'ROE',
      'grossProfitMargin': 'Gross Margin',
      'grossProfitMarginTTM': 'Gross Margin (TTM)',
      'operatingProfitMargin': 'Operating Margin',
      'operatingProfitMarginTTM': 'Operating Margin (TTM)',
      'netProfitMargin': 'Net Margin',
      'netProfitMarginTTM': 'Net Margin (TTM)',
      'ebitdaMargin': 'EBITDA Margin',
      'ebitdaMarginTTM': 'EBITDA Margin (TTM)',
      'netDebtToEBITDA': 'Net Debt/EBITDA',
      'netDebtToEBITDATTM': 'Net Debt/EBITDA (TTM)',
      'enterpriseValue': 'Enterprise Value',
      'marketCap': 'Market Cap',
      // Commodity symbols
      'GCUSD': 'Gold (GC)',
      'SIUSD': 'Silver (SI)',
      'CLUSD': 'Crude Oil (CL)',
      'NGUSD': 'Natural Gas (NG)',
      'HGUSD': 'Copper (HG)',
      'BZUSD': 'Brent Crude (BZ)',
      'PLUSD': 'Platinum (PL)',
      'PAUSD': 'Palladium (PA)',
      'ZCUSD': 'Corn (ZC)',
      'ZSUSD': 'Soybeans (ZS)',
      'ZMUSD': 'Soybean Meal (ZM)',
      'ZLUSD': 'Soybean Oil (ZL)',
      'ZWUSD': 'Wheat (ZW)',
      'KCUSD': 'Coffee (KC)',
      'SBUSD': 'Sugar (SB)',
      'CCUSD': 'Cocoa (CC)',
      'CTUSD': 'Cotton (CT)',
      'LCUSD': 'Live Cattle (LC)',
      'LHUSD': 'Lean Hogs (LH)',
      // Crypto symbols
      'BTCUSD': 'Bitcoin (BTC)',
      'ETHUSD': 'Ethereum (ETH)',
      'SOLUSD': 'Solana (SOL)',
      'XRPUSD': 'Ripple (XRP)',
      'ADAUSD': 'Cardano (ADA)',
      'DOGEUSD': 'Dogecoin (DOGE)',
      'AVAXUSD': 'Avalanche (AVAX)',
      'MATICUSD': 'Polygon (MATIC)',
      'DOTUSD': 'Polkadot (DOT)',
      'LINKUSD': 'Chainlink (LINK)',
      // Equity symbols
      'SPY': 'S&P 500 (SPY)',
      'QQQ': 'Nasdaq 100 (QQQ)',
      'IWM': 'Russell 2000 (IWM)',
      'DIA': 'Dow Jones (DIA)',
      'VTI': 'Total Stock Mkt (VTI)',
      'XLK': 'Tech Sector (XLK)',
      'XLF': 'Financials (XLF)',
      'XLE': 'Energy (XLE)',
      'ARKK': 'ARK Innovation (ARKK)',
      'TLT': '20+ Yr Treasury (TLT)',
    };
    
    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'block', marginBottom: '0.25rem' }}>
          {label}
        </label>
        <div className="flex flex-wrap gap-1">
          {param.enum.map((option) => {
            const isSelected = selectedValues.includes(option);
            const displayLabel = fieldLabels[option] || option;
            return (
              <button
                key={option}
                type="button"
                onClick={() => {
                  const newValues = isSelected
                    ? selectedValues.filter((v: string) => v !== option)
                    : [...selectedValues, option];
                  onChange(newValues);
                }}
                style={{
                  padding: '0.125rem 0.375rem',
                  fontSize: '0.5rem',
                  fontWeight: 500,
                  borderRadius: '0.375rem',
                  border: isSelected ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                  backgroundColor: isSelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                  color: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 45%)',
                  cursor: 'pointer',
                  transition: 'all 0.1s ease',
                }}
              >
                {displayLabel}
              </button>
            );
          })}
        </div>
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }

  // Array input (comma-separated) - fallback for arrays without enum
  if (param.type === 'array') {
    const arrValue = Array.isArray(value) ? value.join(', ') : '';
    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'block', marginBottom: '0.25rem' }}>
          {label}
        </label>
        <input
          type="text"
          value={arrValue}
          onChange={(e) => {
            const items = e.target.value.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
            const parsed = param.items === 'number' ? items.map(Number) : items;
            onChange(parsed);
          }}
          placeholder={param.items === 'number' ? '0.25, 0.25, 0.5' : 'AAPL, MSFT, GOOGL'}
          className="focus:outline-none"
          style={{
            width: '100%',
            padding: '0.325rem 0.5rem',
            fontSize: '0.688rem',
            border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
            borderRadius: '0.5rem',
            color: 'hsl(60 2.5% 23.3%)',
          }}
        />
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }

  // Single ticker field - use SingleTickerSearch for any field with 'ticker' or 'asset' in the name
  // This includes: ticker, ticker_x, ticker_y, asset_x, asset_y, stock_symbol, index_ticker, etf_ticker, primary_asset, hedge_asset, etc.
  if (param.type === 'string' && (name.includes('ticker') || name.includes('asset') || name === 'stock_symbol')) {
    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center', marginBottom: '0.25rem' }}>
          {label}
          <InfoTooltip fieldName={name} />
        </label>
        <TickerPicker
          mode="single"
          selectedSymbols={value ? [value] : []}
          onSelect={(t) => onChange(t.symbol)}
          placeholder="Select ticker..."
        />
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }
  
  // Peers field - use MultiTickerSearch for comma-separated ticker fields
  const isTickerListField = name === 'peers' || name === 'peer_tickers' || name === 'tickers' ||
    (param.description?.toLowerCase().includes('ticker') && param.description?.toLowerCase().includes('comma'));
  
  if (param.type === 'string' && isTickerListField) {
    const tickers = value ? value.split(/[,\s]+/).filter(Boolean).map((t: string) => t.toUpperCase()) : [];

    return (
      <div>
        <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'block', marginBottom: '0.25rem' }}>
          {label}
        </label>
        <TickerPicker
          mode="multi"
          selectedSymbols={tickers}
          onSelect={(t) => onChange([...tickers, t.symbol].join(', '))}
          onRemove={(sym) => onChange(tickers.filter((t: string) => t !== sym).join(', '))}
          placeholder="Select peers..."
          maxTickers={10}
        />
        {param.description && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
        )}
      </div>
    );
  }

  // Special handling for arima_order field - interactive p,d,q selection
  if (name === 'arima_order') {
    // Parse current value or default to auto
    const parseOrder = (val: string | undefined): { mode: 'auto' | 'manual'; p: number; d: number; q: number } => {
      if (!val || val.trim() === '') return { mode: 'auto', p: 5, d: 1, q: 5 };
      const parts = val.split(',').map(x => parseInt(x.trim()));
      if (parts.length === 3 && parts.every(n => !isNaN(n))) {
        return { mode: 'manual', p: parts[0], d: parts[1], q: parts[2] };
      }
      return { mode: 'auto', p: 5, d: 1, q: 5 };
    };
    
    const order = parseOrder(value);
    const isManual = order.mode === 'manual';
    
    const updateOrder = (p: number, d: number, q: number) => {
      onChange(`${p},${d},${q}`);
    };
    
    return (
      <div className="space-y-2">
        <div>
          <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center', marginBottom: '0.25rem' }}>
            Mode
            <InfoTooltip fieldName={name} />
          </label>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => onChange('')}
              style={{
                flex: 1, padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: !isManual ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                backgroundColor: !isManual ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                color: !isManual ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 40%)',
              }}
            >
              Auto
            </button>
            <button
              type="button"
              onClick={() => updateOrder(order.p, order.d, order.q)}
              style={{
                flex: 1, padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: isManual ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                backgroundColor: isManual ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                color: isManual ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 40%)',
              }}
            >
              Manual
            </button>
          </div>
        </div>

        {isManual && (
          <div style={{ padding: '0.375rem', backgroundColor: 'hsl(30 3.3% 11.8% / 3%)', borderRadius: '0.5rem', border: '0.5px solid hsl(30 3.3% 11.8% / 8%)' }} className="space-y-2">
            <div style={{ fontSize: '0.563rem', fontWeight: 500, color: 'hsl(60 2.5% 23.3% / 50%)' }}>
              Order: <span style={{ fontFamily: 'monospace', backgroundColor: 'white', padding: '0.125rem 0.25rem', borderRadius: '0.25rem', border: '0.5px solid hsl(30 3.3% 11.8% / 12%)', color: 'hsl(60 2.5% 23.3%)' }}>({order.p}, {order.d}, {order.q})</span>
            </div>

            {/* P slider */}
            <div>
              <div className="flex justify-between items-center" style={{ marginBottom: 2 }}>
                <span style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 45%)' }}>p (AR)</span>
                <span style={{ fontSize: '0.563rem', fontFamily: 'monospace', fontWeight: 600, color: 'hsl(60 2.5% 23.3%)' }}>{order.p}</span>
              </div>
              <input type="range" min={0} max={15} value={order.p}
                onChange={(e) => updateOrder(Number(e.target.value), order.d, order.q)}
                className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
                style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
              />
            </div>

            {/* D selector */}
            <div>
              <span style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 45%)', display: 'block', marginBottom: 2 }}>d (diff)</span>
              <div className="flex gap-1">
                {[0, 1, 2].map((dVal) => (
                  <button key={dVal} type="button" onClick={() => updateOrder(order.p, dVal, order.q)}
                    style={{
                      flex: 1, padding: '0.2rem', fontSize: '0.563rem', fontWeight: 500,
                      borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                      border: order.d === dVal ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                      backgroundColor: order.d === dVal ? 'hsl(30 3.3% 11.8% / 8%)' : 'white',
                      color: order.d === dVal ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 40%)',
                    }}
                  >
                    {dVal}
                  </button>
                ))}
              </div>
            </div>

            {/* Q slider */}
            <div>
              <div className="flex justify-between items-center" style={{ marginBottom: 2 }}>
                <span style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 45%)' }}>q (MA)</span>
                <span style={{ fontSize: '0.563rem', fontFamily: 'monospace', fontWeight: 600, color: 'hsl(60 2.5% 23.3%)' }}>{order.q}</span>
              </div>
              <input type="range" min={0} max={15} value={order.q}
                onChange={(e) => updateOrder(order.p, order.d, Number(e.target.value))}
                className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
                style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
              />
            </div>

            {/* Presets */}
            <div style={{ paddingTop: '0.25rem', borderTop: '0.5px solid hsl(30 3.3% 11.8% / 8%)' }}>
              <div className="flex flex-wrap gap-1">
                {[
                  { label: 'Walk', p: 0, d: 1, q: 0 },
                  { label: 'AR(1)', p: 1, d: 1, q: 0 },
                  { label: 'ARMA', p: 1, d: 1, q: 1 },
                  { label: 'Weekly', p: 5, d: 1, q: 5 },
                ].map((preset) => {
                  const active = order.p === preset.p && order.d === preset.d && order.q === preset.q;
                  return (
                    <button key={preset.label} type="button" onClick={() => updateOrder(preset.p, preset.d, preset.q)}
                      style={{
                        padding: '0.125rem 0.375rem', fontSize: '0.5rem', fontWeight: 500,
                        borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                        border: active ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                        backgroundColor: active ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                        color: active ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 45%)',
                      }}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {!isManual && (
          <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)' }}>
            Auto-ARIMA searches for optimal (p,d,q) via AIC.
          </div>
        )}
      </div>
    );
  }

  // Default: string input
  return (
    <div>
      <label style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', display: 'flex', alignItems: 'center', marginBottom: '0.25rem' }}>
        {label}
        <InfoTooltip fieldName={name} />
      </label>
      <input
        type="text"
        value={value ?? param.default ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="focus:outline-none"
        style={{
          width: '100%',
          padding: '0.325rem 0.5rem',
          fontSize: '0.688rem',
          border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
          borderRadius: '0.5rem',
          color: 'hsl(60 2.5% 23.3%)',
        }}
      />
      {param.description && (
        <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.25rem' }}>{param.description}</div>
      )}
    </div>
  );
}

// Object field with key-value editor
function ObjectFieldRenderer({ name, param, value, onChange }: FieldRendererProps) {
  const [pairs, setPairs] = useState<Array<{ key: string; value: string }>>([]);
  const [isExpanded, setIsExpanded] = useState(false);

  // Initialize from value
  useEffect(() => {
    if (value && typeof value === 'object') {
      setPairs(Object.entries(value).map(([k, v]) => ({ key: k, value: String(v) })));
    } else if (param.example) {
      setPairs(Object.entries(param.example).map(([k, v]) => ({ key: k, value: String(v) })));
    }
  }, []);

  const updatePairs = (newPairs: Array<{ key: string; value: string }>) => {
    setPairs(newPairs);
    // Convert to object
    const obj: Record<string, string> = {};
    newPairs.forEach((p) => {
      if (p.key.trim()) obj[p.key.trim().toUpperCase()] = p.value.trim();
    });
    onChange(Object.keys(obj).length > 0 ? obj : undefined);
  };

  const addPair = () => {
    updatePairs([...pairs, { key: '', value: '' }]);
  };

  const removePair = (idx: number) => {
    updatePairs(pairs.filter((_, i) => i !== idx));
  };

  const updatePair = (idx: number, field: 'key' | 'value', val: string) => {
    const newPairs = [...pairs];
    newPairs[idx][field] = val;
    updatePairs(newPairs);
  };

  const label = formatLabel(name);

  return (
    <div style={{ border: '0.5px solid hsl(30 3.3% 11.8% / 12%)', borderRadius: '0.5rem', overflow: 'hidden' }}>
      <div
        className="flex items-center justify-between cursor-pointer"
        style={{ padding: '0.375rem 0.5rem', transition: 'background-color 0.1s ease' }}
        onClick={() => setIsExpanded(!isExpanded)}
        onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 3%)'}
        onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.backgroundColor = 'transparent'}
      >
        <div>
          <div style={{ fontSize: '0.688rem', fontWeight: 500, color: 'hsl(60 2.5% 23.3%)' }}>{label}</div>
          {param.description && (
            <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 35%)', marginTop: 1 }}>{param.description}</div>
          )}
        </div>
        <svg
          className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0 }}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {isExpanded && (
        <div className="space-y-1.5" style={{ padding: '0 0.5rem 0.375rem', borderTop: '0.5px solid hsl(30 3.3% 11.8% / 8%)' }}>
          {pairs.map((pair, idx) => (
            <div key={idx} className="flex items-center gap-1">
              <input
                type="text"
                value={pair.key}
                onChange={(e) => updatePair(idx, 'key', e.target.value)}
                placeholder="ETF"
                className="focus:outline-none"
                style={{ flex: 1, padding: '0.2rem 0.375rem', fontSize: '0.563rem', fontFamily: 'monospace', textTransform: 'uppercase', border: '0.5px solid hsl(30 3.3% 11.8% / 15%)', borderRadius: '0.375rem', color: 'hsl(60 2.5% 23.3%)' }}
              />
              <span style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 25%)' }}>→</span>
              <input
                type="text"
                value={pair.value}
                onChange={(e) => updatePair(idx, 'value', e.target.value)}
                placeholder="Factor"
                className="focus:outline-none"
                style={{ flex: 1, padding: '0.2rem 0.375rem', fontSize: '0.563rem', border: '0.5px solid hsl(30 3.3% 11.8% / 15%)', borderRadius: '0.375rem', color: 'hsl(60 2.5% 23.3%)' }}
              />
              <button
                onClick={() => removePair(idx)}
                style={{ padding: '0.125rem', color: 'hsl(60 2.5% 23.3% / 25%)', cursor: 'pointer', borderRadius: '0.25rem', transition: 'color 0.1s ease' }}
                onMouseEnter={e => (e.currentTarget as HTMLButtonElement).style.color = '#dc2626'}
                onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.color = 'hsl(60 2.5% 23.3% / 25%)'}
              >
                <svg style={{ width: 10, height: 10 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
          <button
            onClick={addPair}
            className="flex items-center gap-1"
            style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 35%)', cursor: 'pointer', padding: '0.125rem 0' }}
          >
            <svg style={{ width: 8, height: 8 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add factor
          </button>

          {param.example && (
            <div style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 25%)', marginTop: '0.25rem', paddingTop: '0.25rem', borderTop: '0.5px solid hsl(30 3.3% 11.8% / 8%)' }}>
              Example: {JSON.stringify(param.example)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Preset quick-select options for slider fields
const FIELD_PRESETS: Record<string, Array<{ value: number; label: string }>> = {
  max_p: [
    { value: 3, label: 'Fast' },
    { value: 5, label: 'Conservative' },
    { value: 10, label: 'Balanced' },
    { value: 15, label: 'Thorough' },
  ],
  max_q: [
    { value: 3, label: 'Fast' },
    { value: 5, label: 'Conservative' },
    { value: 10, label: 'Balanced' },
    { value: 15, label: 'Thorough' },
  ],
  seasonal_period: [
    { value: 5, label: 'Weekly' },
    { value: 21, label: 'Monthly' },
    { value: 63, label: 'Quarterly' },
    { value: 252, label: 'Yearly' },
  ],
  forecast_periods: [
    { value: 5, label: '1 Week' },
    { value: 10, label: '2 Weeks' },
    { value: 21, label: '1 Month' },
    { value: 30, label: '30 Days' },
    { value: 60, label: '2 Months' },
    { value: 90, label: '3 Months' },
  ],
};

// Extended tooltips for complex parameters (especially ARIMA)
const FIELD_TOOLTIPS: Record<string, { title: string; explanation: string; examples?: string[] }> = {
  arima_order: {
    title: 'ARIMA Order (p, d, q)',
    explanation: `p (AR) — How many past prices influence today.\nHigher p = longer price memory.\n\nd (Diff) — How many times to difference the series.\nd=1 models returns, d=2 models acceleration.\n\nq (MA) — How many past forecast errors matter.\nHigher q = longer shock memory.`,
    examples: [
      '0,1,0 → Random walk (baseline)',
      '1,1,0 → Simple momentum',
      '1,1,1 → Mean reversion with shocks',
      '5,1,5 → Weekly patterns',
      'Empty → Auto-select via AIC'
    ]
  },
  max_p: {
    title: 'Maximum AR Order',
    explanation: `Controls how far back the model looks for price patterns (momentum). Higher values can capture longer trends but risk overfitting.`,
    examples: ['3-5: Conservative, fast', '10: Balanced (default)', '15-20: Aggressive, slower']
  },
  max_q: {
    title: 'Maximum MA Order', 
    explanation: `Controls how long past shocks (earnings, news) affect forecasts. Higher values model persistent shock effects.`,
    examples: ['3-5: Quick shock decay', '10: Balanced (default)', '15-20: Long shock memory']
  },
  seasonal: {
    title: 'Seasonal ARIMA (SARIMA)',
    explanation: `Enables modeling of recurring patterns like weekly (Mon-Fri effects), monthly (options expiry), or quarterly (earnings) cycles.`,
    examples: ['Enable for stocks with clear weekly patterns', 'Disable for crypto or 24/7 markets']
  },
  seasonal_period: {
    title: 'Seasonality Period',
    explanation: `The cycle length in trading days. Common periods:
• 5 = Weekly (Mon-Fri pattern)
• 21 = Monthly (options expiry, rebalancing)
• 63 = Quarterly (earnings cycles)
• 252 = Yearly (tax loss harvesting, Santa rally)`,
    examples: ['5 for day-of-week effects', '21 for monthly options', '252 for annual patterns']
  },
  stepwise: {
    title: 'Search Method',
    explanation: `How the model searches for optimal (p,d,q):
• Stepwise (True): Fast heuristic search, good for interactive use
• Exhaustive (False): Tests all combinations, slower but may find better model`,
    examples: ['True for quick results', 'False for production/research quality']
  },
  forecast_periods: {
    title: 'Forecast Horizon',
    explanation: `Number of days to forecast ahead. Longer horizons have wider confidence intervals and more uncertainty. ARIMA is best for short-term forecasts.`,
    examples: ['5-10: High confidence', '30: Medium-term (default)', '60-90: Long-term, wider bands']
  },
  // Mean Reversion tooltips
  z_score_entry_long: {
    title: 'Long Entry Z-Score',
    explanation: `Enter a LONG position when price is this many standard deviations BELOW the rolling mean. More negative = more extreme oversold condition required.`,
    examples: ['-1.5: Aggressive (frequent signals)', '-2.0: Standard (balanced)', '-2.5: Conservative (rare signals)']
  },
  z_score_entry_short: {
    title: 'Short Entry Z-Score',
    explanation: `Enter a SHORT position when price is this many standard deviations ABOVE the rolling mean. Higher = more extreme overbought condition required.`,
    examples: ['1.5: Aggressive (frequent signals)', '2.0: Standard (balanced)', '2.5: Conservative (rare signals)']
  },
  z_score_exit: {
    title: 'Exit Z-Score',
    explanation: `Close position when price returns to within this range of the mean. Represents "mean reversion complete."`,
    examples: ['0.0: Wait for exact mean (risky)', '0.5: Near mean (standard)', '1.0: Exit early (safer)']
  },
  lookback_window: {
    title: 'Rolling Window',
    explanation: `Days used to calculate rolling mean and standard deviation. Shorter = more responsive, longer = more stable.`,
    examples: ['10: Fast, noisy', '20: Standard (1 month)', '40: Slow, smooth']
  },
  test_stationarity: {
    title: 'Stationarity Test (ADF)',
    explanation: `Runs Augmented Dickey-Fuller test to verify the price series is mean-reverting. If NOT stationary, the strategy may not work! A stationary series reverts to its mean; a non-stationary series can trend indefinitely.`,
    examples: ['Enable to validate strategy assumptions', 'p-value < 0.05 = stationary ✓']
  },
  direction: {
    title: 'Trading Direction',
    explanation: `Restrict which signals to take:
• Both: Long when oversold, short when overbought
• Long Only: Only buy dips (no shorting)
• Short Only: Only short rallies (bearish bias)`,
    examples: ['Both for full mean reversion', 'Long Only for retirement accounts']
  },
  // IV vs RV Screener tooltips
  rv_window: {
    title: 'Realized Volatility Window',
    explanation: `Number of trading days to calculate historical (realized) volatility. Shorter windows react faster to recent moves, longer windows are more stable.`,
    examples: ['10: Fast, recent moves', '20: Standard (1 month)', '30: Slower, more stable']
  },
  min_dte: {
    title: 'Minimum Days to Expiration',
    explanation: `Minimum option expiration for IV extraction. Shorter DTE options have higher gamma and are more sensitive to near-term events.`,
    examples: ['7: Very short-term IV', '14: 2-week minimum (standard)', '21: Skip weeklies']
  },
  max_dte: {
    title: 'Maximum Days to Expiration',
    explanation: `Maximum option expiration for IV extraction. Longer DTE captures term structure but may miss near-term events.`,
    examples: ['30: Near-term focus', '45: Standard (1-2 months)', '60-90: Longer-term view']
  }
};

// Info tooltip component for detailed parameter explanations
function InfoTooltip({ fieldName }: { fieldName: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const tooltip = FIELD_TOOLTIPS[fieldName];
  
  if (!tooltip) return null;
  
  return (
    <div className="relative inline-block ml-1.5">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        aria-label="More info"
        style={{ color: 'hsl(60 2.5% 23.3% / 30%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', padding: 0, transition: 'color 0.15s ease' }}
        onFocus={e => e.currentTarget.style.color = 'hsl(60 2.5% 23.3% / 55%)'}
        onBlur={e => e.currentTarget.style.color = 'hsl(60 2.5% 23.3% / 30%)'}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>

      {isOpen && (
        <div
          className="absolute z-50 left-0 top-6 w-72"
          style={{
            padding: '0.625rem 0.75rem',
            backgroundColor: 'white',
            borderRadius: '0.75rem',
            border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.10), 0 2px 6px rgba(0,0,0,0.05)',
          }}
        >
          <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 45%)', marginBottom: '0.375rem' }}>{tooltip.title}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            {tooltip.explanation.split('\n\n').map((block, i) => {
              const dashIdx = block.indexOf(' — ');
              return (
                <div key={i} style={{ fontSize: '0.625rem', color: 'hsl(60 2.5% 23.3% / 55%)', lineHeight: 1.5 }}>
                  {dashIdx > -1 ? (
                    <>
                      <span style={{ fontWeight: 600, color: 'hsl(60 2.5% 23.3% / 75%)' }}>{block.slice(0, dashIdx)}</span>
                      <span> — {block.slice(dashIdx + 3)}</span>
                    </>
                  ) : block}
                </div>
              );
            })}
          </div>
          {tooltip.examples && tooltip.examples.length > 0 && (
            <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '0.5px solid hsl(30 3.3% 11.8% / 10%)' }}>
              <div style={{ fontSize: '0.5rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', marginBottom: '0.25rem' }}>Examples</div>
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem' }}>
                {tooltip.examples.map((ex, i) => (
                  <li key={i} style={{ fontSize: '0.625rem', fontFamily: "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace", color: 'hsl(60 2.5% 23.3% / 50%)' }}>• {ex}</li>
                ))}
              </ul>
            </div>
          )}
          <svg width="14" height="7" viewBox="0 0 14 7" style={{ position: 'absolute', top: -7, left: 10 }}>
            <path d="M7 0L14 7H0Z" fill="white" stroke="hsl(30 3.3% 11.8% / 15%)" strokeWidth="0.5" strokeLinejoin="round" />
            <path d="M1 7H13" stroke="white" strokeWidth="1.5" />
          </svg>
        </div>
      )}
    </div>
  );
}

// Helpers
function formatLabel(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}

function getStep(min: number, max: number): number {
  const range = max - min;
  // Handle decimal ranges with fine granularity (0.1% precision for percentages)
  if (range <= 0.1) return 0.001;   // Very small range - 0.1% steps
  if (range <= 0.5) return 0.001;   // Small decimal range - 0.1% steps  
  if (range <= 1) return 0.001;     // Unit range - 0.1% steps
  if (range <= 10) return 0.01;     // Small range - 0.01 steps
  if (range <= 100) return 0.1;
  if (range <= 1000) return 1;
  return 10;
}

function formatNumberValue(val: number, name: string): string {
  // Special formatting based on field name
  const nameLower = name.toLowerCase();
  
  // Percentage fields (weights, rates, confidence, threshold, etc.)
  if (nameLower.includes('weight') || 
      nameLower.includes('confidence') || 
      nameLower.includes('threshold') ||
      nameLower.includes('growth') ||
      nameLower.includes('level') ||
      nameLower.includes('significance') ||
      nameLower.includes('return')) {
    // Show 1 decimal place for 0.1% precision
    return `${(val * 100).toFixed(1)}%`;
  }
  
  // Days/time fields
  if (nameLower.includes('horizon') || nameLower.includes('days') || nameLower.includes('years')) {
    return `${val}${nameLower.includes('years') ? ' yr' : ' days'}`;
  }
  
  // Simulation count
  if (nameLower.includes('simulation')) return val.toLocaleString();
  
  // Dollar values
  if (nameLower.includes('value') && val >= 1000) return `$${val.toLocaleString()}`;
  
  return val.toLocaleString();
}
