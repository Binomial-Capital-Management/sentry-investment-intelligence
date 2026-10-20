import { Globe, Cloud, Upload, ArrowUp, StopCircle } from 'lucide-react';
import type { ModelId } from '@/types';
import type { SavedProcess } from '../../types';
import { ModelSelector } from './ModelSelector';
import { CloudMenu } from './CloudMenu';
import { Tooltip } from '@/features/canvas/shared/Tooltip';

const hslIcon = 'hsl(30 3.3% 11.8% / 85%)';
const hslHoverBg = 'hsl(30 3.3% 11.8% / 6%)';
const hslDisabled = 'hsl(30 3.3% 11.8% / 25%)';

interface ChatControlsProps {
  selectedModel: ModelId;
  isModelMenuOpen: boolean;
  setIsModelMenuOpen: (open: boolean) => void;
  setSelectedModel: (model: ModelId) => void;
  isWebSearchEnabled: boolean;
  setIsWebSearchEnabled: (enabled: boolean) => void;
  uploadingFiles: boolean;
  showCloudMenu: boolean;
  onFileUploadClick: () => void;
  onCloudMenuToggle: () => void;
  onCloudMenuClose: () => void;
  onGoogleDrive: () => void;
  onOneDrivePersonal: () => void;
  onOneDriveBusiness: () => void;
  onSharePoint: () => void;
  process: SavedProcess | null;
  input: string;
  isLoading: boolean;
  onSend: () => void;
  onCancel: () => void;
}

export function ChatControls({
  selectedModel,
  isModelMenuOpen,
  setIsModelMenuOpen,
  setSelectedModel,
  isWebSearchEnabled,
  setIsWebSearchEnabled,
  uploadingFiles,
  showCloudMenu,
  onFileUploadClick,
  onCloudMenuToggle,
  onCloudMenuClose,
  onGoogleDrive,
  onOneDrivePersonal,
  onOneDriveBusiness,
  onSharePoint,
  process,
  input,
  isLoading,
  onSend,
  onCancel,
}: ChatControlsProps) {
  return (
    <>
      {/* Left side: file/cloud controls + web search */}
      <div className="flex items-center gap-0.5">
        {/* Cloud Connectors Click Menu */}
        <div className="relative">
          <Tooltip label="Connect cloud storage" side="top">
            <button
              onClick={onCloudMenuToggle}
              className="p-1.5 rounded-md transition-colors"
              style={{ color: hslIcon }}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <Cloud className="w-4 h-4" />
            </button>
          </Tooltip>

          {showCloudMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={onCloudMenuClose} />
              <CloudMenu
                onGoogleDrive={() => { onCloudMenuClose(); onGoogleDrive(); }}
                onOneDrivePersonal={() => { onCloudMenuClose(); onOneDrivePersonal(); }}
                onOneDriveBusiness={() => { onCloudMenuClose(); onOneDriveBusiness(); }}
                onSharePoint={() => { onCloudMenuClose(); onSharePoint(); }}
              />
            </>
          )}
        </div>

        <Tooltip label="Upload file" side="top">
          <button
            onClick={onFileUploadClick}
            disabled={uploadingFiles}
            className="p-1.5 rounded-md transition-colors disabled:cursor-not-allowed"
            style={{ color: uploadingFiles ? hslDisabled : hslIcon }}
            onMouseEnter={e => { if (!uploadingFiles) e.currentTarget.style.backgroundColor = hslHoverBg; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <Upload className="w-4 h-4" />
          </button>
        </Tooltip>

        <Tooltip label={isWebSearchEnabled ? 'Web search enabled' : 'Enable web search'} side="top">
          <button
            onClick={() => setIsWebSearchEnabled(!isWebSearchEnabled)}
            className={`p-1.5 rounded-md transition-colors ${
              isWebSearchEnabled ? 'bg-blue-50 text-blue-600' : ''
            }`}
            style={isWebSearchEnabled ? undefined : { color: hslIcon }}
            onMouseEnter={e => { if (!isWebSearchEnabled) e.currentTarget.style.backgroundColor = hslHoverBg; }}
            onMouseLeave={e => { if (!isWebSearchEnabled) e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <Globe className="w-4 h-4" />
          </button>
        </Tooltip>
      </div>

      {/* Right side: model selector + send button */}
      <div className="flex items-center gap-2">
        <ModelSelector
          selectedModel={selectedModel}
          isModelMenuOpen={isModelMenuOpen}
          setIsModelMenuOpen={setIsModelMenuOpen}
          setSelectedModel={setSelectedModel}
        />

        {isLoading ? (
          <Tooltip label="Stop" side="top">
            <button
              onClick={onCancel}
              className="p-1.5 rounded-md transition-colors"
              style={{ color: hslIcon }}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <StopCircle className="w-4 h-4" />
            </button>
          </Tooltip>
        ) : (
          <Tooltip label="Send message" side="top">
            <button
              onClick={onSend}
              disabled={!input.trim()}
              className={`p-1.5 rounded flex items-center justify-center transition-colors ${
                input.trim()
                  ? 'text-white shadow-sm'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed opacity-55'
              }`}
              style={input.trim() ? { background: 'hsl(217 91% 53%)' } : undefined}
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </Tooltip>
        )}
      </div>
    </>
  );
}
