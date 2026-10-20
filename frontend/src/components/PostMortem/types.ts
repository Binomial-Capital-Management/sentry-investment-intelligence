export type ViewMode = 'all' | 'date' | 'portfolio';

export interface ImportFilters {
  portfolioIds: string[];
  dateFrom: string | null;
  dateTo: string | null;
  tickers?: string[];
  source?: 'all' | 'manual' | 'ibkr';
  minValue?: number;
}

export interface TransactionImportPreview {
  count: number;
  metrics: PreviewMetrics;
}

export interface PreviewMetrics {
  totalPnL: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  payoffRatio: number;
  biggestWin: number;
  biggestLoss: number;
}

export interface PortfolioOption {
  id: string;
  name: string;
  value: number;
}

export interface QuickDateOption {
  label: string;
  days: number;
}
