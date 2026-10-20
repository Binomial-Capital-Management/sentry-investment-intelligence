/**
 * Email verification form - handles Clerk email code verification
 */

import { useState, FormEvent } from 'react';
import { useSignUp, useClerk } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { FormField } from '../FormField';
import { ErrorBanner } from '../ErrorBanner';
import { useAuthError } from '../../hooks/useAuthError';
import { AUTH_ROUTES, STORAGE_KEYS, VALIDATION_CONSTRAINTS, TIMING } from '../../constants';
import type { PendingOrgData, TeamInvite } from '../../types';

interface VerificationFormProps {
  email: string;
  pendingOrgData?: PendingOrgData | null;
  pendingInvites?: TeamInvite[];
  onBack: () => void;
}

export function VerificationForm({ 
  email, 
  pendingOrgData, 
  pendingInvites = [],
  onBack 
}: VerificationFormProps) {
  const navigate = useNavigate();
  const { signUp, isLoaded, setActive } = useSignUp();
  const clerk = useClerk();
  const { parseVerificationError } = useAuthError();
  
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resendDisabled, setResendDisabled] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!isLoaded || !signUp) {
      setError('Authentication service not ready. Please refresh.');
      return;
    }
    
    if (code.length !== VALIDATION_CONSTRAINTS.VERIFICATION_CODE_LENGTH) {
      setError(`Please enter the ${VALIDATION_CONSTRAINTS.VERIFICATION_CODE_LENGTH}-digit code from your email`);
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const result = await signUp.attemptEmailAddressVerification({ code });
      
      if (result.status === 'complete') {
        // Activate session
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
                } catch (inviteError) {
                  console.error('Failed to send invite:', inviteError);
                }
              }
            }
          } catch (orgError) {
            console.error('Failed to create organization:', orgError);
            // Don't block navigation
          }
        }
        
        navigate(AUTH_ROUTES.CHAT);
      } else if (result.status === 'missing_requirements') {
        const missingFields = result.missingFields?.join(', ') || 'unknown fields';
        setError(`Additional information required: ${missingFields}. Please contact support.`);
      } else {
        setError('Verification incomplete. Please try again.');
      }
    } catch (err) {
      console.error('Verification error:', err);
      setError(parseVerificationError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleResendCode = async () => {
    if (!isLoaded || !signUp) return;
    
    setResendDisabled(true);
    setError('');
    
    try {
      await signUp.prepareEmailAddressVerification({ strategy: 'email_code' });
      setError(`Verification code sent to ${email}`);
      setTimeout(() => setResendDisabled(false), TIMING.RESEND_COOLDOWN_MS);
    } catch (err) {
      console.error('Resend error:', err);
      setError('Failed to resend code. Please try again.');
      setResendDisabled(false);
    }
  };

  return (
    <div>
      <h1 className="text-[28px] font-extrabold mb-2">
        Check your email
      </h1>
      <p className="text-[var(--text-secondary)] mb-6">
        We sent a verification code to <strong>{email}</strong>
      </p>

      <ErrorBanner message={error} />

      <form onSubmit={handleSubmit}>
        <FormField
          label="Verification code"
          type="text"
          value={code}
          onChange={(e) => {
            const value = e.target.value.replace(/\D/g, '').slice(0, 6);
            setCode(value);
            setError('');
          }}
          placeholder="000000"
          maxLength={6}
          className="text-center text-lg tracking-widest"
          disabled={loading}
        />

        <button
          type="submit"
          className="btn btn-primary w-full rounded-full disabled:opacity-70 disabled:cursor-not-allowed"
          disabled={loading || code.length !== 6}
        >
          {loading ? 'Verifying…' : 'Verify email'}
        </button>
      </form>

      <div className="mt-4 text-center text-sm text-[var(--text-secondary)]">
        <button
          onClick={handleResendCode}
          disabled={resendDisabled || loading}
          className={`
            bg-transparent border-none underline p-0 text-sm
            ${resendDisabled ? 'text-[var(--text-secondary)] cursor-not-allowed' : 'text-[var(--accent)] cursor-pointer'}
          `}
        >
          {resendDisabled ? 'Code sent' : "Didn't receive code? Resend"}
        </button>
        {' · '}
        <button
          onClick={onBack}
          disabled={loading}
          className="bg-transparent border-none text-[var(--accent)] underline p-0 text-sm cursor-pointer disabled:cursor-not-allowed"
        >
          Edit email
        </button>
      </div>
    </div>
  );
}

export default VerificationForm;
