/**
 * IBKR Connection Modal - Form for connecting Interactive Brokers accounts
 *
 * Features:
 * - Current Token and Query ID input with validation
 * - Connection name customization
 * - Real-time validation and error display
 * - Loading state during connection
 * - Success feedback with portfolio creation notification
 */

import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';
import {
  connectIBKR,
  validateFlexToken,
  validateFlexQueryId,
} from '../../services/brokerService';
import { IBKRSetupGuideModal } from './IBKRSetupGuideModal';

interface IBKRConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (portfolioId: string, portfolioName: string) => void;
}

export const IBKRConnectionModal: React.FC<IBKRConnectionModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [connectionName, setConnectionName] = useState('My IBKR Account');
  const [flexToken, setFlexToken] = useState('');
  const [flexQueryId, setFlexQueryId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  const [validationErrors, setValidationErrors] = useState<{
    token?: string;
    queryId?: string;
  }>({});

  if (!isOpen) return null;

  const handleTokenChange = (value: string) => {
    setFlexToken(value);
    if (value && !validateFlexToken(value)) {
      setValidationErrors((prev) => ({
        ...prev,
        token: 'Token must be exactly 24 digits',
      }));
    } else {
      setValidationErrors((prev) => ({ ...prev, token: undefined }));
    }
  };

  const handleQueryIdChange = (value: string) => {
    setFlexQueryId(value);
    if (value && !validateFlexQueryId(value)) {
      setValidationErrors((prev) => ({
        ...prev,
        queryId: 'Flex Query ID must be 6-10 digits',
      }));
    } else {
      setValidationErrors((prev) => ({ ...prev, queryId: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Final validation
    if (!validateFlexToken(flexToken)) {
      setValidationErrors((prev) => ({
        ...prev,
        token: 'Flex Token must be exactly 24 digits',
      }));
      return;
    }

    if (!validateFlexQueryId(flexQueryId)) {
      setValidationErrors((prev) => ({
        ...prev,
        queryId: 'Flex Query ID must be 6-10 digits',
      }));
      return;
    }

    if (!connectionName.trim()) {
      setError('Connection name is required');
      return;
    }

    setIsLoading(true);

    try {
      const response = await connectIBKR(flexToken, flexQueryId, connectionName);

      if (response.status === 'connected') {
        // Success - portfolio created
        if (response.portfolio_id && response.portfolio_name) {
          onSuccess(response.portfolio_id, response.portfolio_name);
        }
        handleClose();
      } else if (response.status === 'connected_with_error') {
        // Partial success - connection saved but sync failed
        setError(
          'Connection saved, but initial sync failed. Positions will be synced at next scheduled time (12 PM or 5:30 PM ET).',
        );
      } else {
        setError('Connection failed. Please check your credentials and try again.');
      }
    } catch (err: any) {
      console.error('IBKR connection error:', err);
      const errorMessage =
        err.response?.data?.detail ||
        err.message ||
        'Failed to connect to IBKR. Please verify your credentials.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    // Reset form
    setConnectionName('My IBKR Account');
    setFlexToken('');
    setFlexQueryId('');
    setError(null);
    setValidationErrors({});
    onClose();
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-gray-800">Connect IBKR Account</h2>
            <button
              type="button"
              onClick={() => setShowGuide(true)}
              className="text-gray-400 hover:text-blue-600 transition-colors"
              title="Setup Guide"
            >
              <HelpCircle size={20} />
            </button>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600"
            disabled={isLoading}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Connection Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Connection Name
            </label>
            <input
              type="text"
              value={connectionName}
              onChange={(e) => setConnectionName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., My Trading Account"
              disabled={isLoading}
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Friendly name to identify this broker connection
            </p>
          </div>

          {/* Current Token */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Current Token *
            </label>
            <input
              type="text"
              value={flexToken}
              onChange={(e) => handleTokenChange(e.target.value)}
              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                validationErrors.token
                  ? 'border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:ring-blue-500'
              }`}
              placeholder="24-digit Current Token from IBKR"
              maxLength={24}
              disabled={isLoading}
              required
            />
            {validationErrors.token && (
              <p className="text-xs text-red-600 mt-1">{validationErrors.token}</p>
            )}
            <p className="text-xs text-gray-500 mt-1">
              From IBKR Account Management → Reports → Flex Web Service Configuration
            </p>
          </div>

          {/* Flex Query ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Flex Query ID *
            </label>
            <input
              type="text"
              value={flexQueryId}
              onChange={(e) => handleQueryIdChange(e.target.value)}
              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                validationErrors.queryId
                  ? 'border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:ring-blue-500'
              }`}
              placeholder="6-10 digit Query ID"
              maxLength={10}
              disabled={isLoading}
              required
            />
            {validationErrors.queryId && (
              <p className="text-xs text-red-600 mt-1">{validationErrors.queryId}</p>
            )}
            <p className="text-xs text-gray-500 mt-1">
              From your Activity Flex Query. Required sections: Open Positions, Trades, Cash Report.
              Set Period to "Last 365 Days" for full trade history.
            </p>
          </div>

          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Help Text */}
          <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
            <p className="text-sm text-blue-800">
              <strong>Need help?</strong> Click the{' '}
              <button
                type="button"
                onClick={() => setShowGuide(true)}
                className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium"
              >
                <HelpCircle size={16} className="inline mr-1" />
                Setup Guide
              </button>{' '}
              for step-by-step instructions with screenshots.
            </p>
            <p className="text-xs text-blue-700 mt-2">
              <strong>Quick setup:</strong> Create Activity Flex Query with Open Positions + Trades + Cash Report sections.
              Set Period to "Last 365 Days" for full trade history. Token expires in 6 hours (extend to 1 year in IBKR).
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={handleClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={
                isLoading ||
                !flexToken ||
                !flexQueryId ||
                !!validationErrors.token ||
                !!validationErrors.queryId
              }
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin h-5 w-5 mr-2"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Connecting...
                </span>
              ) : (
                'Connect Account'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>

      {/* Setup Guide Modal */}
      <IBKRSetupGuideModal
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </>
  );
};
