import { create } from 'zustand';
import type { UploadedFile } from '@services/upload';

export interface QueuedMessage {
  id: string;
  content: string;
  fileIds?: string[];
  portfolioId?: string | null;
  attachments?: UploadedFile[];
  createdAt: Date;
}

interface MessageQueueStore {
  // Map of threadId -> array of queued messages
  queuedMessages: Record<string, QueuedMessage[]>;
  
  // Add a message to the queue for a specific thread
  addToQueue: (
    threadId: string,
    content: string,
    fileIds?: string[],
    portfolioId?: string | null,
    attachments?: UploadedFile[]
  ) => void;
  
  // Remove a message from the queue
  removeFromQueue: (threadId: string, messageId: string) => void;
  
  // Update the content of a queued message
  updateQueuedMessage: (threadId: string, messageId: string, newContent: string) => void;
  
  // Get and remove the next message from the queue (FIFO)
  getNextFromQueue: (threadId: string) => QueuedMessage | null;
  
  // Move a message to the front of the queue (for "Send Now")
  moveToFront: (threadId: string, messageId: string) => void;
  
  // Get queue for a specific thread
  getQueueForThread: (threadId: string) => QueuedMessage[];
  
  // Clear queue for a specific thread
  clearQueue: (threadId: string) => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

export const useMessageQueueStore = create<MessageQueueStore>((set, get) => ({
  queuedMessages: {},
  
  addToQueue: (threadId, content, fileIds, portfolioId, attachments) => {
    const newMessage: QueuedMessage = {
      id: generateId(),
      content,
      fileIds,
      portfolioId,
      attachments,
      createdAt: new Date(),
    };
    
    set((state) => ({
      queuedMessages: {
        ...state.queuedMessages,
        [threadId]: [...(state.queuedMessages[threadId] || []), newMessage],
      },
    }));
  },
  
  removeFromQueue: (threadId, messageId) => {
    set((state) => ({
      queuedMessages: {
        ...state.queuedMessages,
        [threadId]: (state.queuedMessages[threadId] || []).filter(
          (msg) => msg.id !== messageId
        ),
      },
    }));
  },
  
  updateQueuedMessage: (threadId, messageId, newContent) => {
    set((state) => ({
      queuedMessages: {
        ...state.queuedMessages,
        [threadId]: (state.queuedMessages[threadId] || []).map((msg) =>
          msg.id === messageId ? { ...msg, content: newContent } : msg
        ),
      },
    }));
  },
  
  getNextFromQueue: (threadId) => {
    const queue = get().queuedMessages[threadId] || [];
    if (queue.length === 0) return null;
    
    const [next, ...rest] = queue;
    set((state) => ({
      queuedMessages: {
        ...state.queuedMessages,
        [threadId]: rest,
      },
    }));
    
    return next;
  },
  
  moveToFront: (threadId, messageId) => {
    set((state) => {
      const queue = state.queuedMessages[threadId] || [];
      const messageIndex = queue.findIndex((msg) => msg.id === messageId);
      if (messageIndex === -1) return state;
      
      const message = queue[messageIndex];
      const newQueue = [
        message,
        ...queue.slice(0, messageIndex),
        ...queue.slice(messageIndex + 1),
      ];
      
      return {
        queuedMessages: {
          ...state.queuedMessages,
          [threadId]: newQueue,
        },
      };
    });
  },
  
  getQueueForThread: (threadId) => {
    return get().queuedMessages[threadId] || [];
  },
  
  clearQueue: (threadId) => {
    set((state) => ({
      queuedMessages: {
        ...state.queuedMessages,
        [threadId]: [],
      },
    }));
  },
}));
