/**
 * Auth feature module - public exports
 * 
 * Usage:
 * import { LoginPage, RegisterPage, AuthGate, useDevAuth } from '@/features/auth';
 */

// Pages
export { LoginPage, RegisterPage, SSOCallbackPage } from './pages';
export { FallbackLoginForm, FallbackRegisterForm } from './pages';

// Components
export { LoginForm, SecondFactorForm } from './components/LoginForm';
export { RegisterForm, VerificationForm } from './components/RegisterForm';
export { OAuthButtons } from './components/OAuthButtons';
export { AuthLayout, LoginRightContent } from './components/AuthLayout';
export { FormField } from './components/FormField';
export { ErrorBanner } from './components/ErrorBanner';

// Guards
export { AuthGate, AuthErrorBoundary } from './guards';

// Hooks
export { useDevAuth, isDevelopment, isClerkConfigured, isAuthEnabled } from './hooks/useDevAuth';
export { useAuthError } from './hooks/useAuthError';

// Utils
export * from './utils/validation';
export * from './utils/errorMessages';

// Constants
export * from './constants';

// Types
export type * from './types';
