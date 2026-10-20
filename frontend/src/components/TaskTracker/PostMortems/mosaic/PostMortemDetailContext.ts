import { createContext, useContext } from 'react';

interface Transaction {
  id: string;
  portfolio_id: string;
  portfolio_name: string;
  ticker: string;
  transaction_type: string;
  quantity: number;
  price: number;
  transaction_date: string;
  realized_gain_loss: number | null;
  total_amount: number;
}

export interface PostMortemDetails {
  id: string;
  title: string | null;
  notes: string | null;
  transaction_count: number;
  created_at: string;
  updated_at: string;
  transactions: Transaction[];
}

export interface PostMortemMetrics {
  totalPnL: number;
  wins: number;
  losses: number;
  winRate: number;
  totalTrades: number;
  sellTradesCount: number;
}

export interface PostMortemDetailContextValue {
  postmortem: PostMortemDetails | null;
  metrics: PostMortemMetrics | null;
  isEditingTitle: boolean;
  editedTitle: string;
  isSavingTitle: boolean;
  setEditedTitle: (v: string) => void;
  handleStartEdit: () => void;
  handleCancelEdit: () => void;
  handleSaveTitle: () => void;
  formatCurrency: (n: number) => string;
  formatDate: (s: string) => string;
}

export const PostMortemDetailContext = createContext<PostMortemDetailContextValue>({
  postmortem: null,
  metrics: null,
  isEditingTitle: false,
  editedTitle: '',
  isSavingTitle: false,
  setEditedTitle: () => {},
  handleStartEdit: () => {},
  handleCancelEdit: () => {},
  handleSaveTitle: () => {},
  formatCurrency: (n) => `$${n.toFixed(2)}`,
  formatDate: (s) => s,
});

export function usePostMortemDetail() {
  return useContext(PostMortemDetailContext);
}
