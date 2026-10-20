/**
 * Auth feature constants
 */

// Route paths
export const AUTH_ROUTES = {
  LOGIN: '/login',
  REGISTER: '/register',
  SSO_CALLBACK: '/sso-callback',
  CHAT: '/chat',
  LANDING: '/',
} as const;

// Clerk error codes
export const CLERK_ERROR_CODES = {
  // Sign-in errors
  PASSWORD_INCORRECT: 'form_password_incorrect',
  IDENTIFIER_NOT_FOUND: 'form_identifier_not_found',
  TOO_MANY_ATTEMPTS: 'too_many_attempts',
  SESSION_EXISTS: 'session_exists',
  
  // Sign-up errors
  IDENTIFIER_EXISTS: 'form_identifier_exists',
  PASSWORD_PWNED: 'form_password_pwned',
  PASSWORD_TOO_SHORT: 'form_password_length_too_short',
  PASSWORD_VALIDATION_FAILED: 'form_password_validation_failed',
  PARAM_FORMAT_INVALID: 'form_param_format_invalid',
  
  // Verification errors
  CODE_INCORRECT: 'form_code_incorrect',
  VERIFICATION_EXPIRED: 'verification_expired',
} as const;

// Sign-in status types from Clerk
export const SIGN_IN_STATUS = {
  COMPLETE: 'complete',
  NEEDS_FIRST_FACTOR: 'needs_first_factor',
  NEEDS_SECOND_FACTOR: 'needs_second_factor',
  NEEDS_NEW_PASSWORD: 'needs_new_password',
  NEEDS_IDENTIFIER: 'needs_identifier',
} as const;

// Sign-up status types from Clerk
export const SIGN_UP_STATUS = {
  COMPLETE: 'complete',
  MISSING_REQUIREMENTS: 'missing_requirements',
  ABANDONED: 'abandoned',
} as const;

// Second factor strategies
export const SECOND_FACTOR_STRATEGY = {
  EMAIL_CODE: 'email_code',
  PHONE_CODE: 'phone_code',
  TOTP: 'totp',
  BACKUP_CODE: 'backup_code',
} as const;

// Validation patterns
export const VALIDATION_PATTERNS = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  USERNAME: /^[a-zA-Z0-9_]{3,64}$/,
} as const;

// Validation constraints
export const VALIDATION_CONSTRAINTS = {
  PASSWORD_MIN_LENGTH: 8,
  USERNAME_MIN_LENGTH: 3,
  USERNAME_MAX_LENGTH: 64,
  NAME_MIN_LENGTH: 2,
  VERIFICATION_CODE_LENGTH: 6,
} as const;

// Timing constants
export const TIMING = {
  LOADING_THRESHOLD_MS: 200,
  RESEND_COOLDOWN_MS: 60000,
  SSO_REDIRECT_TIMEOUT_MS: 2000,
} as const;

// Local storage keys
export const STORAGE_KEYS = {
  ACTIVE_ORGANIZATION: 'activeOrganization',
  CLERK_TOKEN: 'clerk-token',
  AUTH_TOKEN: 'auth-token',
} as const;
