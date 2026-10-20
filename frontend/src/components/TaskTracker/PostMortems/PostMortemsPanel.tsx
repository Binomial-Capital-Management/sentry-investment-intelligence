import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Plus, Trash2, Pencil, Check, X, Search, Activity, HelpCircle } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { getAuthToken } from '../../../services/authService';
import { API_BASE } from '../../../services/api';
import TransactionSelectionModal from './TransactionSelectionModal';
import PostMortemGuidePanel from './PostMortemGuidePanel';
import WorkspaceIndicator from '@/components/Common/WorkspaceIndicator';
import { ViewSwitcher } from '../ViewSwitcher';
import type { Task, ViewMode } from '@/types/task.types';

interface PostMortemsPanelProps {
  tasks: Task[];
  viewMode: ViewMode;
  onViewChange: (mode: ViewMode) => void;
}

interface PostMortem {
  id: string;
  title: string | null;
  transaction_count: number;
  created_at: string;
  updated_at: string;
}

interface PostMortemsResponse {
  postmortems: PostMortem[];
  total: number;
  total_pages: number;
}

/**
 * Post-mortems view in Task Tracker.
 * Shows saved post-mortem analyses in a table.
 * Users can create new post-mortems by selecting transactions.
 */
export function PostMortemsPanel({ tasks, viewMode, onViewChange }: PostMortemsPanelProps) {
  const navigate = useNavigate();
  const [postmortems, setPostmortems] = useState<PostMortem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedTitle, setEditedTitle] = useState('');
  const [isSavingTitle, setIsSavingTitle] = useState(false);
  const [searchQuery, setSearchTerm] = useState('');
  const [guideOpen, setGuideOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const perPage = 20;

  // Fetch post-mortems
  const fetchPostMortems = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        per_page: perPage.toString(),
      });

      const response = await fetch(`${API_BASE}/api/postmortem/list?${params}`, {
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch post-mortems');

      const data: PostMortemsResponse = await response.json();
      setPostmortems(data.postmortems);
      setTotalPages(data.total_pages);
      setTotal(data.total);
    } catch (error) {
      console.error('Failed to fetch post-mortems:', error);
      toast.error('Failed to load post-mortems');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPostMortems();
  }, [currentPage]);

  // Handle select all
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const newSelected = new Set(selectedIds);
      postmortems.forEach(pm => newSelected.add(pm.id));
      setSelectedIds(newSelected);
    } else {
      setSelectedIds(new Set());
    }
  };

  // Handle individual selection
  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  // Handle delete
  const handleDelete = async () => {
    if (selectedIds.size === 0 || isDeleting) return;

    setIsDeleting(true);
    try {
      const response = await fetch(`${API_BASE}/api/postmortem/delete`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await getAuthToken()}`,
        },
        body: JSON.stringify({
          postmortem_ids: Array.from(selectedIds),
        }),
      });

      if (!response.ok) throw new Error('Failed to delete post-mortems');

      const data = await response.json();
      toast.success(`Deleted ${data.deleted_count} post-mortem(s)`);
      setSelectedIds(new Set());
      setShowDeleteModal(false);

      // If we deleted all items on current page and not on page 1, go to previous page
      if (postmortems.length === selectedIds.size && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else {
        fetchPostMortems();
      }
    } catch (error) {
      console.error('Failed to delete post-mortems:', error);
      toast.error('Failed to delete post-mortems');
    } finally {
      setIsDeleting(false);
    }
  };

  // Handle create success
  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    fetchPostMortems();
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Focus input when entering edit mode
  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  // Handle title edit
  const handleStartEdit = (e: React.MouseEvent, postmortem: PostMortem) => {
    e.stopPropagation();
    setEditingId(postmortem.id);
    setEditedTitle(postmortem.title || '');
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
    setEditedTitle('');
  };

  const handleSaveTitle = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!editedTitle.trim()) {
      toast.error('Title cannot be empty');
      return;
    }

    setIsSavingTitle(true);
    try {
      const response = await fetch(`${API_BASE}/api/postmortem/${id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await getAuthToken()}`,
        },
        body: JSON.stringify({ title: editedTitle.trim() }),
      });

      if (!response.ok) throw new Error('Failed to update title');

      // Update local state
      setPostmortems(postmortems.map(pm =>
        pm.id === id ? { ...pm, title: editedTitle.trim() } : pm,
      ));

      toast.success('Title updated');
      setEditingId(null);
    } catch (error) {
      console.error('Failed to update title:', error);
      toast.error('Failed to update title');
    } finally {
      setIsSavingTitle(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, id: string) => {
    if (e.key === 'Enter') {
      handleSaveTitle(e as any, id);
    } else if (e.key === 'Escape') {
      setEditingId(null);
      setEditedTitle('');
    }
  };

  const filteredPostmortems = postmortems.filter(pm =>
    (pm.title?.toLowerCase() || '').includes(searchQuery.toLowerCase()),
  );

  // Check if all current page items are selected
  const allPageSelected = postmortems.length > 0 && postmortems.every(pm => selectedIds.has(pm.id));

  return (
    <div className="flex flex-col h-full bg-[#fafafa]">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Post Mortems</h1>
            <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
              <span>Review trades and document lessons learned</span>
              <span className="text-gray-300">•</span>
              <WorkspaceIndicator size="sm" />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setGuideOpen(true)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
              title="Open Post Mortem Guide"
            >
              <HelpCircle className="w-5 h-5" />
            </button>
            <ViewSwitcher mode={viewMode} onChange={onViewChange} />
          </div>
        </div>

        <div className="flex items-center justify-between">
          {/* Search */}
          <div className="relative max-w-md w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search post-mortems..."
              value={searchQuery}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border-0 rounded-lg text-sm focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2 animate-fadeIn">
                <span className="text-sm text-gray-600 font-medium mr-2">{selectedIds.size} selected</span>
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="flex items-center gap-1.5 text-xs font-medium text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 px-3 py-2 rounded-md transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            )}

            <button
              onClick={() => setShowCreateModal(true)}
              style={{ backgroundColor: '#0051cc' }}
              className="px-4 py-2 text-white text-sm font-medium rounded-lg shadow-sm hover:shadow-md flex items-center gap-2 transition-all hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              Create Post Mortem
            </button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-8">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredPostmortems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-96 bg-white rounded-2xl border border-gray-100 border-dashed">
            <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mb-4">
              <Activity className="w-5 h-5 text-gray-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">No post-mortems found</h3>
            <p className="text-gray-500 text-sm mt-1">
              {postmortems.length === 0 ? 'Create your first post-mortem to get started.' : 'Try adjusting your search terms.'}
            </p>
            {postmortems.length === 0 && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 text-sm text-[#0051cc] hover:text-[#003d99] font-medium hover:underline"
              >
                Create now
              </button>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left border-collapse">
                <thead className="bg-gray-50/80 text-gray-500 font-medium border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 w-[48px] text-center">
                      <input
                        type="checkbox"
                        checked={allPageSelected}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        className="w-4 h-4 text-[#0051cc] rounded border-gray-300 focus:ring-[#0051cc] focus:ring-offset-0 cursor-pointer"
                      />
                    </th>
                    <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs">Title</th>
                    <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-right">Trades</th>
                    <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs">Created</th>
                    <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredPostmortems.map((postmortem) => (
                    <tr
                      key={postmortem.id}
                      className={`group transition-colors cursor-pointer ${selectedIds.has(postmortem.id) ? 'bg-blue-50/50' : 'hover:bg-gray-50/80'}`}
                      onClick={() => navigate(`/postmortem/${postmortem.id}`)}
                    >
                      <td className="px-6 py-4 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(postmortem.id)}
                          onChange={(e) => handleSelectOne(postmortem.id, e.target.checked)}
                          className="w-4 h-4 text-[#0051cc] rounded border-gray-300 focus:ring-[#0051cc] focus:ring-offset-0 cursor-pointer"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </td>
                      <td className="px-6 py-4 font-medium text-gray-900" onClick={(e) => e.stopPropagation()}>
                        {editingId === postmortem.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              ref={inputRef}
                              type="text"
                              value={editedTitle}
                              onChange={(e) => setEditedTitle(e.target.value)}
                              onKeyDown={(e) => handleKeyDown(e, postmortem.id)}
                              className="text-sm font-medium text-gray-900 border-b border-[#0051cc] bg-transparent focus:outline-none w-full py-1"
                              placeholder="Enter title..."
                              disabled={isSavingTitle}
                            />
                            <button
                              onClick={(e) => handleSaveTitle(e, postmortem.id)}
                              disabled={isSavingTitle}
                              className="p-1 text-green-600 hover:bg-green-50 rounded transition-colors"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              disabled={isSavingTitle}
                              className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 group/title">
                            <span className="truncate max-w-md block group-hover:text-blue-600 transition-colors">
                              {postmortem.title || <span className="text-gray-400 italic">Untitled Post-Mortem</span>}
                            </span>
                            <button
                              onClick={(e) => handleStartEdit(e, postmortem)}
                              className="opacity-0 group-hover/title:opacity-100 p-1 text-gray-400 hover:text-[#0051cc] rounded transition-all"
                            >
                              <Pencil className="h-3 w-3" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right tabular-nums">
                        <span className="px-2 py-1 bg-gray-100 rounded-full text-xs font-medium text-gray-600">
                           {postmortem.transaction_count}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-500 tabular-nums text-sm">
                        {formatDate(postmortem.created_at)}
                      </td>
                      <td className="px-6 py-4 text-gray-500 tabular-nums text-sm">
                        {formatDate(postmortem.updated_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Footer / Pagination */}
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50/50 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Showing {((currentPage - 1) * perPage) + 1} to {Math.min(currentPage * perPage, total)} of {total} results
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className="p-1.5 rounded-md hover:bg-gray-200 disabled:opacity-30 text-gray-600 transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-xs font-medium text-gray-700 px-2">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1.5 rounded-md hover:bg-gray-200 disabled:opacity-30 text-gray-600 transition-colors"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Transaction Selection Modal */}
      {showCreateModal && (
        <TransactionSelectionModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm transition-opacity">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-2xl border border-gray-100 transform transition-all scale-100">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Confirm Deletion</h3>
            <p className="text-sm text-gray-500 mb-6 leading-relaxed">
              Are you sure you want to delete <span className="font-bold text-gray-900">{selectedIds.size}</span> post-mortem(s)? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors focus:ring-2 focus:ring-gray-200 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-lg hover:bg-red-700 transition-colors shadow-sm focus:ring-2 focus:ring-red-500 focus:ring-offset-1 disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete Post-Mortems'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Post Mortem Guide Panel */}
      <PostMortemGuidePanel
        isOpen={guideOpen}
        onClose={() => setGuideOpen(false)}
      />
    </div>
  );
}
