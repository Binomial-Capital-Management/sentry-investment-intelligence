/**
 * Auth Service - Provides authentication tokens for API requests
 *
 * This service delegates to Clerk's built-in token management which handles:
 * - Token caching (tokens cached for ~60s)
 * - Automatic refresh before expiry
 * - Race condition handling
 *
 * No need for module-level state or manual sync with React context.
 */

/**
 * Check if we're in development mode
 */
const isDevelopment = (): boolean => {
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
};

/**
 * Wait for Clerk to be ready (up to maxWaitMs)
 * This handles the race condition where API calls happen before Clerk initializes
 */
const waitForClerk = async (maxWaitMs: number = 3000): Promise<any> => {
  const startTime = Date.now();
  const pollInterval = 50; // Check every 50ms
  
  while (Date.now() - startTime < maxWaitMs) {
    const clerk = (window as any).Clerk;
    // Clerk is ready when it exists and has loaded (session may still be null if not signed in)
    if (clerk?.loaded || clerk?.session) {
      return clerk;
    }
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  // Return whatever Clerk state we have after timeout
  return (window as any).Clerk;
};

/**
 * Get the current auth token - used by axios interceptors and streaming
 * Delegates directly to Clerk's session.getToken() which handles caching internally
 *
 * @returns Promise that resolves with the JWT token or null if not authenticated
 */
export const getAuthToken = async (): Promise<string | null> => {
  // In development with DEV_SECRET, bypass Clerk entirely
  if (isDevelopment()) {
    const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
    if (devSecret) {
      // Dev auth will be handled by X-Dev-Secret headers in interceptor
      return null;
    }
  }

  // Wait for Clerk to be ready (handles race condition on page load)
  const clerk = await waitForClerk();

  // If Clerk isn't loaded yet or user isn't signed in, return null
  if (!clerk?.session) {
    return null;
  }

  try {
    // Clerk's getToken handles caching, refresh, and race conditions internally
    // The 'binomialsentry-api' template must be configured in Clerk Dashboard
    const token = await clerk.session.getToken({ template: 'binomialsentry-api' });
    return token;
  } catch (error) {
    console.error('[Auth Service] Failed to get token from Clerk:', error);
    return null;
  }
};

/**
 * Check if user is currently authenticated
 * Uses Clerk's session state directly
 */
export const hasAuthToken = (): boolean => {
  const clerk = (window as any).Clerk;
  return !!clerk?.session;
};

/**
 * @deprecated No longer needed - Clerk manages token state internally
 * Kept for backwards compatibility with AuthProvider
 */
export const setAuthToken = (token: string | null) => {
  // No-op: Clerk manages token state internally
  // This function is kept to avoid breaking AuthProvider imports
  if (token) {
    console.debug('[Auth Service] setAuthToken called (no-op, Clerk manages state)');
  }
};

/**
 * @deprecated No longer needed - Clerk manages token state internally
 * Kept for backwards compatibility with AuthProvider
 */
export const clearAuthToken = () => {
  // No-op: Clerk manages token state internally
  // This function is kept to avoid breaking AuthProvider imports
  console.debug('[Auth Service] clearAuthToken called (no-op, Clerk manages state)');
};
