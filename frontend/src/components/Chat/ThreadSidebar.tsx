import { useState } from 'react';
import { useChatStore } from '@stores/chatStore';
import { useUIStore } from '@stores/uiStore';

// Colorful filled icons
const Icons = {
  ChevronLeft: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
    </svg>
  ),
  ChevronRight: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
  ),
  Plus: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" fill="#10b981"/>
      <path d="M12 8v8M8 12h8" stroke="white" strokeWidth={2} strokeLinecap="round"/>
    </svg>
  ),
  Chat: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" fill="#3b82f6"/>
      <circle cx="8" cy="11" r="1.5" fill="#ffffff"/>
      <circle cx="12" cy="11" r="1.5" fill="#ffffff"/>
      <circle cx="16" cy="11" r="1.5" fill="#ffffff"/>
    </svg>
  ),
  Trash: () => (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="#ef4444"/>
    </svg>
  ),
  CheckSquare: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg>
  ),
  X: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
    </svg>
  ),
};

const ThreadSidebar = () => {
  const {
    threads = [],
    currentThreadId,
    createNewThread,
    setCurrentThread,
    deleteThread,
    bulkDeleteThreads,
    isCreatingThread,
  } = useChatStore();

  const { sidebarExpanded, setSidebarExpanded } = useUIStore();
  
  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedThreads, setSelectedThreads] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Delete confirmation modal state
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; threadId: string; threadTitle: string }>({
    isOpen: false,
    threadId: '',
    threadTitle: '',
  });
  
  // Bulk delete confirmation modal state
  const [bulkDeleteModal, setBulkDeleteModal] = useState(false);

  const handleNewThread = async () => {
    await createNewThread('New Chat');
  };

  const handleDeleteThread = (threadId: string, threadTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModal({ isOpen: true, threadId, threadTitle });
  };

  const confirmDelete = async () => {
    if (deleteModal.threadId) {
      await deleteThread(deleteModal.threadId);
    }
    setDeleteModal({ isOpen: false, threadId: '', threadTitle: '' });
  };

  const cancelDelete = () => {
    setDeleteModal({ isOpen: false, threadId: '', threadTitle: '' });
  };

  // Selection mode handlers
  const toggleSelectionMode = () => {
    setSelectionMode(!selectionMode);
    setSelectedThreads(new Set());
  };

  const toggleThreadSelection = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSelected = new Set(selectedThreads);
    if (newSelected.has(threadId)) {
      newSelected.delete(threadId);
    } else {
      newSelected.add(threadId);
    }
    setSelectedThreads(newSelected);
  };

  const selectAll = () => {
    setSelectedThreads(new Set(threads.map(t => t.id)));
  };

  const deselectAll = () => {
    setSelectedThreads(new Set());
  };

  const handleBulkDelete = () => {
    if (selectedThreads.size > 0) {
      setBulkDeleteModal(true);
    }
  };

  const confirmBulkDelete = async () => {
    setIsDeleting(true);
    try {
      await bulkDeleteThreads(Array.from(selectedThreads));
      setSelectedThreads(new Set());
      setSelectionMode(false);
    } finally {
      setIsDeleting(false);
      setBulkDeleteModal(false);
    }
  };

  const cancelBulkDelete = () => {
    setBulkDeleteModal(false);
  };

  return (
    <div className={`
      flex flex-col h-full border-r border-gray-200 bg-white transition-all duration-300
      ${sidebarExpanded ? 'w-56' : 'w-14'}
    `}>
      {/* Header */}
      <div className={`border-b border-gray-200 py-3 ${sidebarExpanded ? 'px-3' : 'px-2'}`}>
        {/* Toggle Button */}
        <button
          onClick={() => setSidebarExpanded(!sidebarExpanded)}
          className={`
            rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors w-full
            ${sidebarExpanded ? 'p-2 flex items-center justify-between' : 'p-2 flex items-center justify-center'}
          `}
          title={sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarExpanded ? (
            <>
              <span className="text-xs font-semibold text-gray-700">Chats</span>
              <Icons.ChevronLeft />
            </>
          ) : (
            <Icons.ChevronRight />
          )}
        </button>

        {/* New Chat Button */}
        {sidebarExpanded && !selectionMode && (
          <button
            onClick={handleNewThread}
            disabled={isCreatingThread}
            className={`
              w-full mt-3 px-3 py-2 rounded-lg font-medium text-xs flex items-center justify-center gap-2 transition-all
              ${isCreatingThread
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'text-white hover:opacity-90 shadow-sm'
              }
            `}
            style={{
              backgroundColor: isCreatingThread ? undefined : '#0051cc',
            }}
          >
            <Icons.Plus />
            New Chat
          </button>
        )}

        {/* Selection Mode Controls */}
        {sidebarExpanded && selectionMode && (
          <div className="mt-3 space-y-2">
            <div className="flex gap-2">
              <button
                onClick={selectAll}
                className="flex-1 px-2 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
              >
                All
              </button>
              <button
                onClick={deselectAll}
                className="flex-1 px-2 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
              >
                None
              </button>
            </div>
            <button
              onClick={handleBulkDelete}
              disabled={selectedThreads.size === 0 || isDeleting}
              className={`
                w-full px-3 py-2 rounded-lg font-medium text-xs flex items-center justify-center gap-2 transition-all
                ${selectedThreads.size === 0 || isDeleting
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-red-600 text-white hover:bg-red-700'
                }
              `}
            >
              <Icons.Trash />
              Delete {selectedThreads.size > 0 ? `(${selectedThreads.size})` : ''}
            </button>
          </div>
        )}
      </div>

      {/* Thread List */}
      <div className={`flex-1 overflow-y-auto py-2 ${sidebarExpanded ? 'px-2' : 'px-1'}`}>
        {threads.length === 0 ? (
          sidebarExpanded ? (
            <div className="text-center text-xs text-gray-400 mt-8 font-medium">
              No conversations yet
            </div>
          ) : null
        ) : (
          <div className="flex flex-col gap-1">
            {threads.map((thread) => {
              const isActive = currentThreadId === thread.id;
              const isSelected = selectedThreads.has(thread.id);
              return (
                <div
                  key={thread.id}
                  onClick={() => selectionMode ? toggleThreadSelection(thread.id, { stopPropagation: () => {} } as React.MouseEvent) : setCurrentThread(thread.id)}
                  className={`
                    group rounded-lg transition-all duration-200 relative cursor-pointer
                    ${sidebarExpanded ? 'flex items-center gap-2 p-2' : 'flex items-center justify-center p-2'}
                    ${selectionMode && isSelected ? 'bg-red-50 ring-1 ring-red-200' : isActive ? 'bg-gray-100 shadow-sm' : 'hover:bg-gray-50'}
                  `}
                  title={!sidebarExpanded ? thread.title : undefined}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (selectionMode) {
                        toggleThreadSelection(thread.id, { stopPropagation: () => {} } as React.MouseEvent);
                      } else {
                        setCurrentThread(thread.id);
                      }
                    }
                  }}
                >
                  {/* Checkbox in selection mode */}
                  {sidebarExpanded && selectionMode && (
                    <div 
                      className="flex-shrink-0"
                      onClick={(e) => toggleThreadSelection(thread.id, e)}
                    >
                      <div className={`
                        w-4 h-4 rounded border-2 flex items-center justify-center transition-all
                        ${isSelected ? 'bg-red-600 border-red-600' : 'border-gray-300 hover:border-gray-400'}
                      `}>
                        {isSelected && (
                          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                          </svg>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Chat icon (hidden in selection mode when expanded) */}
                  {(!selectionMode || !sidebarExpanded) && (
                    <div className="flex-shrink-0">
                      <Icons.Chat />
                    </div>
                  )}

                  {sidebarExpanded && (
                    <>
                      <span className={`
                        flex-1 text-left text-xs font-medium truncate
                        ${isSelected ? 'text-red-700' : isActive ? 'text-gray-900' : 'text-gray-600'}
                      `}>
                        {thread.title}
                      </span>
                      {!selectionMode && (
                        <button
                          onClick={(e) => handleDeleteThread(thread.id, thread.title, e)}
                          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded transition-all flex-shrink-0"
                        >
                          <Icons.Trash />
                        </button>
                      )}
                    </>
                  )}

                  {/* Tooltip for collapsed state */}
                  {!sidebarExpanded && (
                    <div className="absolute left-full ml-3 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap transition-opacity z-50">
                      {thread.title}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      {sidebarExpanded && threads.length > 0 && (
        <div className="px-3 py-2 border-t border-gray-200 flex items-center justify-between">
          <span className="text-xs text-gray-400 font-medium">
            {threads.length} {threads.length === 1 ? 'chat' : 'chats'}
          </span>
          <button
            onClick={toggleSelectionMode}
            className={`
              p-1.5 rounded transition-colors
              ${selectionMode 
                ? 'bg-gray-200 text-gray-700 hover:bg-gray-300' 
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              }
            `}
            title={selectionMode ? 'Exit selection mode' : 'Select multiple chats'}
          >
            {selectionMode ? <Icons.X /> : <Icons.CheckSquare />}
          </button>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteModal.isOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center"
          onClick={cancelDelete}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/40" />
          
          {/* Modal */}
          <div 
            className="relative bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 transform transition-all"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Icon */}
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
            </div>
            
            {/* Title */}
            <h3 className="text-lg font-semibold text-gray-900 text-center mb-2">
              Delete Chat
            </h3>
            
            {/* Message */}
            <p className="text-sm text-gray-500 text-center mb-6">
              Are you sure you want to delete "<span className="font-medium text-gray-700">{deleteModal.threadTitle}</span>"? This action cannot be undone.
            </p>
            
            {/* Buttons */}
            <div className="flex gap-3">
              <button
                onClick={cancelDelete}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Delete Confirmation Modal */}
      {bulkDeleteModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center"
          onClick={cancelBulkDelete}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/40" />
          
          {/* Modal */}
          <div 
            className="relative bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 transform transition-all"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Icon */}
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
            </div>
            
            {/* Title */}
            <h3 className="text-lg font-semibold text-gray-900 text-center mb-2">
              Delete {selectedThreads.size} Chats
            </h3>
            
            {/* Message */}
            <p className="text-sm text-gray-500 text-center mb-6">
              Are you sure you want to delete <span className="font-medium text-gray-700">{selectedThreads.size}</span> {selectedThreads.size === 1 ? 'chat' : 'chats'}? This action cannot be undone.
            </p>
            
            {/* Buttons */}
            <div className="flex gap-3">
              <button
                onClick={cancelBulkDelete}
                disabled={isDeleting}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmBulkDelete}
                disabled={isDeleting}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isDeleting ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                    </svg>
                    Deleting...
                  </>
                ) : (
                  'Delete All'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ThreadSidebar;
