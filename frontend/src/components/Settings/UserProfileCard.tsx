import { useState } from 'react';
import { useUser, UserProfile } from '@clerk/clerk-react';
import { formatDistanceToNow } from 'date-fns';
import { X } from 'lucide-react';
import { useUserUpdate } from '../../hooks/useUserUpdate';
import toast from 'react-hot-toast';

const UserAvatar = ({ imageUrl, name, onClick }: { imageUrl?: string; name: string; onClick: () => void }) => {
  const initials = name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={name}
        onClick={onClick}
        className="w-20 h-20 rounded-lg object-cover cursor-pointer hover:opacity-90 transition-opacity shadow-sm border border-gray-200"
      />
    );
  }

  return (
    <div
      onClick={onClick}
      className="w-20 h-20 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white text-xl font-semibold cursor-pointer hover:from-blue-600 hover:to-blue-700 transition-all shadow-sm"
    >
      {initials}
    </div>
  );
};

const UserProfileCard = () => {
  const { user } = useUser();
  const { updateProfile, isLoading } = useUserUpdate();
  const [showClerkModal, setShowClerkModal] = useState(false);

  const initialValues = {
    username: user?.username || user?.firstName || '',
    organization: (user?.publicMetadata?.organization as string) || '',
    role: (user?.publicMetadata?.role as string) || 'Risk Analyst',
  };

  const [username, setUsername] = useState(initialValues.username);
  const [organization, setOrganization] = useState(initialValues.organization);
  const [role, setRole] = useState(initialValues.role);

  const isDirty = username !== initialValues.username ||
                  organization !== initialValues.organization ||
                  role !== initialValues.role;

  const handleCancel = () => {
    setUsername(initialValues.username);
    setOrganization(initialValues.organization);
    setRole(initialValues.role);
  };

  const handleUpdate = async () => {
    try {
      await updateProfile({
        username: username,
        publicMetadata: {
          ...user?.publicMetadata,
          organization: organization,
          role: role,
        },
      });
      toast.success('Profile updated successfully');
    } catch (error) {
      toast.error('Failed to update profile');
    }
  };

  const fullName = `${user?.firstName || ''} ${user?.lastName || ''}`.trim() || 'User';
  const isEmailVerified = user?.primaryEmailAddress?.verification?.status === 'verified';
  const memberSince = user?.createdAt ? formatDistanceToNow(new Date(user.createdAt), { addSuffix: true }) : '';

  return (
    <>
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Profile Information</h2>
          <p className="text-sm text-gray-600 mt-1">Update your personal details and preferences</p>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Avatar and Basic Info */}
          <div className="flex items-start gap-6">
            <UserAvatar imageUrl={user?.imageUrl} name={fullName} onClick={() => setShowClerkModal(true)} />
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-gray-900">{fullName}</h3>
              <div className="flex items-center gap-2 mt-1.5">
                <p className="text-sm text-gray-600">{user?.primaryEmailAddress?.emailAddress}</p>
                {isEmailVerified ? (
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                    Verified
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-50 text-yellow-700 border border-yellow-200">
                    Unverified
                  </span>
                )}
              </div>
              {memberSince && (
                <p className="text-xs text-gray-500 mt-2">Member {memberSince}</p>
              )}
              <button
                onClick={() => setShowClerkModal(true)}
                className="mt-4 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Advanced Settings
              </button>
            </div>
          </div>

          {/* Form Fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-gray-200">
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                placeholder="Enter username"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Email Address
              </label>
              <input
                type="email"
                value={user?.primaryEmailAddress?.emailAddress || ''}
                readOnly
                className="w-full px-4 py-2 text-sm border border-gray-300 rounded-md bg-gray-50 text-gray-500 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Organization
              </label>
              <input
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                className="w-full px-4 py-2 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                placeholder="Enter organization name"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Role
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full px-4 py-2 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
              >
                <option>Risk Analyst</option>
                <option>Portfolio Manager</option>
                <option>Trader</option>
                <option>Administrator</option>
              </select>
            </div>
          </div>

          {/* Action Buttons */}
          {isDirty && (
            <div className="flex items-center gap-2 pt-4 border-t border-gray-200">
              <button
                onClick={handleUpdate}
                disabled={isLoading}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                onClick={handleCancel}
                disabled={isLoading}
                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Clerk Modal */}
      {showClerkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowClerkModal(false)} />
          <div className="relative bg-white rounded-md shadow-xl max-w-5xl w-full max-h-[90vh] flex flex-col border border-gray-200">
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
    </>
  );
};

export default UserProfileCard;
