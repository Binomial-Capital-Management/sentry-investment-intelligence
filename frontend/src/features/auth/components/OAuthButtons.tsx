/**
 * OAuth buttons component - Google, Microsoft, GitHub
 * Reusable for both login and registration flows
 */

import type { OAuthProvider } from '../types';

interface OAuthButtonsProps {
  onOAuthClick: (provider: OAuthProvider) => Promise<void>;
  loading?: boolean;
  mode?: 'signin' | 'signup';
}

// Spinner component
const Spinner = () => (
  <svg 
    width="18" 
    height="18" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    className="animate-spin"
  >
    <circle cx="12" cy="12" r="10" opacity="0.25" />
    <path d="M12 2a10 10 0 0 1 10 10" opacity="0.75" />
  </svg>
);

// Google icon
const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18">
    <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
    <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
    <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707 0-.593.102-1.17.282-1.709V4.958H.957C.347 6.173 0 7.548 0 9c0 1.452.348 2.827.957 4.042l3.007-2.335z"/>
    <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/>
  </svg>
);

// Microsoft icon
const MicrosoftIcon = () => (
  <svg width="18" height="18" viewBox="0 0 23 23">
    <path fill="#f35325" d="M0 0h11v11H0z"/>
    <path fill="#81bc06" d="M12 0h11v11H12z"/>
    <path fill="#05a6f0" d="M0 12h11v11H0z"/>
    <path fill="#ffba08" d="M12 12h11v11H12z"/>
  </svg>
);

// GitHub icon
const GitHubIcon = () => (
  <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
  </svg>
);

export function OAuthButtons({ onOAuthClick, loading = false, mode = 'signin' }: OAuthButtonsProps) {
  const buttonText = mode === 'signin' ? 'Continue with' : 'Continue with';
  
  const buttonBaseClass = `
    w-full px-4 py-2.5 mb-2 
    border border-[var(--border)] rounded-[10px]
    bg-[var(--bg-base)] text-[var(--text-primary)]
    text-sm font-medium
    flex items-center justify-center gap-2
    transition-colors duration-200
    hover:bg-[var(--bg-surface)]
    disabled:opacity-70 disabled:cursor-not-allowed
  `;

  return (
    <div className="mb-5">
      <button
        type="button"
        onClick={() => onOAuthClick('oauth_google')}
        disabled={loading}
        className={buttonBaseClass}
      >
        {loading ? <Spinner /> : <GoogleIcon />}
        {buttonText} Google
      </button>

      <button
        type="button"
        onClick={() => onOAuthClick('oauth_microsoft')}
        disabled={loading}
        className={buttonBaseClass}
      >
        {loading ? <Spinner /> : <MicrosoftIcon />}
        {buttonText} Microsoft
      </button>

      <button
        type="button"
        onClick={() => onOAuthClick('oauth_github')}
        disabled={loading}
        className={`${buttonBaseClass} mb-4`}
      >
        {loading ? <Spinner /> : <GitHubIcon />}
        {buttonText} GitHub
      </button>

      {/* Divider */}
      <div className="flex items-center gap-3 my-4">
        <div className="flex-1 h-px bg-[var(--border)]" />
        <span className="text-[13px] text-[var(--text-secondary)]">OR</span>
        <div className="flex-1 h-px bg-[var(--border)]" />
      </div>
    </div>
  );
}

export default OAuthButtons;
