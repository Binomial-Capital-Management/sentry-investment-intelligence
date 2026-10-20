const SettingsHeader = () => {
  return (
    <div className="bg-white border-b border-gray-200 shadow-sm">
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-gray-900">Configuration</span>
          <div className="w-px h-4 bg-gray-300" />
          <span className="text-sm text-gray-600">Account Settings</span>
        </div>
      </div>
    </div>
  );
};

export default SettingsHeader;
