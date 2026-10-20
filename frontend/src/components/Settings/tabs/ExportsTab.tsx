import { useState, useEffect } from 'react';
import { Plus, Settings as SettingsIcon } from 'lucide-react';
import axios from 'axios';
import { getAuthToken } from '@/services/authService';
import ExportStyleCard from '../ExportStyleCard';
import ExportStyleEditor from '../ExportStyleEditor';
import { userSettingsApiService } from '@/services/userSettingsApi';

// API Base URL - use env variable, with smart fallback for different environments
const API_URL = (import.meta as any).env?.VITE_API_BASE ||
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');

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
  created_at: string;
  updated_at: string;
}

const ExportsTab = () => {
  const [styles, setStyles] = useState<ExportStyle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Modal state
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingStyle, setEditingStyle] = useState<ExportStyle | null>(null);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');

  useEffect(() => {
    loadStyles();
  }, []);

  const loadStyles = async () => {
    try {
      setLoading(true);
      setError(null);
      const stylesData = await userSettingsApiService.listExportStyles();
      setStyles(stylesData);
    } catch (err: any) {
      console.error('Failed to load export styles:', err);
      setError('Failed to load export styles. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateStyle = async (styleName: string, settings: ExportSettings, isDefault: boolean) => {
    try {
      setError(null);
      const token = await getAuthToken();
      await axios.post(
        `${API_URL}/api/user-settings/export-styles`,
        {
          style_name: styleName,
          settings,
          is_default: isDefault,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSuccess(`Export style "${styleName}" created successfully!`);
      setTimeout(() => setSuccess(null), 3000);
      await loadStyles(); // Reload styles
    } catch (err: any) {
      console.error('Failed to create export style:', err);
      throw err; // Re-throw to let modal handle it
    }
  };

  const handleUpdateStyle = async (styleName: string, settings: ExportSettings) => {
    try {
      setError(null);
      const token = await getAuthToken();
      await axios.put(
        `${API_URL}/api/user-settings/export-styles/${encodeURIComponent(styleName)}`,
        { settings },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSuccess(`Export style "${styleName}" updated successfully!`);
      setTimeout(() => setSuccess(null), 3000);
      await loadStyles(); // Reload styles
    } catch (err: any) {
      console.error('Failed to update export style:', err);
      throw err; // Re-throw to let modal handle it
    }
  };

  const handleDeleteStyle = async (styleName: string) => {
    if (!confirm(`Are you sure you want to delete the style "${styleName}"?`)) {
      return;
    }

    try {
      setError(null);
      const token = await getAuthToken();
      await axios.delete(
        `${API_URL}/api/user-settings/export-styles/${encodeURIComponent(styleName)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSuccess(`Export style "${styleName}" deleted successfully!`);
      setTimeout(() => setSuccess(null), 3000);
      await loadStyles(); // Reload styles
    } catch (err: any) {
      console.error('Failed to delete export style:', err);
      const errorMsg = err.response?.data?.detail || 'Failed to delete export style';
      setError(errorMsg);
      setTimeout(() => setError(null), 5000);
    }
  };

  const handleSetDefault = async (styleName: string) => {
    try {
      setError(null);
      const token = await getAuthToken();
      await axios.put(
        `${API_URL}/api/user-settings/export-styles/${encodeURIComponent(styleName)}/set-default`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSuccess(`"${styleName}" is now the default export style!`);
      setTimeout(() => setSuccess(null), 3000);
      await loadStyles(); // Reload styles
    } catch (err: any) {
      console.error('Failed to set default style:', err);
      setError('Failed to set default style. Please try again.');
      setTimeout(() => setError(null), 5000);
    }
  };

  const openCreateModal = () => {
    setEditorMode('create');
    setEditingStyle(null);
    setIsEditorOpen(true);
  };

  const openEditModal = (styleName: string) => {
    const style = styles.find((s) => s.style_name === styleName);
    if (style) {
      setEditorMode('edit');
      setEditingStyle(style);
      setIsEditorOpen(true);
    }
  };

  const handleEditorSave = async (styleName: string, settings: ExportSettings, isDefault: boolean) => {
    if (editorMode === 'create') {
      await handleCreateStyle(styleName, settings, isDefault);
    } else {
      await handleUpdateStyle(styleName, settings);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Export Styles</h2>
          <p className="mt-1 text-sm text-gray-500">
            Create and manage export style presets for your Gamma presentations and reports.
          </p>
        </div>
        <button
          onClick={openCreateModal}
          disabled={styles.length >= 10}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          title={styles.length >= 10 ? 'Maximum 10 styles allowed' : 'Create new export style'}
        >
          <Plus className="h-4 w-4 mr-2" />
          Create New Style
        </button>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}
      {success && (
        <div className="rounded-md bg-green-50 p-4">
          <p className="text-sm text-green-800">{success}</p>
        </div>
      )}

      {/* Style Count Info */}
      {styles.length > 0 && (
        <div className="text-sm text-gray-500">
          {styles.length} of 10 export styles created
        </div>
      )}

      {/* Styles Grid */}
      {styles.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <SettingsIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No export styles</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating your first export style preset.
          </p>
          <div className="mt-6">
            <button
              onClick={openCreateModal}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Style
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {styles.map((style) => (
            <ExportStyleCard
              key={style.style_name}
              style={style}
              onEdit={openEditModal}
              onDelete={handleDeleteStyle}
              onSetDefault={handleSetDefault}
            />
          ))}
        </div>
      )}

      {/* Export Style Editor Modal */}
      <ExportStyleEditor
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        onSave={handleEditorSave}
        existingStyle={editingStyle}
        mode={editorMode}
      />
    </div>
  );
};

export default ExportsTab;
