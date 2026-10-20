/**
 * Auth feature types
 */

// Form error types
export interface LoginFormErrors {
  identifier: string;
  password: string;
  secondFactor: string;
  general: string;
}

export interface RegisterFormErrors {
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  verificationCode: string;
  general: string;
}

// Field touched state
export interface LoginFieldTouched {
  identifier: boolean;
  password: boolean;
}

export interface RegisterFieldTouched {
  firstName: boolean;
  lastName: boolean;
  username: boolean;
  email: boolean;
  password: boolean;
  confirmPassword: boolean;
}

// Registration steps
export type RegistrationStep = 'registration' | 'verification' | 'complete';

// Sign-in steps (for second factor)
export type SignInStep = 'credentials' | 'second_factor';

// OAuth provider types
export type OAuthProvider = 'oauth_google' | 'oauth_microsoft' | 'oauth_github';

// Organization data for signup flow
export interface PendingOrgData {
  organizationName: string;
  slug: string;
  industry?: string;
  companySize?: string;
  region?: string;
  website?: string;
  description?: string;
  billingContactName?: string;
  billingContactEmail?: string;
  phone?: string;
  taxId?: string;
  address?: string;
  timezone?: string;
  logo?: string;
}

// Team invite for organization signup
export interface TeamInvite {
  email: string;
  role: 'org:admin' | 'org:member';
}

// Auth layout props
export interface AuthLayoutProps {
  children: React.ReactNode;
  rightContent?: React.ReactNode;
}

// Auth gate props
export interface AuthGateProps {
  children: React.ReactNode;
  fallback?: string;
}

// Dev auth state
export interface DevAuthState {
  isDevMode: boolean;
  devUserId: string | null;
  devSecret: string | null;
}

// Clerk error structure
export interface ClerkError {
  code: string;
  message: string;
  longMessage?: string;
  meta?: Record<string, unknown>;
}

export interface ClerkAPIError {
  errors: ClerkError[];
  status: number;
}
