/**
 * Clerk error code to user-friendly message mapping
 */

import { CLERK_ERROR_CODES } from '../constants';

// Error messages map
export const ERROR_MESSAGES: Record<string, string> = {
  // Sign-in errors
  [CLERK_ERROR_CODES.PASSWORD_INCORRECT]: 'Invalid email or password',
  [CLERK_ERROR_CODES.IDENTIFIER_NOT_FOUND]: 'Invalid email or password',
  [CLERK_ERROR_CODES.TOO_MANY_ATTEMPTS]: 'Too many attempts. Please try again later.',
  [CLERK_ERROR_CODES.SESSION_EXISTS]: 'You are already signed in',
  
  // Sign-up errors
  [CLERK_ERROR_CODES.IDENTIFIER_EXISTS]: 'Email already registered. Try logging in instead.',
  [CLERK_ERROR_CODES.PASSWORD_PWNED]: 'This password has been found in a data breach. Please choose a different password.',
  [CLERK_ERROR_CODES.PASSWORD_TOO_SHORT]: 'Password is too short. Please use at least 8 characters.',
  [CLERK_ERROR_CODES.PASSWORD_VALIDATION_FAILED]: 'Password does not meet requirements. Please use a stronger password.',
  [CLERK_ERROR_CODES.PARAM_FORMAT_INVALID]: 'Invalid email format. Please check and try again.',
  
  // Verification errors
  [CLERK_ERROR_CODES.CODE_INCORRECT]: 'Incorrect code. Please check and try again.',
  [CLERK_ERROR_CODES.VERIFICATION_EXPIRED]: 'Code expired. Please request a new one.',
};

// Default error messages by category
export const DEFAULT_ERROR_MESSAGES = {
  SIGN_IN: 'Unable to sign in. Please try again.',
  SIGN_UP: 'Unable to create account. Please try again.',
  VERIFICATION: 'Invalid or expired code. Please try again.',
  OAUTH: (provider: string) => `Unable to sign in with ${provider}. Please try again.`,
  UNEXPECTED: 'An unexpected error occurred. Please try again.',
  AUTH_NOT_READY: 'Authentication service not ready. Please refresh.',
} as const;

/**
 * Parse a Clerk API error into a user-friendly message
 */
export function parseClerkError(err: unknown, defaultMessage: string = DEFAULT_ERROR_MESSAGES.UNEXPECTED): string {
  if (!err || typeof err !== 'object') {
    return defaultMessage;
  }
  
  const error = err as { errors?: Array<{ code?: string; message?: string }> };
  
  if (error.errors && Array.isArray(error.errors) && error.errors.length > 0) {
    const clerkError = error.errors[0];
    
    if (clerkError.code && ERROR_MESSAGES[clerkError.code]) {
      return ERROR_MESSAGES[clerkError.code];
    }
    
    if (clerkError.message) {
      return clerkError.message;
    }
  }
  
  return defaultMessage;
}
