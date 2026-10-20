/**
 * AuthGate component - Protects routes requiring authentication
 * Uses Clerk's useAuth hook with dev mode fallback
 */

import { useAuth } from '@clerk/clerk-react';
import { Navigate, useLocation } from 'react-router-dom';
import { ReactNode, useEffect } from 'react';
import { useDevAuth, isClerkConfigured, isAuthEnabled } from '../hooks/useDevAuth';
import { AUTH_ROUTES, STORAGE_KEYS } from '../constants';

interface AuthGateProps {
  children: ReactNode;
  fallback?: string;
}

export function AuthGate({ children, fallback = AUTH_ROUTES.LOGIN }: AuthGateProps) {
  const location = useLocation();
  const { isDevMode } = useDevAuth();
  const { isSignedIn, isLoaded } = useAuth();
  const authEnabled = isAuthEnabled();
  const clerkConfigured = isClerkConfigured();

  useEffect(() => {
    if (clerkConfigured && isLoaded && !isSignedIn) {
      localStorage.removeItem(STORAGE_KEYS.CLERK_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    }
  }, [clerkConfigured, isLoaded, isSignedIn]);

  if (!authEnabled || !clerkConfigured || isDevMode) {
    return <>{children}</>;
  }

  // Render children optimistically while Clerk loads — API calls
  // handle 401s gracefully, and we redirect once isLoaded confirms no session
  if (!isLoaded) {
    return <>{children}</>;
  }

  if (!isSignedIn) {
    return <Navigate to={fallback} state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

export default AuthGate;
