import { useCallback, useRef } from 'react';
import { useChatStreamStore, DEFAULT_TAB_STATE, DEFAULT_THREAD_STATE } from '../stores/chatStreamStore';
import type { TabChatView, ChatStreamStore } from '../stores/chatStreamStore';

function shallowEqual(a: Record<string, any>, b: Record<string, any>): boolean {
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  for (const key of keysA) {
    if (!Object.is(a[key], b[key])) return false;
  }
  return true;
}

function buildView(s: ChatStreamStore, tabId: string | undefined): TabChatView {
  const tab = tabId ? s.tabStates[tabId] ?? DEFAULT_TAB_STATE : DEFAULT_TAB_STATE;
  const threadId = tab.activeThreadId;
  const thread = threadId ? s.threadStates[threadId] ?? DEFAULT_THREAD_STATE : DEFAULT_THREAD_STATE;
  return {
    ...tab,
    ...thread,
    currentThreadId: tab.activeThreadId,
  };
}

export function useTabChatState(tabId: string | undefined): TabChatView {
  const prevRef = useRef<TabChatView | null>(null);

  const selector = useCallback(
    (s: ChatStreamStore): TabChatView => {
      const next = buildView(s, tabId);
      if (prevRef.current && shallowEqual(prevRef.current, next)) {
        return prevRef.current;
      }
      prevRef.current = next;
      return next;
    },
    [tabId]
  );

  return useChatStreamStore(selector);
}
