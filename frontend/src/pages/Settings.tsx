import { useState } from 'react';
import SettingsHeader from '../components/Settings/SettingsHeader';
import SettingsSidebar from '../components/Settings/SettingsSidebar';
import AccountTab from '../components/Settings/tabs/AccountTab';
import PreferencesTab from '../components/Settings/tabs/PreferencesTab';
import SecurityTab from '../components/Settings/tabs/SecurityTab';
import OrganizationSettings from '../components/Settings/OrganizationSettings';
import IntegrationsTab from '../components/Settings/tabs/IntegrationsTab';
import ExportsTab from '../components/Settings/tabs/ExportsTab';
import DocsTab from '../components/Settings/tabs/DocsTab';

type TabType = 'account' | 'preferences' | 'security' | 'organization' | 'integrations' | 'exports' | 'docs';

const Settings = () => {
  const [activeTab, setActiveTab] = useState<TabType>('account');

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <SettingsHeader />

      <div className="flex-1 flex">
        <SettingsSidebar activeTab={activeTab} setActiveTab={setActiveTab} />

        <div className="flex-1 p-6 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 80px)' }}>
          {activeTab === 'account' && <AccountTab />}
          {activeTab === 'preferences' && <PreferencesTab />}
          {activeTab === 'security' && <SecurityTab />}
          {activeTab === 'organization' && <OrganizationSettings />}
          {activeTab === 'integrations' && <IntegrationsTab />}
          {activeTab === 'exports' && <ExportsTab />}
          {activeTab === 'docs' && <DocsTab />}
        </div>
      </div>
    </div>
  );
};

export default Settings;
