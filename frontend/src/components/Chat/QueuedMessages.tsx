import { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, Pencil, Clock, Trash2, Check, X } from 'lucide-react';
import { useMessageQueueStore, QueuedMessage } from '@/stores/messageQueueStore';

interface QueuedMessagesProps {
  threadId: string | null;
  onSendNow: (message: QueuedMessage) => void;
}

const QueuedMessages = ({ threadId, onSendNow }: QueuedMessagesProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const editInputRef = useRef<HTMLInputElement>(null);
  
  const { getQueueForThread, removeFromQueue, updateQueuedMessage } = useMessageQueueStore();
  
  const queue = threadId ? getQueueForThread(threadId) : [];
  
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);
  
  if (queue.length === 0) return null;
  
  const handleEdit = (message: QueuedMessage) => {
    setEditingId(message.id);
    setEditValue(message.content);
  };
  
  const handleSaveEdit = () => {
    if (threadId && editingId && editValue.trim()) {
      updateQueuedMessage(threadId, editingId, editValue.trim());
    }
    setEditingId(null);
    setEditValue('');
  };
  
  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };
  
  const handleRemove = (messageId: string) => {
    if (threadId) {
      removeFromQueue(threadId, messageId);
    }
  };
  
  const handleSendNow = (message: QueuedMessage) => {
    if (threadId) {
      // Remove from queue since we're sending immediately
      removeFromQueue(threadId, message.id);
      onSendNow(message);
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };
  
  return (
    <div style={{
      marginBottom: '12px',
      borderRadius: '8px',
      overflow: 'hidden',
      border: '1px solid #E1DFDD',
      background: '#FAFAFA',
    }}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          background: '#F5F5F5',
          border: 'none',
          cursor: 'pointer',
          fontSize: '13px',
          fontWeight: 500,
          color: '#605E5C',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Clock size={14} style={{ color: '#0051cc' }} />
          {queue.length} Queued
        </span>
        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      
      {/* Queue List */}
      {isExpanded && (
        <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
          {queue.map((message, index) => (
            <div
              key={message.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '10px 14px',
                borderTop: index > 0 ? '1px solid #E1DFDD' : 'none',
                gap: '10px',
              }}
            >
              {/* Queue position indicator */}
              <div style={{
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                background: '#E8E8E8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '11px',
                fontWeight: 500,
                color: '#605E5C',
                flexShrink: 0,
              }}>
                {index + 1}
              </div>
              
              {/* Message content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {editingId === message.id ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                      ref={editInputRef}
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={handleKeyDown}
                      style={{
                        flex: 1,
                        padding: '6px 10px',
                        border: '1px solid #0051cc',
                        borderRadius: '4px',
                        fontSize: '13px',
                        outline: 'none',
                      }}
                    />
                    <button
                      onClick={handleSaveEdit}
                      style={{
                        padding: '4px',
                        background: '#0051cc',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      title="Save"
                    >
                      <Check size={14} style={{ color: '#fff' }} />
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      style={{
                        padding: '4px',
                        background: '#E8E8E8',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      title="Cancel"
                    >
                      <X size={14} style={{ color: '#605E5C' }} />
                    </button>
                  </div>
                ) : (
                  <span style={{
                    fontSize: '13px',
                    color: '#323130',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    display: 'block',
                  }}>
                    {message.content}
                  </span>
                )}
              </div>
              
              {/* Action buttons (hidden during edit) */}
              {editingId !== message.id && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                  {/* Edit button */}
                  <button
                    onClick={() => handleEdit(message)}
                    style={{
                      padding: '6px',
                      background: 'transparent',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#E8E8E8';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                    title="Edit"
                  >
                    <Pencil size={14} style={{ color: '#605E5C' }} />
                  </button>
                  
                  {/* Send Now button */}
                  <button
                    onClick={() => handleSendNow(message)}
                    style={{
                      padding: '6px',
                      background: 'transparent',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#E8F4FF';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                    title="Send now"
                  >
                    <Clock size={14} style={{ color: '#0051cc' }} />
                  </button>
                  
                  {/* Remove button */}
                  <button
                    onClick={() => handleRemove(message.id)}
                    style={{
                      padding: '6px',
                      background: 'transparent',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#FFE8E8';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                    title="Remove from queue"
                  >
                    <Trash2 size={14} style={{ color: '#D13438' }} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default QueuedMessages;
