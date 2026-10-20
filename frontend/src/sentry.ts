/**
 * Sentry initialization for React app
 *
 * Import this at the very top of main.tsx
 */
import * as Sentry from '@sentry/react';
import { useEffect } from 'react';
import {
  createRoutesFromChildren,
  matchRoutes,
  useLocation,
  useNavigationType,
} from 'react-router-dom';

// Initialize Sentry only if DSN is provided
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    integrations: [
      // React Router integration
      Sentry.reactRouterV6BrowserTracingIntegration({
        useEffect,
        useLocation,
        useNavigationType,
        createRoutesFromChildren,
        matchRoutes,
      }),
      // Session replay
      Sentry.replayIntegration({
        maskAllText: false,
        blockAllMedia: false,
      }),
    ],
    // Performance Monitoring
    tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0, // 10% in production

    // Session Replay
    replaysSessionSampleRate: import.meta.env.PROD ? 0.1 : 1.0, // 10% in production
    replaysOnErrorSampleRate: 1.0, // Always capture on errors

    // Environment
    environment: import.meta.env.MODE,

    // Release tracking
    release: import.meta.env.VITE_RELEASE_VERSION || 'v6.1.0',

    // Filtering
    ignoreErrors: [
      // Browser extensions
      'top.GLOBALS',
      // Random network errors
      'Network request failed',
      'NetworkError',
      // Clerk auth errors that are expected
      'Clerk: ',
    ],

    // Before send hook to filter sensitive data
    beforeSend(event) {
      // Filter out sensitive data
      if (event.request) {
        // Remove auth headers
        const headers = event.request.headers as Record<string, string> | undefined;
        if (headers) {
          const sensitiveHeaders = ['authorization', 'cookie', 'x-api-key'];
          sensitiveHeaders.forEach(header => {
            if (headers[header]) {
              headers[header] = '[FILTERED]';
            }
          });
        }

        // Remove sensitive query params
        if (typeof event.request.query_string === 'string') {
          event.request.query_string = event.request.query_string.replace(
            /(?:api_key|token|secret)=[^&]*/gi,
            '$1=[FILTERED]',
          );
        }
      }

      // Don't send events in development unless explicitly enabled
      if (!import.meta.env.PROD && !import.meta.env.VITE_SENTRY_DEBUG) {
        return null;
      }

      return event;
    },
  });

  console.log(`Sentry initialized for environment: ${import.meta.env.MODE}`);
} else {
  console.log('Sentry DSN not provided, error tracking disabled');
}

// Export Sentry for use in error boundaries
export { Sentry };

// Custom hook for capturing exceptions with context
export function useSentryUser(user: any) {
  useEffect(() => {
    if (user && SENTRY_DSN) {
      Sentry.setUser({
        id: user.id,
        email: user.emailAddresses?.[0]?.emailAddress,
        username: user.username,
      });
    } else if (!user && SENTRY_DSN) {
      Sentry.setUser(null);
    }
  }, [user]);
}

// Helper to capture custom events
export function captureCustomEvent(message: string, level: Sentry.SeverityLevel = 'info', extra?: any) {
  if (SENTRY_DSN) {
    Sentry.captureMessage(message, {
      level,
      extra,
    });
  }
}

// Helper to capture exceptions with additional context
export function captureExceptionWithContext(error: Error, context: Record<string, any>) {
  if (SENTRY_DSN) {
    Sentry.withScope((scope) => {
      Object.keys(context).forEach(key => {
        scope.setContext(key, context[key]);
      });
      Sentry.captureException(error);
    });
  }
}
