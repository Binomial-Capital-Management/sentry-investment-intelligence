import { useState, useEffect } from 'react';
import { X, FileText, Image, Globe, Settings as SettingsIcon } from 'lucide-react';
import LogoUploader from './LogoUploader';
import LanguageSelector from './LanguageSelector';
import ThemeSelector from './ThemeSelector';

interface ExportSettings {
  custom_prompt: string | null;
  theme_id: string | null;
  logo_source: 'themeLogo' | 'custom' | 'none';
  logo_file_id: string | null;
  logo_url: string | null;
  logo_position: string;
  logo_size: string;
  language: string;
  verbosity: 'brief' | 'low' | 'mid' | 'high';
  tone: string;
  audience: string;
}

interface ExportStyle {
  style_name: string;
  settings: ExportSettings;
  is_default: boolean;
}

interface ExportStyleEditorProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (styleName: string, settings: ExportSettings, isDefault: boolean) => Promise<void>;
  existingStyle?: ExportStyle | null;
  mode: 'create' | 'edit';
}

const DEFAULT_SETTINGS: ExportSettings = {
  custom_prompt: null,
  theme_id: null,
  logo_source: 'themeLogo',
  logo_file_id: null,
  logo_url: null,
  logo_position: 'topRight',
  logo_size: 'md',
  language: 'en',
  verbosity: 'mid',
  tone: 'professional',
  audience: 'expert',
};

