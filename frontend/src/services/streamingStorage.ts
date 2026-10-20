const isBrowser = typeof window !== 'undefined';

const getStores = (): Storage[] => {
  if (!isBrowser) {
    return [];
  }
  const stores: Storage[] = [];
  try {
    stores.push(window.sessionStorage);
  } catch {
    // Ignore when sessionStorage is unavailable (e.g., SSR or Safari private mode)
  }
  try {
    stores.push(window.localStorage);
  } catch {
    // Ignore when localStorage is unavailable
  }
  return stores;
};

export const STREAM_STORAGE_KEYS = {
  context: 'streaming_context',
  state: 'streaming_state',
  messageId: 'streaming_message_id',
  lastEventId: 'streaming_last_event_id',
  sessionId: 'streaming_session_id',
} as const;

export const streamingStorage = {
  read(key: string): string | null {
    for (const store of getStores()) {
      try {
        const value = store.getItem(key);
        if (value !== null) {
          console.info('[StreamingStorage] read', key, value, store === window.sessionStorage ? 'sessionStorage' : 'localStorage');
          return value;
        }
      } catch {
        // Ignore read failures for this store and continue
      }
    }
    return null;
  },

  write(key: string, value: string): void {
    for (const store of getStores()) {
      try {
        store.setItem(key, value);
        // console.info('[StreamingStorage] write', key, value, store === window.sessionStorage ? 'sessionStorage' : 'localStorage');
        return;
      } catch {
        // Try next fallback store
      }
    }
  },

  remove(key: string): void {
    for (const store of getStores()) {
      try {
        store.removeItem(key);
        console.info('[StreamingStorage] remove', key, store === window.sessionStorage ? 'sessionStorage' : 'localStorage');
      } catch {
        // Ignore removal failure for this store
      }
    }
  },

  clear(keys: string[]): void {
    keys.forEach((key) => this.remove(key));
  },
};
