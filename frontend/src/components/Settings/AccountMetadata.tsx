import { useUser } from '@clerk/clerk-react';
import { format, formatDistanceToNow } from 'date-fns';
import { useState } from 'react';
import toast from 'react-hot-toast';

const AccountMetadata = () => {
  const { user } = useUser();
  const [copied, setCopied] = useState(false);

  const handleCopyId = async () => {
    if (user?.id) {
      await navigator.clipboard.writeText(user.id);
      setCopied(true);
      toast.success('Account ID copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const joinDate = user?.createdAt ? format(new Date(user.createdAt), 'MMMM d, yyyy') : 'Unknown';
  const lastSignIn = user?.lastSignInAt
    ? formatDistanceToNow(new Date(user.lastSignInAt), { addSuffix: true })
    : 'Never';

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Account Information</h2>
        <p className="text-sm text-gray-600 mt-1">View your account details and activity</p>
      </div>

      {/* Content */}
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Account ID */}
          <div className="col-span-2 p-4 border border-gray-200 rounded-md">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-gray-600 mb-1">Account ID</p>
                <p className="text-sm font-mono text-gray-900">{user?.id?.slice(0, 32)}...</p>
              </div>
              <button
                onClick={handleCopyId}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>

          {/* Member Since */}
          <div className="p-4 border border-gray-200 rounded-md">
            <p className="text-xs font-medium text-gray-600 mb-1">Member Since</p>
            <p className="text-sm font-semibold text-gray-900">{joinDate}</p>
          </div>

          {/* Last Sign In */}
          <div className="p-4 border border-gray-200 rounded-md">
            <p className="text-xs font-medium text-gray-600 mb-1">Last Sign In</p>
            <p className="text-sm font-semibold text-gray-900">{lastSignIn}</p>
          </div>

          {/* Account Status */}
          <div className="col-span-2 p-4 border border-gray-200 rounded-md">
            <p className="text-xs font-medium text-gray-600 mb-1">Account Status</p>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                Active
              </span>
              <span className="text-sm text-gray-600">Your account is in good standing</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountMetadata;
