/**
 * SSO Callback page - handles OAuth redirects
 * Handles missing requirements (e.g., Google not returning last_name) by providing defaults
 */

import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClerk, useUser, useSignUp, useSignIn } from '@clerk/clerk-react';
import { AUTH_ROUTES, TIMING } from '../constants';

export function SSOCallbackPage() {
  const navigate = useNavigate();
  const clerk = useClerk();
  const { isSignedIn, isLoaded: userLoaded } = useUser();
  const { signUp, setActive: setSignUpActive } = useSignUp();
  const { signIn, setActive: setSignInActive } = useSignIn();
  const [error, setError] = useState<string | null>(null);
  const processedRef = useRef(false);

  useEffect(() => {
    const handleCallback = async () => {
      // Prevent double processing
      if (!clerk.loaded || processedRef.current) {
        return;
      }
      processedRef.current = true;

      try {
        const baseUrl = window.location.origin;
        
        // Check sign-in first (existing user)
        if (signIn && signIn.status === 'complete' && signIn.createdSessionId) {
          console.log('[SSOCallback] Sign-in complete');
          if (setSignInActive) {
            await setSignInActive({ session: signIn.createdSessionId });
          }
          navigate(AUTH_ROUTES.CHAT, { replace: true });
          return;
        }

        // TRANSFER FLOW: User tried to sign-in via OAuth but doesn't exist
        // Transfer the OAuth session to sign-up to create the account
        if (signIn?.firstFactorVerification?.status === 'transferable') {
          console.log('[SSOCallback] Transferring OAuth from sign-in to sign-up (new user on login page)');
          
          const result = await signUp?.create({ transfer: true });
          console.log('[SSOCallback] Transfer result:', result?.status);
          
          if (result?.status === 'complete' && result?.createdSessionId && setSignUpActive) {
            await setSignUpActive({ session: result.createdSessionId });
            navigate(AUTH_ROUTES.CHAT, { replace: true });
            return;
          }
          // If transfer created sign-up but needs more fields, continue to missing_requirements handling below
        }

        // REVERSE TRANSFER: User tried to sign-up via OAuth but already has an account
        // Transfer the OAuth session to sign-in
        if (signUp?.verifications?.externalAccount?.status === 'transferable') {
          console.log('[SSOCallback] Transferring OAuth from sign-up to sign-in (existing user on register page)');
          
          const result = await signIn?.create({ transfer: true });
          console.log('[SSOCallback] Transfer result:', result?.status);
          
          if (result?.status === 'complete' && result?.createdSessionId && setSignInActive) {
            await setSignInActive({ session: result.createdSessionId });
            navigate(AUTH_ROUTES.CHAT, { replace: true });
            return;
          }
        }

        // Check sign-up status (new user)
        if (signUp) {
          console.log('[SSOCallback] SignUp status:', signUp.status, 'Missing:', signUp.missingFields);
          
          // Handle missing requirements (e.g., Google OAuth not returning last_name)
          if (signUp.status === 'missing_requirements' && signUp.missingFields) {
            const updates: Record<string, string> = {};
            
            if (signUp.missingFields.includes('last_name')) {
              updates.lastName = signUp.firstName || 'User';
              console.log('[SSOCallback] Setting default lastName:', updates.lastName);
            }
            
            if (signUp.missingFields.includes('username')) {
              const email = signUp.emailAddress;
              updates.username = email 
                ? email.split('@')[0] + Math.floor(Math.random() * 1000)
                : 'user' + Date.now();
              console.log('[SSOCallback] Setting default username:', updates.username);
            }
            
            if (Object.keys(updates).length > 0) {
              const result = await signUp.update(updates);
              console.log('[SSOCallback] Update result:', result.status);
              
              // Check if complete after update
              if (result.status === 'complete' && result.createdSessionId && setSignUpActive) {
                await setSignUpActive({ session: result.createdSessionId });
                navigate(AUTH_ROUTES.CHAT, { replace: true });
                return;
              }
            }
          }
          
          // If sign-up is complete, activate session
          if (signUp.status === 'complete' && signUp.createdSessionId && setSignUpActive) {
            await setSignUpActive({ session: signUp.createdSessionId });
            navigate(AUTH_ROUTES.CHAT, { replace: true });
            return;
          }
        }

        // Fallback: use standard handleRedirectCallback
        await clerk.handleRedirectCallback({
          signInForceRedirectUrl: `${baseUrl}${AUTH_ROUTES.CHAT}`,
          signUpForceRedirectUrl: `${baseUrl}${AUTH_ROUTES.CHAT}`,
        });
        
        // Final fallback: navigate after timeout
        setTimeout(() => {
          navigate(AUTH_ROUTES.CHAT, { replace: true });
        }, TIMING.SSO_REDIRECT_TIMEOUT_MS);
      } catch (err) {
        console.error('OAuth callback error:', err);
        setError('Authentication failed. Please try again.');
        setTimeout(() => {
          navigate(AUTH_ROUTES.LOGIN, { replace: true });
        }, 2000);
      }
    };

    handleCallback();
  }, [clerk.loaded, navigate, clerk, signUp, signIn, setSignUpActive, setSignInActive]);

  // If user is already signed in, redirect immediately
  useEffect(() => {
    if (userLoaded && isSignedIn) {
      navigate(AUTH_ROUTES.CHAT, { replace: true });
    }
  }, [userLoaded, isSignedIn, navigate]);

  // Show error state if there's an error
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <p className="text-[var(--text-secondary)] text-sm">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  // Show loading state while processing
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-200" />
          <div className="absolute top-0 left-0 animate-spin rounded-full h-12 w-12 border-4 border-transparent border-t-blue-600" />
        </div>
        <p className="text-[var(--text-secondary)] text-sm">Completing sign in...</p>
      </div>
    </div>
  );
}

export default SSOCallbackPage;
