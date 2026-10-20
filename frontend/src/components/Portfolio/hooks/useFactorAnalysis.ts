import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { portfolioApi } from '@/services/portfolioApi';
import type { AxiosResponse } from 'axios';
import {
  useFactorModelConfig,
  configCacheKey,
  toFactorsParam,
} from './useFactorModelConfig';

export interface VarData {
  historical_95?: { pct: number; dollar: number };
  historical_99?: { pct: number; dollar: number };
  cvar_95?: { pct: number; dollar: number };
  annual_vol?: number;
  daily_vol?: number;
  annual_return_est?: number;
  sharpe_est?: number;
  skewness?: number;
  kurtosis?: number;
}

export interface BarraData {
  ex_ante_beta?: number;
  ex_ante_vol?: number;
  factor_risk?: number;
  specific_risk?: number;
  systematic_pct?: number;
  idiosyncratic_pct?: number;
  mean_r_squared?: number;
  portfolio_exposures?: Record<string, number>;
  factor_contributions?: Record<string, number>;
}

export interface PcaComponent {
  pc: number;
  variance_explained: number;
  cumulative: number;
  portfolio_exposure: number;
  top_loadings: { ticker: string; loading: number }[];
}

export interface PcaData {
  n_components_80pct?: number;
  components?: PcaComponent[];
}

export interface TiltEntry {
  portfolio: number;
  benchmark: number;
  active: number;
}

export interface TiltsData {
  benchmark?: string;
  active_factor_risk?: number;
  tracking_error_est?: number;
  active_tilts?: Record<string, TiltEntry>;
}

export interface FactorAnalysisResult {
  portfolio_id: string;
  as_of: string;
  period: string;
  n_assets: number;
  n_factors: number;
  var: VarData;
  barra: BarraData;
  pca: PcaData;
  tilts: TiltsData;
}

interface UseFactorAnalysisReturn {
  data: FactorAnalysisResult | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  lastUpdated: Date | null;
}

// ─── Module-level shared state ────────────────────────────────────────────────
// All hook instances for the same portfolioId+period share ONE fetch.
// inflight: in-progress promise (deduplicates simultaneous mounts)
// cache: completed results with timestamp

interface CacheEntry { data: FactorAnalysisResult; ts: Date }

const inflight = new Map<string, Promise<FactorAnalysisResult>>();
const cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

// Subscribers: when the shared fetch resolves, notify all hook instances
type Subscriber = (result: FactorAnalysisResult | null, err: string | null) => void;
const subscribers = new Map<string, Set<Subscriber>>();

function subscribe(key: string, cb: Subscriber): () => void {
  if (!subscribers.has(key)) subscribers.set(key, new Set());
  subscribers.get(key)!.add(cb);
  return () => subscribers.get(key)?.delete(cb);
}

function notifyAll(key: string, result: FactorAnalysisResult | null, err: string | null) {
  subscribers.get(key)?.forEach(cb => cb(result, err));
}

async function fetchOnce(
  key: string,
  portfolioId: string,
  queryParams: Record<string, unknown>,
  forceRefresh = false,
): Promise<FactorAnalysisResult> {
  if (inflight.has(key)) return inflight.get(key)!;

  const promise = (async () => {
    try {
      const params = forceRefresh ? { ...queryParams, force: true } : queryParams;
      const res: AxiosResponse<FactorAnalysisResult> = await portfolioApi.get(
        `/${portfolioId}/factor-analysis`,
        { params },
      );
      const data = res.data;
      cache.set(key, { data, ts: new Date() });
      notifyAll(key, data, null);
      return data;
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail ?? err.message)
        : 'Failed to load factor analysis';
      const errStr = typeof msg === 'string' ? msg : JSON.stringify(msg);
      notifyAll(key, null, errStr);
      throw new Error(errStr);
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, promise);
  return promise;
}
// ─────────────────────────────────────────────────────────────────────────────

export function useFactorAnalysis(portfolioId: string | undefined): UseFactorAnalysisReturn {
  const { config } = useFactorModelConfig();

  // Build a stable cache key that includes all config params
  const cacheKey = portfolioId ? `${portfolioId}__${configCacheKey(config)}` : '';

  const [data, setData] = useState<FactorAnalysisResult | null>(() => {
    if (!cacheKey) return null;
    return cache.get(cacheKey)?.data ?? null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(() => {
    if (!cacheKey) return null;
    return cache.get(cacheKey)?.ts ?? null;
  });

  // Reset data when config changes (new cacheKey)
  useEffect(() => {
    const hit = cache.get(cacheKey);
    setData(hit?.data ?? null);
    setLastUpdated(hit?.ts ?? null);
  }, [cacheKey]);

  const queryParams = {
    period: config.period,
    benchmark: config.benchmark,
    ewa_half_life: config.ewaHalfLife,
    nw_lags: config.nwLags,
    vol_window: config.volWindow,
    beta_window: config.betaWindow,
    shrinkage: config.shrinkage,
    factors: toFactorsParam(config),
    pca_n: config.pcaN,
  };

  const doFetch = useCallback(async (force = false) => {
    if (!portfolioId || !cacheKey) return;

    // Return cached if fresh and not forced
    if (!force) {
      const hit = cache.get(cacheKey);
      if (hit && Date.now() - hit.ts.getTime() < CACHE_TTL_MS) {
        setData(hit.data);
        setLastUpdated(hit.ts);
        return;
      }
    } else {
      cache.delete(cacheKey);
    }

    setLoading(true);
    setError(null);

    try {
      const result = await fetchOnce(cacheKey, portfolioId, queryParams, force);
      setData(result);
      setLastUpdated(cache.get(cacheKey)?.ts ?? new Date());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load factor analysis';
      setError(msg);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolioId, cacheKey]);

  // Subscribe to shared fetch notifications
  useEffect(() => {
    if (!portfolioId) return;
    const unsub = subscribe(cacheKey, (result, err) => {
      if (result) {
        setData(result);
        setLastUpdated(cache.get(cacheKey)?.ts ?? new Date());
        setError(null);
      } else if (err) {
        setError(err);
      }
      setLoading(false);
    });
    return unsub;
  }, [cacheKey, portfolioId]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  return {
    data,
    loading,
    error,
    refresh: () => doFetch(true),
    lastUpdated,
  };
}
