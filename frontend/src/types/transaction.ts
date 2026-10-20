export interface Transaction {
  id: string;
  portfolio_id: string;
  transaction_type: 'BUY' | 'SELL';
  ticker: string;
  quantity: number;
  price: number;
  total_amount: number;
  transaction_date: string;
  cost_basis?: number;
  realized_gain_loss?: number;
  lots_affected?: Array<{
    lotId: string;
    quantity: number;
    purchasePrice: number;
    purchaseDate: string;
  }>;
  notes?: string;
  created_at: string;
}

export interface TransactionHistoryResponse {
  portfolio_id: string;
  transactions: Transaction[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface TransactionFilters {
  ticker: string | null;
  type: 'BUY' | 'SELL' | null;
  dateFrom: string | null;
  dateTo: string | null;
}
