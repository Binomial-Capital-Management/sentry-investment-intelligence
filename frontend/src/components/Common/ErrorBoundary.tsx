import { Component, ReactNode } from 'react';
import type { ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message?: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(_error: Error, _errorInfo: ErrorInfo) {
    // Could integrate logging here
    // console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, message: undefined });
    // Optional: force reload route or reset app state
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="m-4 p-3 rounded" style={{ color: 'var(--danger)', background: 'color-mix(in oklab, var(--bg-surface), white 2%)', boxShadow: '0 0 0 1px var(--border) inset' }}>
          <div className="font-semibold" style={{ color: 'var(--danger)' }}>Something went wrong</div>
          <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>{this.state.message || 'Unexpected error.'}</div>
          <button
            type="button"
            onClick={this.handleReset}
            className="mt-3 px-2 py-1 text-xs rounded"
            style={{ boxShadow: '0 0 0 1px var(--border) inset', color: 'var(--text-secondary)' }}
          >
            Dismiss
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
