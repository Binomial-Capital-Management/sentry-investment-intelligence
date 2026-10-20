// Initialize Sentry before anything else
import './sentry';

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ClerkProvider } from '@clerk/clerk-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { AuthProvider } from '@components/Auth/AuthProvider';
import './index.css';
import 'katex/dist/katex.min.css';

// Create a client for TanStack Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5000,
    },
  },
});

// Get Clerk publishable key from environment
const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

// Wrapper component that conditionally adds ClerkProvider and AuthProvider
const AppWithAuth = () => {
  // If no Clerk key, render app without auth (backwards compatible)
  if (!clerkPubKey || clerkPubKey === '') {
    console.log('No Clerk key found, running without auth');
    return (
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    );
  }

  // With Clerk key, wrap app with auth provider
  // ClerkProvider config follows Clerk best practices
  // Using forceRedirectUrl variants to prevent redirect to Clerk's hosted Account Portal
  // when OAuth providers don't return all required fields (last_name, username)
  return (
    <ClerkProvider 
      publishableKey={clerkPubKey}
      signInUrl="/login"
      signUpUrl="/register"
      signInFallbackRedirectUrl="/chat"
      signUpFallbackRedirectUrl="/chat"
      signInForceRedirectUrl="/chat"
      signUpForceRedirectUrl="/chat"
      afterSignOutUrl="/"
    >
      <AuthProvider>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AuthProvider>
    </ClerkProvider>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppWithAuth />
    </BrowserRouter>
  </React.StrictMode>,
);
