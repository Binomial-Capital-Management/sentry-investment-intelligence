/**
 * Auth error handling hook
 * Single responsibility: parse Clerk API errors into user-friendly messages
 */

import { useCallback } from 'react';
import { parseClerkError, DEFAULT_ERROR_MESSAGES } from '../utils/errorMessages';

export interface UseAuthErrorReturn {
  parseError: (err: unknown, defaultMessage?: string) => string;
  parseSignInError: (err: unknown) => string;
  parseSignUpError: (err: unknown) => string;
  parseVerificationError: (err: unknown) => string;
  parseOAuthError: (err: unknown, provider: string) => string;
}

/**
 * Hook for parsing Clerk authentication errors
 */
export function useAuthError(): UseAuthErrorReturn {
  const parseError = useCallback((err: unknown, defaultMessage?: string): string => {
    return parseClerkError(err, defaultMessage);
  }, []);
  
  const parseSignInError = useCallback((err: unknown): string => {
    return parseClerkError(err, DEFAULT_ERROR_MESSAGES.SIGN_IN);
  }, []);
  
  const parseSignUpError = useCallback((err: unknown): string => {
    return parseClerkError(err, DEFAULT_ERROR_MESSAGES.SIGN_UP);
  }, []);
  
  const parseVerificationError = useCallback((err: unknown): string => {
    return parseClerkError(err, DEFAULT_ERROR_MESSAGES.VERIFICATION);
  }, []);
  
  const parseOAuthError = useCallback((err: unknown, provider: string): string => {
    const providerName = provider.replace('oauth_', '').charAt(0).toUpperCase() + 
                         provider.replace('oauth_', '').slice(1);
    return parseClerkError(err, DEFAULT_ERROR_MESSAGES.OAUTH(providerName));
  }, []);
  
  return {
    parseError,
    parseSignInError,
    parseSignUpError,
    parseVerificationError,
    parseOAuthError,
  };
}
