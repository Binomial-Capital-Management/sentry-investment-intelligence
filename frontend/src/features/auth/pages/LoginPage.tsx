/**
 * Login page - combines AuthLayout with LoginForm
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '@clerk/clerk-react';
import { AuthLayout, LoginRightContent } from '../components/AuthLayout';
import { LoginForm } from '../components/LoginForm';
import { isClerkConfigured } from '../hooks/useDevAuth';
import { AUTH_ROUTES } from '../constants';
import { FallbackLoginForm } from './FallbackForms';

export function LoginPage() {
  const navigate = useNavigate();
  const clerkConfigured = isClerkConfigured();
  
  // Always call hook unconditionally
  const { isSignedIn } = useUser();

  // Redirect if already signed in
  useEffect(() => {
    if (clerkConfigured && isSignedIn) {
      navigate(AUTH_ROUTES.CHAT);
    }
  }, [isSignedIn, navigate, clerkConfigured]);

  return (
    <AuthLayout rightContent={<LoginRightContent />}>
      {clerkConfigured ? (
        <>
          <h1 className="text-[28px] font-extrabold mb-2">
            Welcome back
          </h1>
          <p className="text-[var(--text-secondary)] mb-6">
            Sign in to access the agentic risk workspace.
          </p>
          <LoginForm />
        </>
      ) : (
        <FallbackLoginForm />
      )}
    </AuthLayout>
  );
}

export default LoginPage;
