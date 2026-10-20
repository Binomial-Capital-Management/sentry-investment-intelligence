/**
 * Login form component with proper Clerk status handling
 * Handles: email/password sign-in, OAuth, and second factor (Client Trust / MFA)
 */

import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSignIn, useClerk } from '@clerk/clerk-react';
import { OAuthButtons } from '../OAuthButtons';
import { FormField } from '../FormField';
import { ErrorBanner } from '../ErrorBanner';
import { SecondFactorForm } from './SecondFactorForm';
import { useAuthError } from '../../hooks/useAuthError';
import { 
  validateIdentifier, 
  validatePassword 
} from '../../utils/validation';
import { AUTH_ROUTES, SIGN_IN_STATUS, STORAGE_KEYS } from '../../constants';
import type { OAuthProvider, LoginFormErrors, LoginFieldTouched, SignInStep } from '../../types';

export function LoginForm() {
  const navigate = useNavigate();
  const { signIn, isLoaded, setActive } = useSignIn();
  const clerk = useClerk();
  const { parseSignInError, parseOAuthError } = useAuthError();

  // Form state
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<SignInStep>('credentials');
  const [errors, setErrors] = useState<LoginFormErrors>({
    identifier: '',
    password: '',
    secondFactor: '',
    general: '',
  });
  const [touched, setTouched] = useState<LoginFieldTouched>({
    identifier: false,
    password: false,
  });

  // Validate form
  const validateForm = (): boolean => {
    const identifierError = validateIdentifier(identifier);
    const passwordError = validatePassword(password);

    setErrors(prev => ({
      ...prev,
      identifier: identifierError,
      password: passwordError,
      general: '',
    }));

    return !identifierError && !passwordError;
  };

  // Handle input changes
  const handleIdentifierChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setIdentifier(e.target.value);
    if (touched.identifier) {
      setErrors(prev => ({ ...prev, identifier: validateIdentifier(e.target.value) }));
    }
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(e.target.value);
    if (touched.password) {
      setErrors(prev => ({ ...prev, password: validatePassword(e.target.value) }));
    }
  };

  const handleBlur = (field: keyof LoginFieldTouched) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    
    if (field === 'identifier') {
      setErrors(prev => ({ ...prev, identifier: validateIdentifier(identifier) }));
    } else if (field === 'password') {
      setErrors(prev => ({ ...prev, password: validatePassword(password) }));
    }
  };

  // Handle sign-in submit
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched({ identifier: true, password: true });

    if (!validateForm()) return;

    if (!isLoaded || !signIn) {
      setErrors(prev => ({ ...prev, general: 'Authentication service not ready. Please refresh.' }));
      return;
    }

    setLoading(true);
    setErrors(prev => ({ ...prev, general: '' }));

    try {
      const result = await signIn.create({
        identifier,
        password,
      });

      // Handle all possible sign-in statuses (Clerk best practice)
      if (result.status === SIGN_IN_STATUS.COMPLETE) {
        await setActive({ session: result.createdSessionId });
        
        // Restore organization context if saved
        const savedOrgId = localStorage.getItem(STORAGE_KEYS.ACTIVE_ORGANIZATION);
        if (savedOrgId && clerk?.setActive) {
          try {
            await clerk.setActive({ organization: savedOrgId });
          } catch {
            localStorage.removeItem(STORAGE_KEYS.ACTIVE_ORGANIZATION);
          }
        }
        
        navigate(AUTH_ROUTES.CHAT);
      } else if (result.status === SIGN_IN_STATUS.NEEDS_SECOND_FACTOR) {
        // Client Trust or MFA - check supported second factors
        const secondFactors = result.supportedSecondFactors || [];
        
        // Find email_code factor (used for Client Trust / email-based MFA)
        const emailFactor = secondFactors.find(
          (f: { strategy: string }) => f.strategy === 'email_code'
        ) as { strategy: string; emailAddressId?: string } | undefined;
        
        if (emailFactor && emailFactor.emailAddressId) {
          // For email_code second factor, Clerk may auto-send the code
          // Try to prepare explicitly, but proceed even if it fails
          // Note: Clerk types don't include email_code but API supports it per docs
          try {
            await signIn.prepareSecondFactor({
              strategy: 'email_code',
              emailAddressId: emailFactor.emailAddressId,
            } as unknown as Parameters<typeof signIn.prepareSecondFactor>[0]);
          } catch {
            // Email code may already be sent automatically by Clerk
            console.log('[LoginForm] prepareSecondFactor skipped - email may already be sent');
          }
          setStep('second_factor');
        } else {
          // Check for TOTP option
          const totpFactor = secondFactors.find(
            (f: { strategy: string }) => f.strategy === 'totp'
          );
          
          if (totpFactor) {
            setErrors(prev => ({
              ...prev,
              general: 'Please use your authenticator app to complete sign-in.',
            }));
          } else {
            setErrors(prev => ({
              ...prev,
              general: 'Additional verification required but no supported method available.',
            }));
          }
        }
      } else if (result.status === SIGN_IN_STATUS.NEEDS_FIRST_FACTOR) {
        setErrors(prev => ({
          ...prev,
          general: 'Additional verification required. Please complete the sign-in process.',
        }));
      } else {
        setErrors(prev => ({
          ...prev,
          general: 'Sign-in incomplete. Please try again.',
        }));
      }
    } catch (err: unknown) {
      console.error('Sign-in error:', err);
      
      // Handle session_exists error
      const error = err as { errors?: Array<{ code?: string }> };
      if (error?.errors?.[0]?.code === 'session_exists') {
        navigate(AUTH_ROUTES.CHAT);
        return;
      }
      
      setErrors(prev => ({ ...prev, general: parseSignInError(err) }));
    } finally {
      setLoading(false);
    }
  };

  // Handle OAuth sign-in
  const handleOAuthSignIn = async (provider: OAuthProvider) => {
    if (!isLoaded || !signIn) return;

    try {
      // Must use absolute URLs for OAuth redirect
      // Using our SSO callback to handle the redirect properly
      const baseUrl = window.location.origin;
      await signIn.authenticateWithRedirect({
        strategy: provider,
        redirectUrl: `${baseUrl}${AUTH_ROUTES.SSO_CALLBACK}`,
        redirectUrlComplete: `${baseUrl}${AUTH_ROUTES.CHAT}`,
      });
    } catch (err) {
      console.error(`OAuth ${provider} error:`, err);
      setErrors(prev => ({
        ...prev,
        general: parseOAuthError(err, provider),
      }));
    }
  };

  // Show second factor form if needed
  if (step === 'second_factor') {
    return (
      <SecondFactorForm 
        email={identifier}
        onBack={() => {
          setStep('credentials');
          setPassword('');
        }}
      />
    );
  }

  return (
    <div>
      <OAuthButtons onOAuthClick={handleOAuthSignIn} loading={loading} mode="signin" />

      <ErrorBanner message={errors.general} />

      <form onSubmit={handleSubmit}>
        <FormField
          label="Email or username"
          type="text"
          value={identifier}
          onChange={handleIdentifierChange}
          onBlur={() => handleBlur('identifier')}
          placeholder="email or username"
          disabled={loading}
          error={errors.identifier}
          touched={touched.identifier}
        />

        <FormField
          label="Password"
          type="password"
          value={password}
          onChange={handlePasswordChange}
          onBlur={() => handleBlur('password')}
          placeholder="••••••••"
          disabled={loading}
          error={errors.password}
          touched={touched.password}
        />

        {/* Clerk CAPTCHA Widget */}
        <div id="clerk-captcha" className="mb-4" />

        <button
          type="submit"
          className="btn btn-primary w-full rounded-full disabled:opacity-70 disabled:cursor-not-allowed"
          disabled={loading}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}

export default LoginForm;
