import { API_BASE } from '@/services/api';

const buffer: string[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

export function debugLog(tag: string, data: Record<string, any>) {
  buffer.push(`[${tag}] ${JSON.stringify(data)}`);
  if (!flushTimer) {
    flushTimer = setTimeout(flush, 500);
  }
}

function flush() {
  flushTimer = null;
  if (buffer.length === 0) return;
  const lines = buffer.splice(0);
  fetch(`${API_BASE}/api/canvas/chat/debug-log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lines }),
  }).catch(() => {});
}
