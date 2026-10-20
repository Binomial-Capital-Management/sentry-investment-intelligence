import { Star, Edit2, Trash2, Check } from 'lucide-react';

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

interface ExportStyleCardProps {
  style: ExportStyle;
  onEdit: (styleName: string) => void;
  onDelete: (styleName: string) => void;
  onSetDefault: (styleName: string) => void;
}

const ExportStyleCard = ({ style, onEdit, onDelete, onSetDefault }: ExportStyleCardProps) => {
  const { style_name, settings, is_default } = style;

  return (
    <div className={`bg-white shadow sm:rounded-lg border-2 ${is_default ? 'border-indigo-500' : 'border-gray-200'} hover:border-indigo-400 transition-colors`}>
      <div className="px-4 py-5 sm:p-6">
        {/* Header with title and default badge */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center">
            <h3 className="text-lg font-medium text-gray-900">{style_name}</h3>
            {is_default && (
              <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                <Star className="h-3 w-3 mr-1" />
                Default
              </span>
            )}
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => onEdit(style_name)}
              className="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors"
              title="Edit style"
            >
              <Edit2 className="h-4 w-4" />
            </button>
            {!is_default && (
              <button
                onClick={() => onDelete(style_name)}
                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                title="Delete style"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Settings preview */}
        <div className="space-y-2 text-sm text-gray-600">
          {settings.custom_prompt && (
            <div className="flex items-start">
              <span className="font-medium mr-2">Prompt:</span>
              <span className="text-gray-500 truncate flex-1">
                {settings.custom_prompt.slice(0, 100)}
                {settings.custom_prompt.length > 100 ? '...' : ''}
              </span>
            </div>
          )}
          {settings.theme_id && (
            <div className="flex items-center">
              <span className="font-medium mr-2">Theme:</span>
              <span className="text-gray-500">{settings.theme_id}</span>
            </div>
          )}
          <div className="flex items-center space-x-4">
            <div>
              <span className="font-medium mr-2">Language:</span>
              <span className="text-gray-500">{settings.language.toUpperCase()}</span>
            </div>
            <div>
              <span className="font-medium mr-2">Verbosity:</span>
              <span className="text-gray-500 capitalize">{settings.verbosity}</span>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div>
              <span className="font-medium mr-2">Tone:</span>
              <span className="text-gray-500 capitalize">{settings.tone}</span>
            </div>
            <div>
              <span className="font-medium mr-2">Audience:</span>
              <span className="text-gray-500 capitalize">{settings.audience}</span>
            </div>
          </div>
          <div className="flex items-center">
            <span className="font-medium mr-2">Logo:</span>
            <span className="text-gray-500 capitalize">{settings.logo_source === 'themeLogo' ? 'Theme Logo' : settings.logo_source === 'custom' ? 'Custom Upload' : 'None'}</span>
          </div>
        </div>

        {/* Set as Default button */}
        {!is_default && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <button
              onClick={() => onSetDefault(style_name)}
              className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <Check className="h-4 w-4 mr-2" />
              Set as Default
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ExportStyleCard;
