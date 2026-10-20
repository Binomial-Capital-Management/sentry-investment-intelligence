import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Pencil, Check, X, Settings, Trash2, HelpCircle, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { toast } from 'react-hot-toast';

import { getAuthToken } from '../../../services/authService';
import { API_BASE } from '../../../services/api';
import PostMortemChatPanel from './PostMortemChatPanel';
import PostMortemGuidePanel from './PostMortemGuidePanel';
import TransactionSelectionModal from './TransactionSelectionModal';

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

interface PostMortemDetails {
  id: string;
  title: string | null;
  notes: string | null;
  transaction_count: number;
  created_at: string;
  updated_at: string;
  transactions: Transaction[];
}

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const formatCurrency = (n: number) => fmt.format(n);
const formatDate = (s: string) =>
  new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

function calcMetrics(pm: PostMortemDetails) {
  const sells = pm.transactions.filter(t => t.transaction_type === 'SELL' && t.realized_gain_loss !== null);
  const totalPnL = sells.reduce((s, t) => s + (t.realized_gain_loss || 0), 0);
  const wins   = sells.filter(t => (t.realized_gain_loss || 0) > 0).length;
  const losses = sells.filter(t => (t.realized_gain_loss || 0) < 0).length;
  return { totalPnL, wins, losses, winRate: wins + losses > 0 ? (wins / (wins + losses)) * 100 : 0, totalTrades: pm.transactions.length };
}

