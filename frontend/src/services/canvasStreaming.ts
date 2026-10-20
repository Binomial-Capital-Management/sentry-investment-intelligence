import { API_BASE } from './api';

// Helper to build the Canvas chat stream URL
export const getCanvasStreamEndpoint = (params: {
  message: string;
  processId?: string;
  threadId?: string;
  model?: string;
}) => {
  const url = new URL(`${API_BASE}/api/canvas/chat/stream`);
  url.searchParams.set('message', params.message);

  if (params.processId) {
    url.searchParams.set('process_id', params.processId);
  }
  if (params.threadId) {
    url.searchParams.set('thread_id', params.threadId);
  }
  if (params.model) {
    url.searchParams.set('model', params.model);
  }

  return url.toString();
};