const ExportStyleEditor = ({ isOpen, onClose, onSave, existingStyle, mode }: ExportStyleEditorProps) => {
  const [styleName, setStyleName] = useState('');
  const [settings, setSettings] = useState<ExportSettings>(DEFAULT_SETTINGS);
  const [isDefault, setIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existingStyle) {
      setStyleName(existingStyle.style_name);
      setSettings(existingStyle.settings);
      setIsDefault(existingStyle.is_default);
    } else {
      setStyleName('');
      setSettings(DEFAULT_SETTINGS);
      setIsDefault(false);
    }
    setError(null);
  }, [existingStyle, isOpen]);

  const updateSetting = (key: keyof ExportSettings, value: any) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    // Validation
    if (!styleName.trim()) {
      setError('Style name is required');
      return;
    }

    if (!/^[a-zA-Z0-9\s\-_]+$/.test(styleName)) {
      setError('Style name can only contain letters, numbers, spaces, hyphens, and underscores');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      await onSave(styleName.trim(), settings, isDefault);
      onClose();
    } catch (err: any) {
      console.error('Failed to save style:', err);
      setError(err.response?.data?.detail || 'Failed to save export style');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" onClick={onClose}></div>

      {/* Modal */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
            <h2 className="text-xl font-semibold text-gray-900">
              {mode === 'create' ? 'Create New Export Style' : `Edit "${existingStyle?.style_name}"`}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 space-y-6">
            {/* Error Message */}
            {error && (
              <div className="rounded-md bg-red-50 p-4">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {/* Style Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Style Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={styleName}
                onChange={(e) => setStyleName(e.target.value)}
                disabled={mode === 'edit'}
                maxLength={50}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
                placeholder="e.g., Executive Summary, Technical Deep Dive"
              />
              <p className="mt-1 text-xs text-gray-500">
                Letters, numbers, spaces, hyphens, and underscores only (max 50 characters)
              </p>
            </div>

            {/* Set as Default */}
            {mode === 'create' && (
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is-default"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label htmlFor="is-default" className="ml-2 block text-sm text-gray-900">
                  Set as default export style
                </label>
              </div>
            )}

            {/* Custom Prompt Section */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center mb-3">
                <FileText className="h-5 w-5 text-gray-400 mr-2" />
                <h3 className="text-base font-medium text-gray-900">Custom Prompt</h3>
              </div>
              <p className="text-sm text-gray-500 mb-3">
                Override the default institutional prompt with your own instructions.
              </p>
              <textarea
                value={settings.custom_prompt || ''}
                onChange={(e) => updateSetting('custom_prompt', e.target.value || null)}
                rows={4}
                maxLength={5000}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Enter custom instructions (leave empty to use default)"
              />
            </div>

            {/* Theme Section */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center mb-3">
                <SettingsIcon className="h-5 w-5 text-gray-400 mr-2" />
                <h3 className="text-base font-medium text-gray-900">Presentation Theme</h3>
              </div>
              <p className="text-sm text-gray-500 mb-3">
                Select a visual theme for consistent branding. Choose from 12 default themes or create your own custom themes.
              </p>
              <ThemeSelector
                value={settings.theme_id}
                onChange={(themeId) => updateSetting('theme_id', themeId)}
              />
            </div>

            {/* Logo Section */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center mb-3">
                <Image className="h-5 w-5 text-gray-400 mr-2" />
                <h3 className="text-base font-medium text-gray-900">Logo Configuration</h3>
              </div>

              {/* Logo Source */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">Logo Source</label>
                <select
                  value={settings.logo_source}
                  onChange={(e) => updateSetting('logo_source', e.target.value as 'themeLogo' | 'custom' | 'none')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                >
                  <option value="themeLogo">Use Theme Logo</option>
                  <option value="custom">Custom Logo Upload</option>
                  <option value="none">No Logo</option>
                </select>
              </div>

              {/* Logo Upload */}
              {settings.logo_source === 'custom' && (
                <div className="mb-4">
                  <LogoUploader
                    currentLogoUrl={settings.logo_url}
                    currentFileId={settings.logo_file_id}
                    onLogoUploaded={(fileId, logoUrl) => {
                      updateSetting('logo_file_id', fileId);
                      updateSetting('logo_url', logoUrl);
                    }}
                    onLogoRemoved={() => {
                      updateSetting('logo_file_id', null);
                      updateSetting('logo_url', null);
                    }}
                  />
                </div>
              )}

              {/* Logo Position & Size */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Position</label>
                  <select
                    value={settings.logo_position}
                    onChange={(e) => updateSetting('logo_position', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  >
                    <option value="topLeft">Top Left</option>
                    <option value="topRight">Top Right</option>
                    <option value="topCenter">Top Center</option>
                    <option value="bottomLeft">Bottom Left</option>
                    <option value="bottomRight">Bottom Right</option>
                    <option value="bottomCenter">Bottom Center</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Size</label>
                  <select
                    value={settings.logo_size}
                    onChange={(e) => updateSetting('logo_size', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  >
                    <option value="sm">Small</option>
                    <option value="md">Medium</option>
                    <option value="lg">Large</option>
                    <option value="xl">Extra Large</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Language & Text Options Section */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center mb-3">
                <Globe className="h-5 w-5 text-gray-400 mr-2" />
                <h3 className="text-base font-medium text-gray-900">Language & Text Options</h3>
              </div>

              {/* Language Selector */}
              <div className="mb-4">
                <LanguageSelector
                  value={settings.language}
                  onChange={(languageCode) => updateSetting('language', languageCode)}
                />
              </div>

              {/* Verbosity */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">Verbosity</label>
                <select
                  value={settings.verbosity}
                  onChange={(e) => updateSetting('verbosity', e.target.value as 'brief' | 'low' | 'mid' | 'high')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                >
                  <option value="brief">Brief</option>
                  <option value="low">Low</option>
                  <option value="mid">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              {/* Tone and Audience */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Tone</label>
                  <select
                    value={settings.tone}
                    onChange={(e) => updateSetting('tone', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  >
                    <option value="formal">Formal</option>
                    <option value="conversational">Conversational</option>
                    <option value="technical">Technical</option>
                    <option value="academic">Academic</option>
                    <option value="persuasive">Persuasive</option>
                    <option value="neutral">Neutral</option>
                    <option value="engaging">Engaging</option>
                    <option value="strategic">Strategic</option>
                    <option value="direct">Direct</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Audience</label>
                  <select
                    value={settings.audience}
                    onChange={(e) => updateSetting('audience', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  >
                    <option value="C-suite executives">C-suite Executives</option>
                    <option value="Institutional analysts">Institutional Analysts</option>
                    <option value="Potential investors">Potential Investors</option>
                    <option value="Board of directors">Board of Directors</option>
                    <option value="Conference attendees">Conference Attendees</option>
                    <option value="Shareholders">Shareholders</option>
                    <option value="Individual investors">Individual Investors</option>
                    <option value="Leadership team">Leadership Team</option>
                    <option value="Research teams">Research Teams</option>
                    <option value="Busy executives">Busy Executives</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex items-center justify-end space-x-3">
            <button
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : mode === 'create' ? 'Create Style' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExportStyleEditor;
