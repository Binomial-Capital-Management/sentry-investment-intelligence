/**
 * Dev mode authentication hook
 * Single responsibility: detect dev mode and provide dev credentials
 */

import { useMemo } from 'react';
import type { DevAuthState } from '../types';

/**
 * Hook to detect dev mode and provide dev auth state
 * Dev mode is enabled when:
 * 1. Running on localhost/127.0.0.1
 * 2. VITE_DEV_SECRET environment variable is set
 */
export function useDevAuth(): DevAuthState {
  return useMemo(() => {
    const isDev = 
      window.location.hostname === 'localhost' || 
      window.location.hostname === '127.0.0.1';
    
    const devSecret = import.meta.env.VITE_DEV_SECRET as string | undefined;
    
    return {
      isDevMode: isDev && !!devSecret,
      devUserId: isDev && devSecret ? 'dev-local-user' : null,
      devSecret: isDev ? devSecret || null : null,
    };
  }, []);
}

/**
 * Check if we're in development environment
 */
export function isDevelopment(): boolean {
  return (
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1'
  );
}

/**
 * Check if Clerk is configured
 */
export function isClerkConfigured(): boolean {
  return !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
}

/**
 * Check if auth is enabled
 */
export function isAuthEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_AUTH === 'true';
}
