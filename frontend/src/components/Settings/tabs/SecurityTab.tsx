import { useState } from 'react';
import { useUser, UserProfile } from '@clerk/clerk-react';
import { formatDistanceToNow } from 'date-fns';
import SettingSection from '../SettingSection';

const SecurityTab = () => {
  const { user } = useUser();
  const [showClerkModal, setShowClerkModal] = useState(false);

  const hasTwoFactor = user?.twoFactorEnabled || false;
  const lastSignIn = user?.lastSignInAt
    ? formatDistanceToNow(new Date(user.lastSignInAt), { addSuffix: true })
    : 'Never';
  const createdAt = user?.createdAt
    ? formatDistanceToNow(new Date(user.createdAt), { addSuffix: true })
    : 'Unknown';

  return (
    <div>
      <h2 className="text-lg font-medium mb-6 text-gray-900">Security Settings</h2>

      <SettingSection title="Authentication & Security">
        <div className="space-y-4">
          {/* 2FA Status */}
          <div className="flex items-center justify-between p-4 border border-gray-200 rounded-md">
            <div>
              <p className="text-sm font-medium text-gray-900">Two-Factor Authentication</p>
              <p className="text-xs text-gray-500 mt-1">
                {hasTwoFactor ? 'Your account is protected with 2FA' : 'Add an extra layer of security'}
              </p>
            </div>
            <div>
              {hasTwoFactor ? (
                <span className="px-3 py-1 text-xs font-medium bg-green-50 text-green-700 border border-green-200 rounded">
                  Enabled
                </span>
              ) : (
                <span className="px-3 py-1 text-xs font-medium bg-yellow-50 text-yellow-700 border border-yellow-200 rounded">
                  Disabled
                </span>
              )}
            </div>
          </div>

          {/* Account Created */}
          <div className="p-4 border border-gray-200 rounded-md">
            <p className="text-sm font-medium text-gray-900">Account Created</p>
            <p className="text-xs text-gray-500 mt-1">{createdAt}</p>
          </div>

          {/* Last Sign In */}
          <div className="p-4 border border-gray-200 rounded-md">
            <p className="text-sm font-medium text-gray-900">Last Sign In</p>
            <p className="text-xs text-gray-500 mt-1">{lastSignIn}</p>
          </div>

          {/* Manage Security Button */}
          <button
            onClick={() => setShowClerkModal(true)}
            className="w-full px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            Advanced Security Settings
          </button>
        </div>
      </SettingSection>

      <SettingSection title="Active Sessions">
        <div className="space-y-3">
          <div className="p-4 border border-gray-200 rounded-md">
            <p className="text-sm font-medium text-gray-900">Current Session</p>
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-gray-500">Active now</p>
              <span className="text-xs font-medium text-green-600">Active</span>
            </div>
          </div>

          <button
            onClick={() => setShowClerkModal(true)}
            className="w-full px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            View All Sessions
          </button>
        </div>
      </SettingSection>

      <SettingSection title="Account Activity">
        <div className="space-y-2">
          <p className="text-xs text-gray-600">
            View your complete account activity history, including sign-ins, password changes, and security
            events in the security settings panel.
          </p>
          <button
            onClick={() => setShowClerkModal(true)}
            className="w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
          >
            View Activity Log
          </button>
        </div>
      </SettingSection>

      {/* Clerk Modal */}
      {showClerkModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowClerkModal(false)} />
          <div className="relative bg-white rounded-md shadow-xl border border-gray-200 w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex-1 overflow-y-auto p-6">
              <UserProfile
                appearance={{
                  elements: {
                    rootBox: 'w-full flex justify-center',
                    card: 'shadow-none border-0 w-full max-w-3xl',
                  },
                }}
              />
            </div>
            <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
              <button
                onClick={() => setShowClerkModal(false)}
                className="w-full px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-100 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SecurityTab;
