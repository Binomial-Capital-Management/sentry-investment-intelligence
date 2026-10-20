/**
 * Fallback forms for when Clerk is not configured
 * Provides backwards compatibility
 */

import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { AUTH_ROUTES } from '../constants';

export function FallbackLoginForm() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Stub login: accept anything for backwards compatibility
      await new Promise(r => setTimeout(r, 600));
      navigate(AUTH_ROUTES.CHAT);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-[28px] font-extrabold mb-2">Welcome back</h1>
      <p className="text-[var(--text-secondary)]">
        Sign in to access the agentic risk workspace.
      </p>

      <form onSubmit={handleSubmit} className="mt-6">
        <label className="block text-sm mb-1.5 text-[var(--text-secondary)]">
          Work email
        </label>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="input rounded-[10px] w-full"
          placeholder="you@firm.com"
        />

        <label className="block text-sm mb-1.5 mt-3 text-[var(--text-secondary)]">
          Password
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input rounded-[10px] w-full"
          placeholder="••••••••"
        />

        <button
          type="submit"
          className="btn btn-primary rounded-full mt-4 w-full"
          disabled={loading}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </>
  );
}

export function FallbackRegisterForm() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Stub registration: accept anything for backwards compatibility
      await new Promise(r => setTimeout(r, 600));
      navigate(AUTH_ROUTES.CHAT);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-[28px] font-extrabold mb-2">Create your account</h1>
      <p className="text-[var(--text-secondary)]">
        Start using the agentic risk workspace today.
      </p>

      <form onSubmit={handleSubmit} className="mt-6">
        <label className="block text-sm mb-1.5 text-[var(--text-secondary)]">
          Work email
        </label>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="input rounded-[10px] w-full"
          placeholder="you@firm.com"
        />

        <label className="block text-sm mb-1.5 mt-3 text-[var(--text-secondary)]">
          Password
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input rounded-[10px] w-full"
          placeholder="••••••••"
        />

        <label className="block text-sm mb-1.5 mt-3 text-[var(--text-secondary)]">
          Confirm password
        </label>
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="input rounded-[10px] w-full"
          placeholder="••••••••"
        />

        <button
          type="submit"
          className="btn btn-primary rounded-full mt-4 w-full"
          disabled={loading}
        >
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </>
  );
}
