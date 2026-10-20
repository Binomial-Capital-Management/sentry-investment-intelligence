/**
 * Shared, localStorage-persisted configuration for the portfolio factor model.
 * All tiles read from the same config; changing it busts the fetch cache and
 * triggers a fresh compute with the new parameters.
 */
import { useState, useCallback, useEffect } from 'react';

export const ALL_STYLE_FACTORS = ['Momentum', 'Size', 'Value', 'Quality', 'Volatility', 'Beta'] as const;
export type StyleFactor = (typeof ALL_STYLE_FACTORS)[number];

export interface FactorModelConfig {
  /** Return history window */
  period: '6mo' | '1y' | '2y';
  /** Benchmark ticker for tilts and beta reference */
  benchmark: string;
  /** EWA covariance half-life in trading days */
  ewaHalfLife: number;
  /** Newey-West autocorrelation lags */
  nwLags: number;
  /** Realized volatility lookback in trading days */
  volWindow: number;
  /** OLS beta estimation window in trading days */
  betaWindow: number;
  /** Bayesian specific-risk shrinkage (0–0.5) */
  shrinkage: number;
  /** Style factors to include */
  styleFactors: StyleFactor[];
  /** Include GICS sector dummies */
  includeSectors: boolean;
  /** Number of PCA components to return */
  pcaN: number;
}

export const DEFAULT_CONFIG: FactorModelConfig = {
  period: '1y',
  benchmark: 'SPY',
  ewaHalfLife: 90,
  nwLags: 5,
  volWindow: 60,
  betaWindow: 252,
  shrinkage: 0.1,
  styleFactors: [...ALL_STYLE_FACTORS],
  includeSectors: true,
  pcaN: 8,
};

const STORAGE_KEY = 'factor-model-config-v1';

function load(): FactorModelConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CONFIG;
    const parsed = JSON.parse(raw) as Partial<FactorModelConfig>;
    return { ...DEFAULT_CONFIG, ...parsed };
  } catch {
    return DEFAULT_CONFIG;
  }
}

function save(cfg: FactorModelConfig) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg)); } catch { /* ignore */ }
}

/** Build the `factors` query-param string the backend expects */
export function toFactorsParam(cfg: FactorModelConfig): string {
  const parts: string[] = [...cfg.styleFactors];
  if (cfg.includeSectors) parts.push('Sectors');
  return parts.join(',');
}

/** Build a stable cache key that changes whenever any setting changes */
export function configCacheKey(cfg: FactorModelConfig): string {
  return `${cfg.period}:${cfg.benchmark}:${cfg.ewaHalfLife}:${cfg.nwLags}:` +
         `${cfg.volWindow}:${cfg.betaWindow}:${cfg.shrinkage}:` +
         `${cfg.styleFactors.join(',')}:${cfg.includeSectors}:${cfg.pcaN}`;
}

// ─── Module-level singleton so all hook instances share the same state ─────
let _config: FactorModelConfig = load();
const _listeners = new Set<() => void>();

function setConfig(next: FactorModelConfig) {
  _config = next;
  save(next);
  _listeners.forEach(fn => fn());
}

export function useFactorModelConfig() {
  const [config, setLocal] = useState<FactorModelConfig>(_config);

  useEffect(() => {
    const refresh = () => setLocal({ ..._config });
    _listeners.add(refresh);
    return () => { _listeners.delete(refresh); };
  }, []);

  const update = useCallback((patch: Partial<FactorModelConfig>) => {
    setConfig({ ..._config, ...patch });
  }, []);

  const reset = useCallback(() => {
    setConfig(DEFAULT_CONFIG);
  }, []);

  return { config, update, reset };
}
