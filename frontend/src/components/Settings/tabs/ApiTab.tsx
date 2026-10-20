import { useState, useEffect } from 'react';
import { useUser } from '@clerk/clerk-react';
import { toast } from 'sonner';
import { Eye, EyeOff, Save, CheckCircle2 } from 'lucide-react';
import SettingSection from '../SettingSection';
import { API_BASE } from '@/services/api';

const ApiTab = () => {
  const { user } = useUser();
  const [openaiKey, setOpenaiKey] = useState('');
  const [fredKey, setFredKey] = useState('');
  const [showOpenai, setShowOpenai] = useState(false);
  const [showFred, setShowFred] = useState(false);
  const [testingOpenai, setTestingOpenai] = useState(false);
  const [testingFred, setTestingFred] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const initialKeys = {
    openai: (user?.unsafeMetadata?.openai_api_key as string) || '',
    fred: (user?.unsafeMetadata?.fred_api_key as string) || '',
  };

  const isDirty = openaiKey !== initialKeys.openai || fredKey !== initialKeys.fred;

  useEffect(() => {
    if (user) {
      setOpenaiKey(initialKeys.openai);
      setFredKey(initialKeys.fred);
      setLoading(false);
    }
  }, [user]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await user?.update({
        unsafeMetadata: {
          ...user.unsafeMetadata,
          openai_api_key: openaiKey,
          fred_api_key: fredKey,
        },
      });
      toast.success('API keys saved successfully');
    } catch (error) {
      console.error('Failed to save API keys:', error);
      toast.error('Failed to save API keys');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setOpenaiKey(initialKeys.openai);
    setFredKey(initialKeys.fred);
  };

  const testApiKey = async (service: 'openai' | 'fred', key: string) => {
    if (!key) {
      toast.error('Please enter an API key');
      return;
    }

    const setTestingState = service === 'openai' ? setTestingOpenai : setTestingFred;
    setTestingState(true);

    try {
      const response = await fetch(`${API_BASE}/v6/validate-api-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service, apiKey: key }),
      });

      if (response.ok) {
        toast.success(`${service.toUpperCase()} API key is valid`);
      } else {
        toast.error(`Invalid ${service.toUpperCase()} API key`);
      }
    } catch (error) {
      toast.error(`Failed to test ${service.toUpperCase()} API key`);
    } finally {
      setTestingState(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-sm text-gray-500">Loading API configuration...</div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-medium mb-6 text-gray-900">API Configuration</h2>

      <SettingSection title="API Credentials">
        <div className="space-y-4">
          {/* OpenAI API Key */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1.5">OpenAI API Key</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showOpenai ? 'text' : 'password'}
                  placeholder="sk-..."
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowOpenai(!showOpenai)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-gray-700"
                >
                  {showOpenai ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <button
                onClick={() => testApiKey('openai', openaiKey)}
                disabled={testingOpenai || !openaiKey}
                className="px-4 py-2 text-sm font-medium border border-gray-300 bg-white rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {testingOpenai ? 'Testing...' : 'Test'}
              </button>
            </div>
            {openaiKey && openaiKey === initialKeys.openai && (
              <div className="flex items-center gap-1.5 mt-1.5">
                <CheckCircle2 size={14} className="text-green-600" />
                <span className="text-xs text-green-600">Saved</span>
              </div>
            )}
          </div>

          {/* FRED API Key */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1.5">FRED API Key</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showFred ? 'text' : 'password'}
                  placeholder="Enter FRED API key"
                  value={fredKey}
                  onChange={(e) => setFredKey(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowFred(!showFred)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-gray-700"
                >
                  {showFred ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <button
                onClick={() => testApiKey('fred', fredKey)}
                disabled={testingFred || !fredKey}
                className="px-4 py-2 text-sm font-medium border border-gray-300 bg-white rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {testingFred ? 'Testing...' : 'Test'}
              </button>
            </div>
            {fredKey && fredKey === initialKeys.fred && (
              <div className="flex items-center gap-1.5 mt-1.5">
                <CheckCircle2 size={14} className="text-green-600" />
                <span className="text-xs text-green-600">Saved</span>
              </div>
            )}
          </div>

          {/* Save/Cancel Buttons */}
          <div className="flex gap-3 justify-end pt-2 border-t border-gray-200">
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
              className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {saving ? (
                'Saving...'
              ) : (
                <>
                  <Save size={16} />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </SettingSection>

      <div className="bg-white border border-gray-200 rounded-md shadow-sm">
        <div className="bg-gray-100 px-4 py-3 border-b border-gray-200">
          <span className="text-sm font-medium text-gray-900">Data Sources</span>
        </div>
        <div className="p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 text-gray-600 font-medium">Source</th>
                <th className="text-left py-2 text-gray-600 font-medium">Status</th>
                <th className="text-left py-2 text-gray-600 font-medium">Latency</th>
                <th className="text-left py-2 text-gray-600 font-medium">Rate Limit</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100">
                <td className="py-2">Yahoo Finance</td>
                <td className="py-2 text-gray-500">Check backend</td>
                <td className="py-2">-</td>
                <td className="py-2">-</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="py-2">FRED</td>
                <td className="py-2 text-gray-500">Check backend</td>
                <td className="py-2">-</td>
                <td className="py-2">-</td>
              </tr>
              <tr>
                <td className="py-2">OpenAI</td>
                <td className="py-2 text-gray-500">Check backend</td>
                <td className="py-2">-</td>
                <td className="py-2">-</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ApiTab;
