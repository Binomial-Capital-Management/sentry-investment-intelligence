import UserProfileCard from '../UserProfileCard';
import AccountMetadata from '../AccountMetadata';
import DangerZone from '../DangerZone';

const AccountTab = () => {
  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Account Settings</h1>
        <p className="text-sm text-gray-600 mt-1">
          Manage your personal account information and preferences
        </p>
      </div>

      {/* Content Sections */}
      <div className="space-y-6">
        <UserProfileCard />
        <AccountMetadata />
        <DangerZone />
      </div>
    </div>
  );
};

export default AccountTab;
