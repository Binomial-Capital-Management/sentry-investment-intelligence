/**
 * Second factor verification form - for Client Trust / MFA
 */

import { useState, FormEvent } from 'react';
import { useSignIn } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { FormField } from '../FormField';
import { ErrorBanner } from '../ErrorBanner';
import { useAuthError } from '../../hooks/useAuthError';
import { AUTH_ROUTES, VALIDATION_CONSTRAINTS } from '../../constants';

interface SecondFactorFormProps {
  email?: string;
  onBack: () => void;
}

export function SecondFactorForm({ email, onBack }: SecondFactorFormProps) {
  const navigate = useNavigate();
  const { signIn, isLoaded, setActive } = useSignIn();
  const { parseSignInError } = useAuthError();
  
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageVariant, setMessageVariant] = useState<'error' | 'info'>('error');
  const [resendDisabled, setResendDisabled] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!isLoaded || !signIn) {
      setMessage('Authentication service not ready. Please refresh.');
      setMessageVariant('error');
      return;
    }
    
    if (code.length !== VALIDATION_CONSTRAINTS.VERIFICATION_CODE_LENGTH) {
      setMessage(`Please enter the ${VALIDATION_CONSTRAINTS.VERIFICATION_CODE_LENGTH}-digit code from your email`);
      setMessageVariant('error');
      return;
    }
    
    setLoading(true);
    setMessage('');
    
    try {
      // Use email_code strategy for email-based second factor verification
      // Note: Clerk types don't include email_code but API supports it per docs
      const result = await signIn.attemptSecondFactor({
        strategy: 'email_code',
        code,
      } as unknown as Parameters<typeof signIn.attemptSecondFactor>[0]);
      
      if (result.status === 'complete') {
        await setActive({ session: result.createdSessionId });
        navigate(AUTH_ROUTES.CHAT);
      } else {
        setMessage('Verification incomplete. Please try again.');
        setMessageVariant('error');
      }
    } catch (err) {
      console.error('Second factor verification error:', err);
      setMessage(parseSignInError(err));
      setMessageVariant('error');
    } finally {
      setLoading(false);
    }
  };

  const handleResendCode = async () => {
    if (!isLoaded || !signIn) return;
    
    setResendDisabled(true);
    setMessage('');
    
    try {
      // Re-prepare the second factor to resend the email code
      const factors = signIn.supportedSecondFactors || [];
      const emailFactor = factors.find(
        (f: { strategy: string }) => f.strategy === 'email_code'
      ) as { strategy: string; emailAddressId?: string } | undefined;
      
      if (emailFactor && emailFactor.emailAddressId) {
        // Note: Clerk types don't include email_code but API supports it per docs
        await signIn.prepareSecondFactor({
          strategy: 'email_code',
          emailAddressId: emailFactor.emailAddressId,
        } as unknown as Parameters<typeof signIn.prepareSecondFactor>[0]);
        setMessage('Verification code sent');
        setMessageVariant('info');
      }
      
      // Re-enable after 60 seconds
      setTimeout(() => setResendDisabled(false), 60000);
    } catch (err) {
      console.error('Resend code error:', err);
      setMessage('Failed to resend code. Please try again.');
      setMessageVariant('error');
      setResendDisabled(false);
    }
  };

  return (
    <div>
      <h1 className="text-[28px] font-extrabold mb-2">
        Check your email
      </h1>
      <p className="text-[var(--text-secondary)] mb-6">
        We sent a verification code to{' '}
        {email && <strong>{email}</strong>}
      </p>

      <ErrorBanner message={message} variant={messageVariant} />

      <form onSubmit={handleSubmit}>
        <FormField
          label="Verification code"
          type="text"
          value={code}
          onChange={(e) => {
            const value = e.target.value.replace(/\D/g, '').slice(0, 6);
            setCode(value);
            setMessage('');
          }}
          placeholder="000000"
          maxLength={6}
          className="text-center text-lg tracking-widest"
          disabled={loading}
        />

        <button
          type="submit"
          className="btn btn-primary w-full rounded-full"
          disabled={loading || code.length !== 6}
        >
          {loading ? 'Verifying…' : 'Verify'}
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
          Use different email
        </button>
      </div>
    </div>
  );
}

export default SecondFactorForm;
