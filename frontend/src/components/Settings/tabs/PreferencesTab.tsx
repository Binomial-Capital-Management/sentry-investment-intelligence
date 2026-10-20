import { useState, useEffect } from 'react';
import { useUser } from '@clerk/clerk-react';
import { toast } from 'sonner';
import SettingSection from '../SettingSection';
import SettingRow from '../SettingRow';

interface Preferences {
  theme: 'light' | 'dark' | 'system';
  decimalPrecision: 2 | 4 | 6;
  timezone: 'UTC' | 'EST' | 'PST' | 'Local';
  notifications: {
    riskLimitBreaches: boolean;
    portfolioRebalancing: boolean;
    marketVolatility: boolean;
    calculationCompletion: boolean;
  };
}

const defaultPreferences: Preferences = {
  theme: 'light',
  decimalPrecision: 4,
  timezone: 'UTC',
  notifications: {
    riskLimitBreaches: true,
    portfolioRebalancing: true,
    marketVolatility: false,
    calculationCompletion: true,
  },
};

const PreferencesTab = () => {
  const { user } = useUser();
  const [preferences, setPreferences] = useState<Preferences>(defaultPreferences);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const initialPreferences: Preferences = {
    theme: (user?.unsafeMetadata?.preferences as any)?.theme || defaultPreferences.theme,
    decimalPrecision: (user?.unsafeMetadata?.preferences as any)?.decimalPrecision || defaultPreferences.decimalPrecision,
    timezone: (user?.unsafeMetadata?.preferences as any)?.timezone || defaultPreferences.timezone,
    notifications: (user?.unsafeMetadata?.preferences as any)?.notifications || defaultPreferences.notifications,
  };

  const isDirty = JSON.stringify(preferences) !== JSON.stringify(initialPreferences);

  useEffect(() => {
    if (user) {
      setPreferences(initialPreferences);
      setLoading(false);
    }
  }, [user]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await user?.update({
        unsafeMetadata: {
          ...user.unsafeMetadata,
          preferences,
        },
      });
      toast.success('Preferences saved successfully');
    } catch (error) {
      console.error('Failed to save preferences:', error);
      toast.error('Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setPreferences(initialPreferences);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-sm text-gray-500">Loading preferences...</div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-medium mb-6 text-gray-900">Preferences</h2>

      <SettingSection title="Display Settings">
        <div className="space-y-4">
          <SettingRow
            label="Theme"
            description="Interface color scheme"
            control={
              <select
                value={preferences.theme}
                onChange={(e) => setPreferences({ ...preferences, theme: e.target.value as any })}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="system">System</option>
              </select>
            }
          />

          <SettingRow
            label="Decimal Precision"
            description="Number of decimal places"
            control={
              <select
                value={preferences.decimalPrecision}
                onChange={(e) => setPreferences({ ...preferences, decimalPrecision: parseInt(e.target.value) as any })}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={2}>2</option>
                <option value={4}>4</option>
                <option value={6}>6</option>
              </select>
            }
          />

          <SettingRow
            label="Time Zone"
            description="Display timezone for timestamps"
            control={
              <select
                value={preferences.timezone}
                onChange={(e) => setPreferences({ ...preferences, timezone: e.target.value as any })}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="UTC">UTC</option>
                <option value="EST">EST</option>
                <option value="PST">PST</option>
                <option value="Local">Local</option>
              </select>
            }
          />
        </div>
      </SettingSection>

      <SettingSection title="Notifications">
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={preferences.notifications.riskLimitBreaches}
              onChange={(e) =>
                setPreferences({
                  ...preferences,
                  notifications: { ...preferences.notifications, riskLimitBreaches: e.target.checked },
                })
              }
              className="w-4 h-4 cursor-pointer"
            />
            <span className="text-sm text-gray-900">Risk limit breaches</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={preferences.notifications.portfolioRebalancing}
              onChange={(e) =>
                setPreferences({
                  ...preferences,
                  notifications: { ...preferences.notifications, portfolioRebalancing: e.target.checked },
                })
              }
              className="w-4 h-4 cursor-pointer"
            />
            <span className="text-sm text-gray-900">Portfolio rebalancing alerts</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={preferences.notifications.marketVolatility}
              onChange={(e) =>
                setPreferences({
                  ...preferences,
                  notifications: { ...preferences.notifications, marketVolatility: e.target.checked },
                })
              }
              className="w-4 h-4 cursor-pointer"
            />
            <span className="text-sm text-gray-900">Market volatility spikes</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={preferences.notifications.calculationCompletion}
              onChange={(e) =>
                setPreferences({
                  ...preferences,
                  notifications: { ...preferences.notifications, calculationCompletion: e.target.checked },
                })
              }
              className="w-4 h-4 cursor-pointer"
            />
            <span className="text-sm text-gray-900">Calculation completion</span>
          </label>
        </div>
      </SettingSection>

      {/* Save/Cancel Buttons */}
      <div className="flex gap-3 justify-end mt-6">
        <button
          onClick={handleCancel}
          disabled={!isDirty || saving}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={!isDirty || saving}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};

export default PreferencesTab;
