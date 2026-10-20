/**
 * Error banner component for displaying form errors
 */

import { Link } from 'react-router-dom';
import { AUTH_ROUTES } from '../constants';

interface ErrorBannerProps {
  message: string;
  showLoginLink?: boolean;
  variant?: 'error' | 'success' | 'info';
}

export function ErrorBanner({ 
  message, 
  showLoginLink = false,
  variant = 'error' 
}: ErrorBannerProps) {
  if (!message) return null;
  
  const variantStyles = {
    error: 'bg-red-50 border-red-300 text-red-800',
    success: 'bg-green-50 border-green-300 text-green-800',
    info: 'bg-blue-50 border-blue-300 text-blue-800',
  };
  
  // Use explicit variant prop - callers should specify the correct variant
  const effectiveVariant = variant;
  
  return (
    <div 
      className={`
        mb-4 p-3 rounded-md border text-sm
        ${variantStyles[effectiveVariant]}
      `}
    >
      {message}
      {showLoginLink && message.includes('already registered') && (
        <>
          {' '}
          <Link 
            to={AUTH_ROUTES.LOGIN} 
            className="text-red-800 underline font-semibold"
          >
            Log in instead
          </Link>
        </>
      )}
    </div>
  );
}

export default ErrorBanner;
