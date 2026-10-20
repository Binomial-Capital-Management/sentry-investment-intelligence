import { AlertCircle, RefreshCw, WifiOff, ServerCrash, ShieldAlert } from 'lucide-react';

interface ErrorMessageProps {
  error: string | Error;
  onRetry?: () => void;
  type?: 'network' | 'server' | 'auth' | 'generic';
}

export default function ErrorMessage({ error, onRetry, type = 'generic' }: ErrorMessageProps) {
  const errorMessage = error instanceof Error ? error.message : error;

  // Map error types to specific messages and icons
  const errorConfig = {
    network: {
      icon: WifiOff,
      title: 'Connection Problem',
      message: 'Unable to connect to the server. Please check your internet connection.',
      suggestion: 'Try again in a few moments',
    },
    server: {
      icon: ServerCrash,
      title: 'Server Error',
      message: 'Something went wrong on our end.',
      suggestion: 'Our team has been notified. Please try again later.',
    },
    auth: {
      icon: ShieldAlert,
      title: 'Authentication Required',
      message: 'You need to be logged in to access this feature.',
      suggestion: 'Please log in and try again',
    },
    generic: {
      icon: AlertCircle,
      title: 'Something went wrong',
      message: errorMessage || 'An unexpected error occurred.',
      suggestion: 'Please try again or contact support if the problem persists',
    },
  };

  const config = errorConfig[type];
  const Icon = config.icon;

  return (
    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6 max-w-md mx-auto">
      <div className="flex gap-4">
        <div className="flex-shrink-0">
          <Icon className="w-6 h-6 text-red-400" />
        </div>
        <div className="flex-1 space-y-2">
          <h3 className="text-lg font-medium text-white">{config.title}</h3>
          <p className="text-white/70 text-sm">{config.message}</p>
          <p className="text-white/50 text-xs">{config.suggestion}</p>

          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-4 flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Simple inline error for forms
export function InlineError({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 text-red-400 text-sm mt-1">
      <AlertCircle className="w-4 h-4" />
      <span>{message}</span>
    </div>
  );
}
