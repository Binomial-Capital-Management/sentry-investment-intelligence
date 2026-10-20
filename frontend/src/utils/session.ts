export function getSessionId(): string | null {
  try {
    return localStorage.getItem('session_id');
  } catch {
    return null;
  }
}

export function setSessionId(sessionId: string | null) {
  try {
    if (sessionId) localStorage.setItem('session_id', sessionId);
  } catch {
    // ignore
  }
}
