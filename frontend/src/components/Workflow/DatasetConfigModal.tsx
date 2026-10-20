import { useState, useEffect } from 'react';
import { Node } from 'reactflow';
import { portfolioApiService } from '@/services/portfolioApi';
import { uploadService, UploadedFile } from '@/services/upload';
import { GoogleDriveNativePicker } from '@/components/KnowledgeGraph/GoogleDriveNativePicker';
import { OneDriveNativePicker } from '@/components/KnowledgeGraph/OneDriveNativePicker';
import { ensureOneDriveConnection } from '@/utils/onedrive';
import googleDriveIcon from '@/assets/connector-logos/google-drive.png';
import oneDriveIcon from '@/assets/connector-logos/one-drive.png';

// Simplified to match backend InputNodeType
type InputType = 'portfolio' | 'uploaded_file' | 'prompt' | 'external_data';

interface DatasetConfiguration {
  inputType: InputType;

  // Portfolio type
  portfolio_id?: string;

  // Uploaded file type
  file_id?: string;

  // Prompt type
  prompt_text?: string;

  // External data type
  external_source?: 'google_drive' | 'onedrive';
}

interface DatasetConfigModalProps {
  node: Node;
  isOpen: boolean;
  onClose: () => void;
  onSave: (nodeId: string, configuration: DatasetConfiguration) => void;
  isDemo?: boolean;
}

