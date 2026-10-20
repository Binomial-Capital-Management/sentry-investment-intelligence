import { useState, useEffect, useRef } from 'react';
import { Palette, Plus, X, AlertCircle, ChevronDown, Check } from 'lucide-react';
import axios from 'axios';
import { getAuthToken } from '@/services/authService';

// API Base URL
const API_URL = (import.meta as any).env?.VITE_API_BASE ||
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');

interface GammaTheme {
  id: number;
  name: string;
  gamma_theme_id: string;
  color_description: string;
  created_at: string;
}

interface UserCustomTheme {
  id: number;
  user_id: string;
  name: string;
  gamma_theme_id: string;
  created_at: string;
  updated_at: string;
}

interface ThemeSelectorProps {
  value: string | null;
  onChange: (themeId: string | null) => void;
}

const ThemeSelector = ({ value, onChange }: ThemeSelectorProps) => {
  const [defaultThemes, setDefaultThemes] = useState<GammaTheme[]>([]);
  const [customThemes, setCustomThemes] = useState<UserCustomTheme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canAddCustom, setCanAddCustom] = useState(true);

  // Dropdown state
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Custom theme creation state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newThemeName, setNewThemeName] = useState('');
  const [newThemeId, setNewThemeId] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  useEffect(() => {
    loadThemes();
  }, []);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const loadThemes = async () => {
    try {
      setLoading(true);
      setError(null);
      const token = await getAuthToken();

      const response = await axios.get(`${API_URL}/api/gamma-themes/all`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      setDefaultThemes(response.data.default_themes);
      setCustomThemes(response.data.custom_themes);
      setCanAddCustom(response.data.can_add_custom);
    } catch (err: any) {
      console.error('Failed to load themes:', err);
      setError('Failed to load themes');
    } finally {
      setLoading(false);
    }
  };

  const handleAddCustomTheme = async () => {
    if (!newThemeName.trim() || !newThemeId.trim()) {
      setAddError('Both name and theme ID are required');
      return;
    }

    try {
      setAdding(true);
      setAddError(null);
      const token = await getAuthToken();

      await axios.post(
        `${API_URL}/api/gamma-themes/custom`,
        {
          name: newThemeName.trim(),
          gamma_theme_id: newThemeId.trim(),
        },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );

      // Reset form
      setNewThemeName('');
      setNewThemeId('');
      setShowAddModal(false);

      // Reload themes
      await loadThemes();
    } catch (err: any) {
      console.error('Failed to add custom theme:', err);
      setAddError(err.response?.data?.detail || 'Failed to add custom theme');
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteCustomTheme = async (themeId: number) => {
    if (!confirm('Are you sure you want to delete this custom theme?')) {
      return;
    }

    try {
      const token = await getAuthToken();
      await axios.delete(`${API_URL}/api/gamma-themes/custom/${themeId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      // If deleted theme was selected, clear selection
      const deletedTheme = customThemes.find(t => t.id === themeId);
      if (deletedTheme && value === deletedTheme.gamma_theme_id) {
        onChange(null);
      }

      // Reload themes
      await loadThemes();
    } catch (err: any) {
      console.error('Failed to delete custom theme:', err);
      setError('Failed to delete custom theme');
      setTimeout(() => setError(null), 3000);
    }
  };

  // Find selected theme for display
  const selectedTheme = [...defaultThemes, ...customThemes].find(
    t => t.gamma_theme_id === value,
  );

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-10 bg-gray-200 rounded"></div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Theme Selection Dropdown */}
      <div className="relative" ref={dropdownRef}>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Gamma Theme
        </label>

        {/* Custom Dropdown Button */}
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="relative w-full bg-white border border-gray-300 rounded-md shadow-sm pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm hover:bg-gray-50 transition-colors"
        >
          <span className="block truncate">
            {selectedTheme ? (
              <span className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{selectedTheme.name}</span>
                {'color_description' in selectedTheme && (
                  <span className="text-xs text-gray-500 ml-2">{selectedTheme.color_description}</span>
                )}
              </span>
            ) : (
              <span className="text-gray-500">Select a theme...</span>
            )}
          </span>
          <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
            <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? 'transform rotate-180' : ''}`} />
          </span>
        </button>

        {/* Dropdown Menu */}
        {isOpen && (
          <div className="absolute z-10 mt-1 w-full bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm">
            {/* Default Option */}
            <button
              type="button"
              onClick={() => {
                onChange(null);
                setIsOpen(false);
              }}
              className={`w-full text-left px-3 py-2 hover:bg-indigo-50 flex items-center justify-between ${
                !value ? 'bg-indigo-50 text-indigo-600' : 'text-gray-900'
              }`}
            >
              <span>Default (No theme)</span>
              {!value && <Check className="h-4 w-4 text-indigo-600" />}
            </button>

            {/* System Themes */}
            {defaultThemes.length > 0 && (
              <>
                <div className="px-3 py-1 text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50 border-t border-b border-gray-200">
                  System Themes
                </div>
                {defaultThemes.map((theme) => (
                  <button
                    key={theme.id}
                    type="button"
                    onClick={() => {
                      onChange(theme.gamma_theme_id);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 hover:bg-indigo-50 ${
                      value === theme.gamma_theme_id ? 'bg-indigo-50' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{theme.name}</div>
                        <div className="text-xs text-gray-500">{theme.color_description}</div>
                      </div>
                      {value === theme.gamma_theme_id && (
                        <Check className="h-4 w-4 text-indigo-600 flex-shrink-0 ml-2" />
                      )}
                    </div>
                  </button>
                ))}
              </>
            )}

            {/* Custom Themes */}
            {customThemes.length > 0 && (
              <>
                <div className="px-3 py-1 text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50 border-t border-b border-gray-200">
                  My Custom Themes
                </div>
                {customThemes.map((theme) => (
                  <button
                    key={theme.id}
                    type="button"
                    onClick={() => {
                      onChange(theme.gamma_theme_id);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 hover:bg-indigo-50 ${
                      value === theme.gamma_theme_id ? 'bg-indigo-50' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{theme.name}</div>
                        <div className="text-xs text-gray-500 font-mono">{theme.gamma_theme_id}</div>
                      </div>
                      {value === theme.gamma_theme_id && (
                        <Check className="h-4 w-4 text-indigo-600 flex-shrink-0 ml-2" />
                      )}
                    </div>
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Custom Theme Management */}
      <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-md">
        <div className="flex items-center gap-2">
          <Palette className="h-4 w-4 text-gray-500" />
          <span className="text-sm text-gray-700">
            Custom Themes: {customThemes.length}/4
          </span>
        </div>
        {canAddCustom && (
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 font-medium"
          >
            <Plus className="h-4 w-4" />
            Add Custom
          </button>
        )}
      </div>

      {/* Custom Themes List */}
      {customThemes.length > 0 && (
        <div className="space-y-2">
          {customThemes.map((theme) => (
            <div key={theme.id} className="flex items-center justify-between py-2 px-3 bg-white border border-gray-200 rounded-md">
              <div>
                <p className="text-sm font-medium text-gray-900">{theme.name}</p>
                <p className="text-xs text-gray-500 font-mono">{theme.gamma_theme_id}</p>
              </div>
              <button
                onClick={() => handleDeleteCustomTheme(theme.id)}
                className="text-red-600 hover:text-red-700"
                title="Delete custom theme"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add Custom Theme Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          {/* Backdrop */}
          <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => !adding && setShowAddModal(false)}></div>

          {/* Modal */}
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Add Custom Theme</h3>
                <button
                  onClick={() => !adding && setShowAddModal(false)}
                  disabled={adding}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Error */}
              {addError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-800">{addError}</p>
                </div>
              )}

              {/* Form */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Theme Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newThemeName}
                    onChange={(e) => setNewThemeName(e.target.value)}
                    maxLength={50}
                    placeholder="e.g., My Corporate Theme"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Gamma Theme ID <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newThemeId}
                    onChange={(e) => setNewThemeId(e.target.value)}
                    maxLength={100}
                    placeholder="e.g., glncucs7ja1zd7z"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm font-mono"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Get this from your Gamma theme URL
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="mt-6 flex items-center justify-end gap-3">
                <button
                  onClick={() => setShowAddModal(false)}
                  disabled={adding}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddCustomTheme}
                  disabled={adding}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 disabled:opacity-50"
                >
                  {adding ? 'Adding...' : 'Add Theme'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ThemeSelector;
