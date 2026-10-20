/**
 * Registration form component with proper Clerk status handling
 * Handles: email/password sign-up, OAuth, email verification, and org creation
 */

import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useSignUp, useClerk } from '@clerk/clerk-react';
import { OAuthButtons } from '../OAuthButtons';
import { FormField } from '../FormField';
import { ErrorBanner } from '../ErrorBanner';
import { VerificationForm } from './VerificationForm';
import { useAuthError } from '../../hooks/useAuthError';
import {
  validateFirstName,
  validateLastName,
  validateUsername,
  validateEmail,
  validatePassword,
  validateConfirmPassword,
} from '../../utils/validation';
import { AUTH_ROUTES, SIGN_UP_STATUS, STORAGE_KEYS } from '../../constants';
import type { 
  OAuthProvider, 
  RegisterFormErrors, 
  RegisterFieldTouched, 
  RegistrationStep,
  PendingOrgData,
  TeamInvite 
} from '../../types';

interface RegisterFormProps {
  pendingOrgData?: PendingOrgData | null;
  pendingInvites?: TeamInvite[];
}

export function RegisterForm({ 
  pendingOrgData = null, 
  pendingInvites = [] 
}: RegisterFormProps) {
  const navigate = useNavigate();
  const { signUp, isLoaded, setActive } = useSignUp();
  const clerk = useClerk();
  const { parseSignUpError, parseOAuthError } = useAuthError();

  // Form state
  const [step, setStep] = useState<RegistrationStep>('registration');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<RegisterFormErrors>({
    firstName: '',
    lastName: '',
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    verificationCode: '',
    general: '',
  });
  const [touched, setTouched] = useState<RegisterFieldTouched>({
    firstName: false,
    lastName: false,
    username: false,
    email: false,
    password: false,
    confirmPassword: false,
  });

  // Validate form
  const validateForm = (): boolean => {
    const newErrors = {
      firstName: validateFirstName(firstName),
      lastName: validateLastName(lastName),
      username: validateUsername(username),
      email: validateEmail(email),
      password: validatePassword(password),
      confirmPassword: validateConfirmPassword(confirmPassword, password),
      verificationCode: '',
      general: '',
    };

    setErrors(newErrors);
    return !Object.values(newErrors).some(e => e !== '');
  };

  // Handle input changes with validation
  const handleChange = (field: keyof RegisterFieldTouched, value: string) => {
    const setters: Record<keyof RegisterFieldTouched, (v: string) => void> = {
      firstName: setFirstName,
      lastName: setLastName,
      username: setUsername,
      email: setEmail,
      password: setPassword,
      confirmPassword: setConfirmPassword,
    };
    
    setters[field](value);
    
    if (touched[field]) {
      const validators: Record<keyof RegisterFieldTouched, (v: string) => string> = {
        firstName: validateFirstName,
        lastName: validateLastName,
        username: validateUsername,
        email: validateEmail,
        password: validatePassword,
        confirmPassword: (v) => validateConfirmPassword(v, field === 'password' ? value : password),
      };
      
      setErrors(prev => ({ ...prev, [field]: validators[field](value) }));
      
      // Revalidate confirm password when password changes
      if (field === 'password' && touched.confirmPassword && confirmPassword) {
        setErrors(prev => ({
          ...prev,
          confirmPassword: value === confirmPassword ? '' : 'Passwords do not match',
        }));
      }
    }
  };

  const handleBlur = (field: keyof RegisterFieldTouched) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    
    const validators: Record<keyof RegisterFieldTouched, () => string> = {
      firstName: () => validateFirstName(firstName),
      lastName: () => validateLastName(lastName),
      username: () => validateUsername(username),
      email: () => validateEmail(email),
      password: () => validatePassword(password),
      confirmPassword: () => validateConfirmPassword(confirmPassword, password),
    };
    
    setErrors(prev => ({ ...prev, [field]: validators[field]() }));
  };

  // Handle registration submit
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    setTouched({
      firstName: true,
      lastName: true,
      username: true,
      email: true,
      password: true,
      confirmPassword: true,
    });

    if (!validateForm()) return;

    if (!isLoaded || !signUp) {
      setErrors(prev => ({ ...prev, general: 'Authentication service not ready. Please refresh.' }));
      return;
    }

    setLoading(true);
    setErrors(prev => ({ ...prev, general: '' }));

    try {
      const result = await signUp.create({
        emailAddress: email,
        password,
        firstName,
        lastName,
        username,
        ...(pendingOrgData && { unsafeMetadata: { pendingOrgData } }),
      });

      if (result.status === SIGN_UP_STATUS.COMPLETE) {
        await setActive({ session: result.createdSessionId });
        
        // Create organization if pending
        if (pendingOrgData && clerk?.createOrganization) {
          try {
            const organization = await clerk.createOrganization({
              name: pendingOrgData.organizationName,
              slug: pendingOrgData.slug,
            });
            
            if (organization && clerk?.setActive) {
              await clerk.setActive({ organization: organization.id });
              localStorage.setItem(STORAGE_KEYS.ACTIVE_ORGANIZATION, organization.id);
              
              // Send invitations
              for (const invite of pendingInvites) {
                try {
                  await organization.inviteMember({
                    emailAddress: invite.email,
                    role: invite.role,
                  });
                } catch {
                  // Continue with other invites
                }
              }
            }
          } catch (orgError) {
            console.error('Failed to create organization:', orgError);
            // Don't block navigation
          }
        }
        
        navigate(AUTH_ROUTES.CHAT);
      } else if (result.status === SIGN_UP_STATUS.MISSING_REQUIREMENTS) {
        // Email verification required
        await signUp.prepareEmailAddressVerification({ strategy: 'email_code' });
        setStep('verification');
      } else {
        setErrors(prev => ({
          ...prev,
          general: 'Registration incomplete. Please try again or contact support.',
        }));
      }
    } catch (err) {
      console.error('Registration error:', err);
      setErrors(prev => ({ ...prev, general: parseSignUpError(err) }));
    } finally {
      setLoading(false);
    }
  };

  // Handle OAuth sign-up
  const handleOAuthSignUp = async (provider: OAuthProvider) => {
    if (!isLoaded || !signUp) return;

    try {
      // Must use absolute URLs for OAuth redirect
      const baseUrl = window.location.origin;
      await signUp.authenticateWithRedirect({
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

  // Show verification form if needed
  if (step === 'verification') {
    return (
      <VerificationForm 
        email={email}
        pendingOrgData={pendingOrgData}
        pendingInvites={pendingInvites}
        onBack={() => {
          setStep('registration');
        }}
      />
    );
  }

  return (
    <div>
      <OAuthButtons onOAuthClick={handleOAuthSignUp} loading={loading} mode="signup" />

      <ErrorBanner message={errors.general} showLoginLink />

      <form onSubmit={handleSubmit}>
        {/* Name fields - side by side */}
        <div className="flex gap-3 mb-3">
          <div className="flex-1">
            <FormField
              label="First name"
              type="text"
              value={firstName}
              onChange={(e) => handleChange('firstName', e.target.value)}
              onBlur={() => handleBlur('firstName')}
              placeholder="John"
              disabled={loading}
              error={errors.firstName}
              touched={touched.firstName}
            />
          </div>
          <div className="flex-1">
            <FormField
              label="Last name"
              type="text"
              value={lastName}
              onChange={(e) => handleChange('lastName', e.target.value)}
              onBlur={() => handleBlur('lastName')}
              placeholder="Doe"
              disabled={loading}
              error={errors.lastName}
              touched={touched.lastName}
            />
          </div>
        </div>

        <FormField
          label="Username"
          type="text"
          value={username}
          onChange={(e) => handleChange('username', e.target.value)}
          onBlur={() => handleBlur('username')}
          placeholder="johndoe123"
          disabled={loading}
          error={errors.username}
          touched={touched.username}
        />

        <FormField
          label="Work email"
          type="email"
          value={email}
          onChange={(e) => handleChange('email', e.target.value)}
          onBlur={() => handleBlur('email')}
          placeholder="you@firm.com"
          disabled={loading}
          error={errors.email}
          touched={touched.email}
        />

        <FormField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => handleChange('password', e.target.value)}
          onBlur={() => handleBlur('password')}
          placeholder="••••••••"
          disabled={loading}
          error={errors.password}
          touched={touched.password}
        />

        <FormField
          label="Confirm password"
          type="password"
          value={confirmPassword}
          onChange={(e) => handleChange('confirmPassword', e.target.value)}
          onBlur={() => handleBlur('confirmPassword')}
          placeholder="••••••••"
          disabled={loading}
          error={errors.confirmPassword}
          touched={touched.confirmPassword}
        />

        {/* Clerk CAPTCHA Widget */}
        <div id="clerk-captcha" className="mb-4" />

        <button
          type="submit"
          className="btn btn-primary w-full rounded-full disabled:opacity-70 disabled:cursor-not-allowed"
          disabled={loading}
        >
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      <div className="mt-4 text-center text-sm text-[var(--text-secondary)]">
        Already have an account?{' '}
        <Link 
          to={AUTH_ROUTES.LOGIN} 
          className="text-[var(--accent)] underline font-semibold"
        >
          Log in
        </Link>
      </div>
    </div>
  );
}

export default RegisterForm;