export function DatasetConfigModal({ node, isOpen, onClose, onSave, isDemo = false }: DatasetConfigModalProps) {
  const [config, setConfig] = useState<DatasetConfiguration>(
    node.data.configuration || {
      inputType: 'portfolio',
      portfolio_id: undefined,
    },
  );

  const [portfolios, setPortfolios] = useState<any[]>([]);
  const [loadingPortfolios, setLoadingPortfolios] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showDrivePicker, setShowDrivePicker] = useState(false);
  const [showOneDrivePicker, setShowOneDrivePicker] = useState(false);
  const [showOneDriveMenu, setShowOneDriveMenu] = useState(false);
  const [oneDriveAccountType, setOneDriveAccountType] = useState<'personal' | 'business'>('personal');

  useEffect(() => {
    setConfig(node.data.configuration || {
      inputType: 'portfolio',
      portfolio_id: undefined,
    });
  }, [node]);

  // Fetch portfolios when inputType is portfolio
  useEffect(() => {
    if (config.inputType === 'portfolio') {
      setLoadingPortfolios(true);
      portfolioApiService.listPortfolios()
        .then(data => {
          setPortfolios(data || []);
          // Auto-select default portfolio if no selection
          if (!config.portfolio_id && data.length > 0) {
            const defaultPortfolio = data.find((p: any) => p.is_default) || data[0];
            setConfig(prev => ({ ...prev, portfolio_id: defaultPortfolio.id }));
          }
        })
        .catch(err => {
          console.error('Failed to load portfolios:', err);
          setPortfolios([]);
        })
        .finally(() => setLoadingPortfolios(false));
    }
  }, [config.inputType]);

  // Fetch uploaded files when inputType is uploaded_file
  useEffect(() => {
    if (config.inputType === 'uploaded_file') {
      setLoadingFiles(true);
      uploadService.listFiles()
        .then(data => {
          setUploadedFiles(data.files);
        })
        .catch(err => {
          console.error('Failed to load files:', err);
          setUploadedFiles([]);
        })
        .finally(() => setLoadingFiles(false));
    }
  }, [config.inputType]);

  if (!isOpen) return null;

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      const uploaded = await uploadService.uploadFiles(Array.from(files));
      setUploadedFiles(prev => [...uploaded, ...prev]);
      // Auto-select first uploaded file
      if (uploaded.length > 0) {
        setConfig(prev => ({ ...prev, file_id: uploaded[0].id }));
      }
      alert(`Successfully uploaded ${uploaded.length} file(s)`);
    } catch (err: any) {
      alert(err.message || 'Failed to upload files');
    } finally {
      setUploading(false);
      // Reset file input
      event.target.value = '';
    }
  };

  const handleOpenDrivePicker = () => {
    setShowDrivePicker(true);
  };

  const handleOpenOneDrivePicker = async () => {
    const { connected } = await ensureOneDriveConnection();
    if (!connected) {
      return;
    }
    setShowOneDrivePicker(true);
  };

  const handleSave = () => {
    // Validate based on input type
    if (config.inputType === 'portfolio' && !config.portfolio_id) {
      alert('Please select a portfolio');
      return;
    }
    if (config.inputType === 'uploaded_file' && !config.file_id) {
      alert('Please select or upload a file');
      return;
    }
    if (config.inputType === 'external_data' && !config.file_id) {
      alert('Please select a file from Google Drive or OneDrive');
      return;
    }
    if (config.inputType === 'prompt' && !config.prompt_text?.trim()) {
      alert('Please enter prompt text');
      return;
    }

    onSave(node.id, config);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="node-config-modal" role="dialog" aria-modal="true" aria-labelledby="dataset-modal-title" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 id="dataset-modal-title">Configure Input Data</h3>
          <button className="modal-close" aria-label="Close modal" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Input Type Selection */}
          <div className="config-form-group">
            <label className="config-label">Input Type</label>
            <select
              className="config-select"
              value={config.inputType}
              onChange={(e) => setConfig({
                inputType: e.target.value as InputType,
                // Clear type-specific fields when switching
                portfolio_id: undefined,
                file_id: undefined,
                prompt_text: undefined,
                external_source: undefined,
              })}
            >
              <option value="portfolio">Portfolio</option>
              <option value="uploaded_file">Uploaded File</option>
              <option value="external_data">External Data (Google Drive, OneDrive)</option>
              <option value="prompt">Prompt Text</option>
            </select>
            <span className="config-hint">
              {config.inputType === 'portfolio' && 'Use one of your saved portfolios as input'}
              {config.inputType === 'uploaded_file' && 'Upload a file (CSV, PDF, etc.) as input'}
              {config.inputType === 'external_data' && 'Connect to files from Google Drive or OneDrive'}
              {config.inputType === 'prompt' && 'Use custom text as input'}
            </span>
          </div>

          {/* Portfolio Selection */}
          {config.inputType === 'portfolio' && (
            <div className="config-form-group">
              <label className="config-label">Select Portfolio</label>
              <select
                className="config-select"
                value={config.portfolio_id || ''}
                onChange={(e) => setConfig({...config, portfolio_id: e.target.value})}
                disabled={loadingPortfolios}
              >
                {loadingPortfolios ? (
                  <option value="">Loading portfolios...</option>
                ) : portfolios.length === 0 ? (
                  <option value="">No portfolios found - create one first</option>
                ) : (
                  <>
                    <option value="">Select a portfolio</option>
                    {portfolios.map((p: any) => (
                      <option key={p.id} value={p.id}>
                        {p.name} {p.is_default ? '(Default)' : ''} - {p.tickers.length} stocks
                      </option>
                    ))}
                  </>
                )}
              </select>
            </div>
          )}

          {/* File Upload Selection */}
          {config.inputType === 'uploaded_file' && (
            <div className="config-form-group">
              <label className="config-label">Select or Upload File</label>

              {/* Upload Button */}
              <div style={{ marginBottom: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div>
                  <input
                    type="file"
                    id="file-upload-input"
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                    accept=".pdf,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg,.docx"
                    multiple
                    disabled={uploading}
                  />
                  <label htmlFor="file-upload-input">
                    <button
                      className="btn-secondary"
                      onClick={() => document.getElementById('file-upload-input')?.click()}
                      disabled={uploading}
                      type="button"
                      style={{
                        width: '100%',
                        cursor: uploading ? 'not-allowed' : 'pointer',
                        opacity: uploading ? 0.6 : 1,
                      }}
                    >
                      {uploading ? 'Uploading...' : '+ Upload Files'}
                    </button>
                  </label>
                </div>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                  }}
                  onClick={isDemo ? () => alert('Demo Mode - Sign up to connect Google Drive') : handleOpenDrivePicker}
                  disabled={uploading || isDemo}
                >
                  <img src={googleDriveIcon} alt="Google Drive" style={{ width: '18px', height: 'auto' }} />
                  Browse Google Drive {isDemo && '🔒'}
                </button>
                <div style={{ position: 'relative', width: '100%' }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                    }}
                    onClick={isDemo ? () => alert('Demo Mode - Sign up to connect OneDrive') : () => setShowOneDriveMenu(!showOneDriveMenu)}
                    disabled={uploading || isDemo}
                  >
                    <img src={oneDriveIcon} alt="OneDrive" style={{ width: '18px', height: 'auto' }} />
                    Browse OneDrive {isDemo && '🔒'}
                  </button>
                  {showOneDriveMenu && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        marginTop: '4px',
                        backgroundColor: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: '8px',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                        zIndex: 1000,
                        overflow: 'hidden',
                      }}
                    >
                      <button
                        type="button"
                        onClick={async () => {
                          setOneDriveAccountType('personal');
                          setShowOneDriveMenu(false);
                          const { connected } = await ensureOneDriveConnection();
                          if (connected) {
                            setShowOneDrivePicker(true);
                          }
                        }}
                        style={{
                          width: '100%',
                          padding: '10px 16px',
                          textAlign: 'left',
                          border: 'none',
                          background: 'transparent',
                          cursor: 'pointer',
                          fontSize: '14px',
                          color: 'var(--text-primary)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        Personal
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          setOneDriveAccountType('business');
                          setShowOneDriveMenu(false);
                          const { connected } = await ensureOneDriveConnection();
                          if (connected) {
                            setShowOneDrivePicker(true);
                          }
                        }}
                        style={{
                          width: '100%',
                          padding: '10px 16px',
                          textAlign: 'left',
                          border: 'none',
                          background: 'transparent',
                          cursor: 'pointer',
                          fontSize: '14px',
                          color: 'var(--text-primary)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        Business
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* File Selection Dropdown */}
              {loadingFiles ? (
                <div style={{ padding: '12px', textAlign: 'center', color: '#605E5C' }}>
                  Loading files...
                </div>
              ) : uploadedFiles.length === 0 ? (
                <div style={{
                  padding: '12px',
                  textAlign: 'center',
                  color: '#605E5C',
                  border: '1px solid #E1DFDD',
                  borderRadius: '4px',
                  background: '#F3F2F1',
                }}>
                  No files uploaded yet. Upload files using the button above.
                </div>
              ) : (
                <select
                  className="config-select"
                  value={config.file_id || ''}
                  onChange={(e) => setConfig({...config, file_id: e.target.value})}
                >
                  <option value="">Select a file</option>
                  {uploadedFiles.map((f: UploadedFile) => (
                    <option key={f.id} value={f.id}>
                      {f.original_name} ({(f.size / 1024).toFixed(1)} KB)
                    </option>
                  ))}
                </select>
              )}

              <span className="config-hint">
                Supports: PDF, CSV, Excel, TXT, JSON, images, DOCX (max 10MB)
              </span>
            </div>
          )}

          {/* External Data Selection */}
          {config.inputType === 'external_data' && (
            <div className="config-form-group">
              <label className="config-label">Select Data Source</label>

              {/* Source Selection Buttons */}
              <div style={{ marginBottom: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                  }}
                  onClick={isDemo ? () => alert('Demo Mode - Sign up to connect Google Drive') : handleOpenDrivePicker}
                  disabled={uploading || isDemo}
                >
                  <img src={googleDriveIcon} alt="Google Drive" style={{ width: '18px', height: 'auto' }} />
                  Browse Google Drive {isDemo && '🔒'}
                </button>
                <div style={{ position: 'relative', width: '100%' }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                    }}
                    onClick={isDemo ? () => alert('Demo Mode - Sign up to connect OneDrive') : () => setShowOneDriveMenu(!showOneDriveMenu)}
                    disabled={uploading || isDemo}
                  >
                    <img src={oneDriveIcon} alt="OneDrive" style={{ width: '18px', height: 'auto' }} />
                    Browse OneDrive {isDemo && '🔒'}
                  </button>
                  {showOneDriveMenu && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        marginTop: '4px',
                        backgroundColor: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: '8px',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                        zIndex: 1000,
                        overflow: 'hidden',
                      }}
                    >
                      <button
                        type="button"
                        onClick={async () => {
                          setOneDriveAccountType('personal');
                          setShowOneDriveMenu(false);
                          const { connected } = await ensureOneDriveConnection();
                          if (connected) {
                            setShowOneDrivePicker(true);
                          }
                        }}
                        style={{
                          width: '100%',
                          padding: '10px 16px',
                          textAlign: 'left',
                          border: 'none',
                          background: 'transparent',
                          cursor: 'pointer',
                          fontSize: '14px',
                          color: 'var(--text-primary)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        Personal
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          setOneDriveAccountType('business');
                          setShowOneDriveMenu(false);
                          const { connected } = await ensureOneDriveConnection();
                          if (connected) {
                            setShowOneDrivePicker(true);
                          }
                        }}
                        style={{
                          width: '100%',
                          padding: '10px 16px',
                          textAlign: 'left',
                          border: 'none',
                          background: 'transparent',
                          cursor: 'pointer',
                          fontSize: '14px',
                          color: 'var(--text-primary)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        Business
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Selected File Display */}
              {config.file_id && uploadedFiles.length > 0 && (
                <div style={{
                  padding: '12px',
                  border: '1px solid #E1DFDD',
                  borderRadius: '4px',
                  background: '#F3F2F1',
                }}>
                  <div style={{ fontWeight: 500, marginBottom: '4px' }}>Selected File:</div>
                  {uploadedFiles.find(f => f.id === config.file_id)?.original_name || 'Unknown file'}
                </div>
              )}

              <span className="config-hint">
                Connect to external data sources and select files to use as workflow input
              </span>
            </div>
          )}

          {/* Prompt Text Input */}
          {config.inputType === 'prompt' && (
            <div className="config-form-group">
              <label className="config-label">Prompt Text</label>
              <textarea
                className="config-textarea"
                style={{
                  width: '100%',
                  minHeight: '120px',
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #E1DFDD',
                  fontFamily: 'inherit',
                  fontSize: '14px',
                  resize: 'vertical',
                }}
                placeholder="Enter the text or instructions to use as input for this workflow..."
                value={config.prompt_text || ''}
                onChange={(e) => setConfig({...config, prompt_text: e.target.value})}
              />
              <span className="config-hint">
                This text will be passed as {'{input}'} to the first agent
              </span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save Configuration</button>
        </div>
      </div>

      {showDrivePicker && (
        <GoogleDriveNativePicker
          onSelect={async (file: File) => {
            setShowDrivePicker(false);
            setUploading(true);
            try {
              const uploadedFiles = await uploadService.uploadFiles([file]);
              if (uploadedFiles && uploadedFiles[0]) {
                const driveFile = { ...uploadedFiles[0], source: 'google_drive' };
                setUploadedFiles(prev => [driveFile, ...prev]);
                setConfig(prev => ({
                  ...prev,
                  file_id: driveFile.id,
                  external_source: 'google_drive',
                }));
                alert(`Attached ${file.name} from Google Drive`);
              }
            } catch (error) {
              console.error('Failed to upload file from Google Drive', error);
              alert('Failed to upload file from Google Drive');
            } finally {
              setUploading(false);
            }
          }}
          onClose={() => setShowDrivePicker(false)}
          allowAllFileTypes={true}
        />
      )}

      {showOneDrivePicker && (
        <OneDriveNativePicker
          onSelect={async (file: File) => {
            setShowOneDrivePicker(false);
            setUploading(true);
            try {
              const uploadedFiles = await uploadService.uploadFiles([file]);
              if (uploadedFiles && uploadedFiles[0]) {
                const driveFile = { ...uploadedFiles[0], source: 'onedrive' };
                setUploadedFiles(prev => [driveFile, ...prev]);
                setConfig(prev => ({
                  ...prev,
                  file_id: driveFile.id,
                  external_source: 'onedrive',
                }));
                alert(`Attached ${file.name} from OneDrive`);
              }
            } catch (error) {
              console.error('Failed to upload file from OneDrive', error);
              alert('Failed to upload file from OneDrive');
            } finally {
              setUploading(false);
            }
          }}
          onClose={() => setShowOneDrivePicker(false)}
          allowAllFileTypes={true}
          accountType={oneDriveAccountType}
        />
      )}
    </div>
  );
}