export default function PostMortemDetailPage() {
  const { id }   = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [postmortem, setPostmortem]     = useState<PostMortemDetails | null>(null);
  const [loading, setLoading]           = useState(true);
  const [isEditingTitle, setEditing]    = useState(false);
  const [editedTitle, setEditedTitle]   = useState('');
  const [isSavingTitle, setSaving]      = useState(false);
  const [showTxModal, setShowTxModal]   = useState(false);
  const [selectedTxIds, setSelectedTxIds] = useState<Set<string>>(new Set());
  const [showDelConfirm, setDelConfirm] = useState(false);
  const [isDeleting, setDeleting]       = useState(false);
  const [isUpdatingTx, setUpdatingTx]   = useState(false);
  const [guideOpen, setGuideOpen]       = useState(false);
  const [chatOpen, setChatOpen]         = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { fetchDetails(); }, [id]);
  useEffect(() => {
    if (postmortem?.transactions) setSelectedTxIds(new Set(postmortem.transactions.map(t => t.id)));
  }, [postmortem?.transactions]);
  useEffect(() => {
    if (isEditingTitle && inputRef.current) { inputRef.current.focus(); inputRef.current.select(); }
  }, [isEditingTitle]);

  const fetchDetails = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/postmortem/${id}`, {
        headers: { Authorization: `Bearer ${await getAuthToken()}` },
      });
      if (!res.ok) throw new Error();
      setPostmortem(await res.json());
    } catch { toast.error('Failed to load post-mortem'); }
    finally { setLoading(false); }
  };

  const handleSaveTitle = async () => {
    if (!id || !editedTitle.trim()) { toast.error('Title cannot be empty'); return; }
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/postmortem/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await getAuthToken()}` },
        body: JSON.stringify({ title: editedTitle.trim() }),
      });
      if (!res.ok) throw new Error();
      if (postmortem) setPostmortem({ ...postmortem, title: editedTitle.trim() });
      toast.success('Title updated'); setEditing(false);
    } catch { toast.error('Failed to update title'); }
    finally { setSaving(false); }
  };

  const handleUpdateTx = async () => {
    if (!id || isUpdatingTx) return;
    setUpdatingTx(true);
    try {
      const res = await fetch(`${API_BASE}/api/postmortem/${id}/transactions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await getAuthToken()}` },
        body: JSON.stringify({ transaction_ids: Array.from(selectedTxIds) }),
      });
      if (!res.ok) throw new Error();
      toast.success('Transactions updated'); setShowTxModal(false); fetchDetails();
    } catch { toast.error('Failed to update transactions'); }
    finally { setUpdatingTx(false); }
  };

  const handleDelete = async () => {
    if (!id) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/api/postmortem/${id}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${await getAuthToken()}` },
      });
      if (!res.ok) throw new Error();
      toast.success('Deleted'); navigate('/review');
    } catch { toast.error('Failed to delete'); setDeleting(false); setDelConfirm(false); }
  };

  if (loading) return (
    <div className="h-full w-full flex items-center justify-center">
      <div className="w-7 h-7 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
    </div>
  );
  if (!postmortem) return (
    <div className="h-full w-full flex items-center justify-center">
      <div className="text-center">
        <p className="text-gray-500 mb-3">Post-mortem not found</p>
        <button onClick={() => navigate('/review')} className="text-sm font-medium text-blue-600 hover:underline">Back to Reviews</button>
      </div>
    </div>
  );

  const metrics = calcMetrics(postmortem);

  return (
    <div className="h-full flex flex-col bg-[#fafafa] overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 py-3 bg-white border-b border-gray-200 shrink-0">
        <button onClick={() => navigate('/review')}
          className="flex items-center gap-1.5 text-gray-500 hover:text-gray-800 text-sm font-medium hover:bg-gray-100 px-2 py-1 rounded-md transition-colors">
          <ArrowLeft size={15} /> Back
        </button>
        <div className="w-px h-5 bg-gray-200" />

        {/* Editable title */}
        {isEditingTitle ? (
          <div className="flex items-center gap-2">
            <input ref={inputRef} value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveTitle(); if (e.key === 'Escape') { setEditing(false); } }}
              disabled={isSavingTitle}
              className="text-base font-semibold text-gray-900 border-b-2 border-blue-500 bg-transparent focus:outline-none py-0.5"
            />
            <button onClick={handleSaveTitle} disabled={isSavingTitle} className="p-1 text-gray-700 hover:bg-gray-100 rounded disabled:opacity-40"><Check size={14} /></button>
            <button onClick={() => setEditing(false)} disabled={isSavingTitle} className="p-1 text-gray-500 hover:bg-gray-100 rounded disabled:opacity-40"><X size={14} /></button>
          </div>
        ) : (
          <div className="flex items-center gap-2 group">
            <h1 className="text-base font-semibold text-gray-900">{postmortem.title || 'Untitled Post-Mortem'}</h1>
            <button onClick={() => { setEditedTitle(postmortem.title || ''); setEditing(true); }}
              className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded transition-all">
              <Pencil size={12} />
            </button>
          </div>
        )}

        <span className="text-xs text-gray-400 font-medium">
          {postmortem.transaction_count} trade{postmortem.transaction_count !== 1 ? 's' : ''}
        </span>

        <div className="flex items-center gap-2 ml-auto">
          <button onClick={() => setGuideOpen(true)} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors" title="Guide">
            <HelpCircle size={16} />
          </button>
          <button
            onClick={() => setChatOpen(o => !o)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
            title={chatOpen ? 'Collapse AI panel' : 'Open AI panel'}
          >
            {chatOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
          </button>
          <button onClick={() => setShowTxModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
            <Settings size={12} /> Manage Trades
          </button>
          <button onClick={() => setDelConfirm(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-md hover:bg-red-50 transition-colors">
            <Trash2 size={12} /> Delete
          </button>
        </div>
      </div>

      {/* ── Body: left content + right chat ─────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden min-h-0">

        {/* Left column */}
        <div className="flex flex-col flex-1 overflow-hidden border-r border-gray-200 min-w-0">

          {/* Metrics row */}
          <div className="grid shrink-0 border-b border-gray-200" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
            {[
              { label: 'Total P&L',    value: `${metrics.totalPnL >= 0 ? '+' : ''}${formatCurrency(metrics.totalPnL)}`, color: metrics.totalPnL >= 0 ? '#059669' : '#dc2626' },
              { label: 'Trades',       value: String(metrics.totalTrades), color: '#111827' },
              { label: 'Wins',         value: String(metrics.wins),        color: '#059669' },
              { label: 'Losses',       value: String(metrics.losses),      color: '#dc2626' },
              { label: 'Win Rate',     value: `${metrics.winRate.toFixed(1)}%`, color: '#111827', bar: metrics.winRate },
            ].map((c, i) => (
              <div key={c.label}
                className="flex flex-col justify-center px-4 py-4 bg-white min-w-0"
                style={{ borderRight: i < 4 ? '1px solid #e5e7eb' : 'none' }}>
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">{c.label}</p>
                <p className="text-xl font-bold tracking-tight leading-none" style={{ color: c.color }}>{c.value}</p>
                {c.bar !== undefined && (
                  <div className="mt-2 h-0.5 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${c.bar}%` }} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Transactions table */}
          <div className="flex-1 overflow-y-auto overflow-x-auto">
            {postmortem.transactions.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">No transactions attached</div>
            ) : (
              <table className="min-w-full text-sm border-collapse">
                <thead className="sticky top-0 bg-gray-50 z-10">
                  <tr>
                    {['Portfolio', 'Date', 'Ticker', 'Type', 'Qty', 'Price', 'Value', 'Realized'].map((h, i) => (
                      <th key={h} className="px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-200"
                        style={{ textAlign: i > 3 ? 'right' : 'left', whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {postmortem.transactions.map((tx) => {
                    const isBuy = tx.transaction_type === 'BUY';
                    return (
                      <tr key={tx.id} className="hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-0">
                        <td className="px-4 py-3 text-gray-700 text-xs max-w-[160px]">
                          <span className="block truncate" title={tx.portfolio_name}>{tx.portfolio_name}</span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 font-mono text-xs whitespace-nowrap">{formatDate(tx.transaction_date)}</td>
                        <td className="px-4 py-3 font-bold text-gray-900 whitespace-nowrap">{tx.ticker}</td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${isBuy ? 'bg-gray-50 text-gray-500 border-gray-200' : 'bg-emerald-50 text-emerald-600 border-emerald-100'}`}>
                            {isBuy ? 'BUY' : 'SELL'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-gray-700 whitespace-nowrap">{tx.quantity.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-gray-700 whitespace-nowrap">{formatCurrency(tx.price)}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-gray-700 whitespace-nowrap">{isBuy ? '-' : '+'}{formatCurrency(Math.abs(tx.total_amount))}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap">
                          {tx.realized_gain_loss != null ? (
                            <span className={`font-semibold ${tx.realized_gain_loss >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                              {tx.realized_gain_loss >= 0 ? '+' : ''}{formatCurrency(tx.realized_gain_loss)}
                            </span>
                          ) : <span className="text-gray-300">—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right column — AI chat, collapsible */}
        <div
          className="shrink-0 flex flex-col overflow-hidden bg-white transition-all duration-200"
          style={{ width: chatOpen ? 420 : 0, minWidth: chatOpen ? 420 : 0 }}
        >
          {chatOpen && (
            <PostMortemChatPanel
              isOpen={true}
              onClose={() => setChatOpen(false)}
              postMortemTitle={postmortem.title || 'Untitled Post-Mortem'}
              transactionCount={postmortem.transaction_count || 0}
              postMortemId={id || ''}
              transactions={postmortem.transactions || []}
            />
          )}
        </div>
      </div>

      {/* ── Modals ──────────────────────────────────────────────────────────── */}
      {showTxModal && (
        <TransactionSelectionModal isOpen={showTxModal} onClose={() => setShowTxModal(false)}
          selectedIds={selectedTxIds} onSelectionChange={setSelectedTxIds}
          onSuccess={handleUpdateTx} isSaving={isUpdatingTx} />
      )}

      {showDelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => !isDeleting && setDelConfirm(false)}>
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-gray-900 mb-2">Delete this post-mortem?</h3>
            <p className="text-sm text-gray-500 mb-5">This is permanent and cannot be undone.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDelConfirm(false)} disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Cancel</button>
              <button onClick={handleDelete} disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50">
                {isDeleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <PostMortemGuidePanel isOpen={guideOpen} onClose={() => setGuideOpen(false)} />
    </div>
  );
}
