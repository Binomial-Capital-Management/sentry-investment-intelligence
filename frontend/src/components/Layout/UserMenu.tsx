import { useState } from 'react';
import { useAuth, useUser, useClerk, UserProfile } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { LogOut, Settings, ChevronDown, User, Shield, Bell } from 'lucide-react';
import clsx from 'clsx';

const UserMenu = () => {
  const { isSignedIn } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [showClerkModal, setShowClerkModal] = useState(false);

  if (!isSignedIn || !user) {
    return null;
  }

  const handleSignOut = async () => {
    try {
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isDevelopment) {
        localStorage.removeItem('clerk-token');
        localStorage.removeItem('auth-token');
      }
      await signOut({ redirectUrl: '/login' });
    } catch (error) {
      console.error('Logout error:', error);
      window.location.href = '/login';
    }
  };

  const userInitials = user.firstName?.[0] || user.emailAddresses?.[0]?.emailAddress?.[0] || 'U';
  const userName = user.firstName || user.emailAddresses?.[0]?.emailAddress?.split('@')[0] || 'User';
  const userEmail = user.emailAddresses?.[0]?.emailAddress;

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          {user.imageUrl ? (
            <img
              src={user.imageUrl}
              alt={userName}
              className="w-8 h-8 rounded-full object-cover"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold">
              {userInitials}
            </div>
          )}
          <span className="text-sm font-medium text-gray-700">
            {userName}
          </span>
          <ChevronDown className={clsx(
            'w-4 h-4 text-gray-500 transition-transform',
            isOpen && 'rotate-180',
          )} />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />

            <div className="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 z-20">
              {/* User info header */}
              <div className="px-4 py-3 border-b border-gray-200">
                <div className="flex items-center gap-3">
                  {user.imageUrl ? (
                    <img
                      src={user.imageUrl}
                      alt={userName}
                      className="w-12 h-12 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-blue-600 text-white flex items-center justify-center text-lg font-semibold">
                      {userInitials}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {user.fullName || userName}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {userEmail}
                    </p>
                  </div>
                </div>
              </div>

              {/* Menu items */}
              <div className="py-1">
                <button
                  onClick={() => {
                    setIsOpen(false);
                    setShowClerkModal(true);
                  }}
                  className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3 transition-colors"
                >
                  <User className="w-4 h-4 text-gray-500" />
                  <div className="flex-1">
                    <p className="font-medium">Manage Account</p>
                    <p className="text-xs text-gray-500">Profile, password, 2FA</p>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setIsOpen(false);
                    navigate('/settings');
                  }}
                  className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3 transition-colors"
                >
                  <Settings className="w-4 h-4 text-gray-500" />
                  <div className="flex-1">
                    <p className="font-medium">Settings</p>
                    <p className="text-xs text-gray-500">Preferences & configuration</p>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setIsOpen(false);
                    navigate('/settings');
                  }}
                  className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3 transition-colors"
                >
                  <Shield className="w-4 h-4 text-gray-500" />
                  <div className="flex-1">
                    <p className="font-medium">Security</p>
                    <p className="text-xs text-gray-500">Sessions & activity</p>
                  </div>
                </button>
              </div>

              {/* Sign out */}
              <div className="border-t border-gray-200 py-1">
                <button
                  onClick={handleSignOut}
                  className="w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-3 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="font-medium">Sign Out</span>
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Clerk Profile Modal */}
      {showClerkModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl border border-gray-200 w-full max-w-5xl max-h-[90vh] flex flex-col">
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
            <div className="border-t border-gray-200 p-4">
              <button
                onClick={() => setShowClerkModal(false)}
                className="w-full px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default UserMenu;
