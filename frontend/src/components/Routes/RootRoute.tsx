import { useAuth } from '@clerk/clerk-react';
import { Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Landing from '@components/Landing/Landing';
import { BrandedLoader } from '@/features/auth/components/BrandedLoader';

const RootRoute = () => {
  const [showLoading, setShowLoading] = useState(false);

  // Check if Clerk is configured
  const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

  // Always call hooks unconditionally at the top
  const authResult = useAuth();
  const { isSignedIn, isLoaded } = clerkPubKey ? authResult : { isSignedIn: false, isLoaded: true };

  // Optimistic loading: only show spinner if Clerk takes >200ms
  useEffect(() => {
    if (!isLoaded) {
      const timer = setTimeout(() => setShowLoading(true), 200);
      return () => clearTimeout(timer);
    } else {
      setShowLoading(false);
    }
  }, [isLoaded]);

  // If no auth configured, show landing page (let it handle auth)
  if (!clerkPubKey || clerkPubKey === '') {
    console.log('No Clerk key configured - showing landing page');
    return <Landing />;
  }

  // Only show loading if Clerk is taking longer than 200ms
  if (!isLoaded && showLoading) {
    return <BrandedLoader subtitle="Initializing secure session..." />;
  }

  // Wait for Clerk to load before making routing decisions
  // This prevents the flash of redirecting to /chat then back to landing
  if (!isLoaded) {
    return null; // Will show loading spinner if >200ms
  }

  // Not signed in? Show public landing at /
  if (!isSignedIn) {
    return <Landing />;
  }

  // Signed in? Redirect to chat (with Layout and navigation)
  return <Navigate to="/chat" replace />;
};

export default RootRoute;
