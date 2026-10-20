// Format helpers for tool workflow metrics display
export const fmtCurrency = (v: number | undefined) => {
  if (v == null || isNaN(v)) return '—';
  return `$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

export const fmtPercent = (v: number | undefined) => {
  if (v == null || isNaN(v)) return '—';
  const pct = Math.abs(v) > 1 ? v : v * 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
};
