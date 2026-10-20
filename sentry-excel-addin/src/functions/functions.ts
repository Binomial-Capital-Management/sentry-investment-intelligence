/**
 * Custom Excel functions: =SENTRY.PRICE(), =SENTRY.METRIC(), etc.
 *
 * These are streaming custom functions that call the Sentry backend.
 * They persist in saved workbooks and auto-refresh on open.
 */

declare const CustomFunctions: {
  associate(name: string, fn: Function): void;
};

const API_BASE = "/v1/excel";

function getApiKey(): string {
  return localStorage.getItem("sentry_api_key") || "";
}

async function fetchData(path: string): Promise<unknown> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${getApiKey()}`,
      "Content-Type": "application/json",
    },
  });
  if (!resp.ok) return null;
  return resp.json();
}

/**
 * Get current stock price.
 * @customfunction SENTRY.PRICE
 * @param ticker Stock ticker symbol
 * @returns Current price
 */
async function sentryPrice(ticker: string): Promise<number | string> {
  const data = (await fetchData(`/data/price?ticker=${encodeURIComponent(ticker)}`)) as {
    price: number | null;
  } | null;
  if (!data || data.price === null) return "#N/A";
  return data.price;
}

/**
 * Get a financial metric.
 * @customfunction SENTRY.METRIC
 * @param ticker Stock ticker symbol
 * @param metric Metric name (e.g. marketCap, pe, eps)
 * @returns Metric value
 */
async function sentryMetric(ticker: string, metric: string): Promise<number | string> {
  const data = (await fetchData(
    `/data/metric?ticker=${encodeURIComponent(ticker)}&metric=${encodeURIComponent(metric)}`
  )) as { value: number | null } | null;
  if (!data || data.value === null) return "#N/A";
  return data.value;
}

/**
 * Get FRED economic data.
 * @customfunction SENTRY.FRED
 * @param series FRED series ID (e.g. UNRATE, GDP)
 * @returns Latest value
 */
async function sentryFred(series: string): Promise<number | string> {
  const data = (await fetchData(
    `/data/fred?series=${encodeURIComponent(series)}`
  )) as { value: number | null } | null;
  if (!data || data.value === null) return "#N/A";
  return data.value;
}

// Register functions
CustomFunctions.associate("SENTRY.PRICE", sentryPrice);
CustomFunctions.associate("SENTRY.METRIC", sentryMetric);
CustomFunctions.associate("SENTRY.FRED", sentryFred);
