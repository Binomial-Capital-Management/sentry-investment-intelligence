/**
 * Auth layout component - two-column layout for auth pages
 * Reusable for login, register, and other auth flows
 */

import { Link } from 'react-router-dom';
import type { AuthLayoutProps } from '../types';
import { AUTH_ROUTES } from '../constants';

interface ExtendedAuthLayoutProps extends AuthLayoutProps {
  showBackLink?: boolean;
}

export function AuthLayout({ 
  children, 
  rightContent,
  showBackLink = true 
}: ExtendedAuthLayoutProps) {
  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2">
      {/* Left side - form */}
      <div 
        className="p-8 border-r border-[var(--border)] bg-white"
      >
        <div className="max-w-[520px] mx-auto">
          {/* Logo */}
          <div className="flex items-center gap-2.5 mb-6">
            <img 
              src="/binomial-icon-logo.png" 
              alt="Binomial" 
              className="w-7 h-7" 
            />
            <b>Binomial - Sentry</b>
          </div>

          {/* Form content */}
          {children}

          {/* Back to landing link */}
          {showBackLink && (
            <div className="mt-3">
              <Link 
                to={AUTH_ROUTES.LANDING} 
                className="text-[var(--accent)] hover:underline"
              >
                Back to landing
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Right side - info cards */}
      <div className="hidden md:flex bg-[var(--bg-surface)] p-8 items-center">
        <div className="max-w-[520px] mx-auto">
          {rightContent || <DefaultRightContent />}
        </div>
      </div>
    </div>
  );
}

// Default right content for auth pages
function DefaultRightContent() {
  return (
    <>
      <div className="card p-4 mb-3">
        <h3 className="text-base font-bold">Security First</h3>
        <p className="text-[var(--text-secondary)]">
          Enterprise-grade authentication with Clerk. Your data is protected with industry-standard encryption.
        </p>
      </div>
      <div className="card p-4">
        <h3 className="text-base font-bold">Get Started in Minutes</h3>
        <p className="text-[var(--text-secondary)]">
          Create your account and start analyzing portfolios, managing risk, and making data-driven decisions.
        </p>
      </div>
    </>
  );
}

// Login-specific right content
export function LoginRightContent() {
  return (
    <>
      <div className="card p-4 mb-3">
        <h3 className="text-base font-bold">Security</h3>
        <p className="text-[var(--text-secondary)]">
          We never store credentials; sessions are persisted locally via SQLite by default.
        </p>
      </div>
      <div className="card p-4">
        <h3 className="text-base font-bold">Enterprise Ready</h3>
        <p className="text-[var(--text-secondary)]">
          Docker-based deployment; SSE-compatible proxy examples; configurable providers.
        </p>
      </div>
    </>
  );
}

export default AuthLayout;
