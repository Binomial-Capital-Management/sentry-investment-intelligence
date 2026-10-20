import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SessionStore {
  sessionId: string | null;
  lastActivity: Date;
  preferences: {
    theme: 'light' | 'dark';
    focusMode: string;
  };

  setSessionId: (id: string) => void;
  updateActivity: () => void;
  setPreference: <K extends keyof SessionStore['preferences']>(
    key: K,
    value: SessionStore['preferences'][K]
  ) => void;
  clearSession: () => void;
}

export const useSessionStore = create<SessionStore>()(
  persist(
    (set) => ({
      sessionId: null,
      lastActivity: new Date(),
      preferences: {
        theme: 'light',
        focusMode: 'internet',
      },

      setSessionId: (id) =>
        set({ sessionId: id, lastActivity: new Date() }),

      updateActivity: () =>
        set({ lastActivity: new Date() }),

      setPreference: (key, value) =>
        set((state) => ({
          preferences: { ...state.preferences, [key]: value },
        })),

      clearSession: () =>
        set({
          sessionId: null,
          lastActivity: new Date(),
          preferences: {
            theme: 'light',
            focusMode: 'internet',
          },
        }),
    }),
    {
      name: 'binomial-session',
    },
  ),
);
