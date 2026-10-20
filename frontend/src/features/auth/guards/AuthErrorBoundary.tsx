/**
 * Auth error boundary - catches auth-related errors and displays fallback UI
 */

import { Component, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AUTH_ROUTES } from '../constants';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class AuthErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Auth error boundary caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
          <div className="max-w-md text-center p-8">
            <h1 className="text-2xl font-bold mb-4">Authentication Error</h1>
            <p className="text-[var(--text-secondary)] mb-6">
              Something went wrong with authentication. Please try signing in again.
            </p>
            <div className="flex gap-4 justify-center">
              <Link
                to={AUTH_ROUTES.LOGIN}
                className="btn btn-primary rounded-full px-6"
              >
                Sign In
              </Link>
              <button
                onClick={() => window.location.reload()}
                className="btn rounded-full px-6"
              >
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default AuthErrorBoundary;
