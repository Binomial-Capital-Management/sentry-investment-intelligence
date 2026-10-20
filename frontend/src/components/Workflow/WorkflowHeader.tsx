import { useState, useRef, useEffect } from 'react';

interface WorkflowHeaderProps {
  onClose?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onClearAll?: () => void;
  onReset?: () => void;
  onSave?: () => void;
  onValidate?: () => void;
  onLoad?: (id: string) => void;
  onDelete?: () => void;
  onDeploy?: () => void;
  onMinimize?: () => void;
  onViewResults?: () => void;
  hasResults?: boolean;
  isSaving?: boolean;
  saveSuccess?: boolean;
  isValidating?: boolean;
  isDeploying?: boolean;
  workflows?: Array<{id: string, name: string, created_at: string}>;
  workflowName?: string;
  onWorkflowNameChange?: (name: string) => void;
  onToggleResults?: () => void;
  showResults?: boolean;
  activeTab?: string;
  onTabChange?: (tab: string) => void;
}

export function WorkflowHeader({
  onClose,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  onClearAll,
  onReset,
  onSave,
  onValidate,
  onLoad,
  onDelete,
  onDeploy,
  onMinimize,
  onViewResults,
  hasResults = false,
  isSaving = false,
  saveSuccess = false,
  isValidating = false,
  isDeploying = false,
  workflows = [],
  workflowName = 'Pipeline Builder AI',
  onWorkflowNameChange,
  onToggleResults,
  showResults = false,
  activeTab: externalActiveTab = 'graph',
  onTabChange,
}: WorkflowHeaderProps) {
  const [isStarred, setIsStarred] = useState(false);
  const activeTab = externalActiveTab;
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(workflowName);

  // Handle workflow name save
  const handleSaveName = () => {
    if (editedName.trim() && editedName !== workflowName) {
      onWorkflowNameChange?.(editedName.trim());
    }
    setIsEditingName(false);
  };

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(event.target as Node)) {
        setShowMoreMenu(false);
      }
    };

    if (showMoreMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showMoreMenu]);

  return (
    <div className="workflow-header">
      {/* Left Section */}
      <div className="header-left">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <span className="breadcrumb-item">Workflows</span>
          <svg className="breadcrumb-separator" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          <span className="breadcrumb-item">Builder</span>
          <svg className="breadcrumb-separator" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>

        {/* Workflow Name and Selector combined */}
        <div className="workflow-name" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isEditingName ? (
            // Edit mode - show input
            <input
              type="text"
              className="workflow-name-input"
              value={editedName}
              onChange={(e) => setEditedName(e.target.value)}
              onBlur={handleSaveName}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveName();
                if (e.key === 'Escape') {
                  setEditedName(workflowName);
                  setIsEditingName(false);
                }
              }}
              autoFocus
              style={{
                padding: '4px 8px',
                border: '1px solid #3B82F6',
                borderRadius: '4px',
                fontSize: '14px',
                minWidth: '200px',
                outline: 'none',
              }}
            />
          ) : workflows.length > 0 ? (
            // View mode with workflows - show dropdown
            <select
              className="workflow-selector"
              value={workflowName}
              onChange={(e) => {
                const selectedWorkflow = workflows.find(w => w.name === e.target.value);
                if (selectedWorkflow) {
                  onLoad?.(selectedWorkflow.id);
                } else {
                  onWorkflowNameChange?.(e.target.value);
                }
              }}
              style={{
                padding: '4px 8px',
                border: '1px solid #E1DFDD',
                borderRadius: '4px',
                fontSize: '14px',
                minWidth: '200px',
              }}
            >
              <option value={workflowName}>{workflowName}</option>
              {workflows.map(w => (
                <option key={w.id} value={w.name}>{w.name}</option>
              ))}
            </select>
          ) : (
            // View mode without workflows - show input
            <input
              type="text"
              className="workflow-name-input"
              value={workflowName}
              onChange={(e) => onWorkflowNameChange?.(e.target.value)}
              style={{
                padding: '4px 8px',
                border: '1px solid #E1DFDD',
                borderRadius: '4px',
                fontSize: '14px',
                minWidth: '200px',
              }}
            />
          )}
          {/* Edit button - only show when not editing and workflows exist */}
          {!isEditingName && workflows.length > 0 && (
            <button
              className="header-btn icon-only"
              title="Rename workflow"
              onClick={() => {
                setEditedName(workflowName);
                setIsEditingName(true);
              }}
              style={{
                padding: '4px',
                minWidth: 'auto',
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 16, height: 16 }}>
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
          )}
          <button
            className={`star-btn ${isStarred ? 'starred' : ''}`}
            onClick={() => setIsStarred(!isStarred)}
          >
            <svg viewBox="0 0 24 24" fill={isStarred ? 'currentColor' : 'none'} stroke="currentColor">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
          </button>
        </div>


        {/* Tabs */}
        <div className="header-tabs">
          <div
            className={`header-tab ${activeTab === 'graph' ? 'active' : ''}`}
            onClick={() => onTabChange?.('graph')}
          >
            Graph
          </div>
          <div
            className={`header-tab ${activeTab === 'proposals' ? 'active' : ''}`}
            onClick={() => onTabChange?.('proposals')}
          >
            Proposals
          </div>
          <div
            className={`header-tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => onTabChange?.('history')}
          >
            History
          </div>
          {hasResults && (
            <div
              className={`header-tab ${activeTab === 'results' ? 'active' : ''}`}
              onClick={() => onTabChange?.('results')}
            >
              <div className="flex items-center space-x-1">
                <span>Results</span>
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Section */}
      <div className="header-right">
        {/* Undo/Redo */}
        <button
          className={`header-btn icon-only ${!canUndo ? 'disabled' : ''}`}
          title="Undo (Ctrl+Z)"
          onClick={onUndo}
          disabled={!canUndo}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M3 7v6h6"/>
            <path d="M21 17a9 9 0 00-9-9 9 9 0 00-9 6.26L3 7"/>
          </svg>
        </button>
        <button
          className={`header-btn icon-only ${!canRedo ? 'disabled' : ''}`}
          title="Redo (Ctrl+Y)"
          onClick={onRedo}
          disabled={!canRedo}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M21 7v6h-6"/>
            <path d="M3 17a9 9 0 019-9 9 9 0 019 6.26L21 7"/>
          </svg>
        </button>

        <div className="header-separator" />

        {/* More Options */}
        <div className="dropdown-container" ref={moreMenuRef}>
          <button
            className="header-btn icon-only"
            title="More"
            onClick={() => setShowMoreMenu(!showMoreMenu)}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="5" r="2"/>
              <circle cx="12" cy="12" r="2"/>
              <circle cx="12" cy="19" r="2"/>
            </svg>
          </button>
          {showMoreMenu && (
            <div className="dropdown-menu more-menu">
              <div className="dropdown-section-label">WORKFLOW ACTIONS</div>
              <div
                className="dropdown-item technical"
                onClick={() => {
                  onClearAll?.();
                  setShowMoreMenu(false);
                }}
              >
                <div className="dropdown-item-main">Clear All</div>
                <div className="dropdown-item-sub">Remove all nodes and edges</div>
              </div>
              <div
                className="dropdown-item technical"
                onClick={() => {
                  onReset?.();
                  setShowMoreMenu(false);
                }}
              >
                <div className="dropdown-item-main">Reset to Default</div>
                <div className="dropdown-item-sub">Restore initial workflow</div>
              </div>

              <div className="dropdown-divider" />

              <div
                className="dropdown-item technical"
                onClick={() => {
                  onDelete?.();
                  setShowMoreMenu(false);
                }}
                style={{ color: '#D13438' }}
              >
                <div className="dropdown-item-main">Delete Workflow</div>
                <div className="dropdown-item-sub">Permanently remove this workflow</div>
              </div>

              <div className="dropdown-divider" />
              <div className="dropdown-section-label">IMPORT/EXPORT</div>

              <div className="dropdown-item technical">
                <div className="dropdown-item-main">Import Workflow</div>
                <div className="dropdown-item-sub">Load from JSON file</div>
              </div>
              <div className="dropdown-item technical">
                <div className="dropdown-item-main">Export Workflow</div>
                <div className="dropdown-item-sub">Save as JSON file</div>
              </div>

              <div className="dropdown-divider" />
              <div className="dropdown-section-label">WORKFLOW SETTINGS</div>

              <div className="dropdown-item technical">
                <div className="dropdown-item-main">Duplicate</div>
                <div className="dropdown-item-sub">Create a copy</div>
              </div>
              <div className="dropdown-item technical">
                <div className="dropdown-item-main">Settings</div>
                <div className="dropdown-item-sub">Configure preferences</div>
              </div>

              <div className="dropdown-divider" />
              <div className="dropdown-section-label">VIEW OPTIONS</div>

              <div className="dropdown-item technical">
                <div className="dropdown-item-main">Grid View</div>
                <div className="dropdown-item-sub">Toggle grid overlay</div>
              </div>
              <div className="dropdown-item technical">
                <div className="dropdown-item-main">Explain Mode</div>
                <div className="dropdown-item-sub">Show workflow explanations</div>
              </div>
            </div>
          )}
        </div>

        <div className="header-separator" />

        {/* Save */}
        <button
          className={`header-btn icon-only save-btn ${isSaving ? 'saving' : ''} ${saveSuccess ? 'success' : ''}`}
          title={isSaving ? 'Saving...' : saveSuccess ? 'Saved!' : 'Save'}
          onClick={onSave}
          disabled={isSaving || saveSuccess}
          style={{
            position: 'relative',
            transition: 'all 0.3s ease',
            backgroundColor: saveSuccess ? '#10B981' : undefined,
            borderColor: saveSuccess ? '#10B981' : undefined,
          }}
        >
          {isSaving ? (
            <div className="save-spinner" style={{
              width: '16px',
              height: '16px',
              border: '2px solid #E1DFDD',
              borderTop: '2px solid #0078D4',
              borderRadius: '50%',
              animation: 'spin 0.6s linear infinite',
            }} />
          ) : saveSuccess ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="white" style={{
              animation: 'checkmark-appear 0.3s ease-out',
            }}>
              <polyline points="20 6 9 17 4 12" strokeWidth="2.5"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
              <polyline points="17 21 17 13 7 13 7 21"/>
              <polyline points="7 3 7 8 15 8"/>
            </svg>
          )}
        </button>

        {/* Validate */}
        <button
          className="header-btn"
          title="Validate"
          onClick={onValidate}
          disabled={isValidating}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 16, height: 16 }}>
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          {isValidating ? 'Validating...' : 'Validate'}
        </button>

        {/* Propose */}
        <button className="header-btn primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          Propose
        </button>

        {/* Deploy */}
        <button className={`header-btn deploy-btn ${isDeploying ? 'deploying' : ''}`} onClick={onDeploy} disabled={isDeploying}>
          {isDeploying ? (
            <>
              <div className="deploy-spinner">
                <div className="spinner-ring"></div>
              </div>
              <span className="deploy-text">Running...</span>
              <div className="deploy-progress"></div>
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="deploy-icon">
                <circle cx="12" cy="12" r="10"/>
                <polygon points="10,8 16,12 10,16 10,8"/>
              </svg>
              <span className="deploy-text">Deploy</span>
            </>
          )}
        </button>

        {/* Minimize button - only shown when workflow is running */}
        {isDeploying && onMinimize && (
          <button
            className="header-btn"
            title="Minimize (continue in background)"
            onClick={onMinimize}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 16, height: 16 }}>
              <polyline points="4 14 10 14 10 20"/>
              <polyline points="20 10 14 10 14 4"/>
              <line x1="14" y1="10" x2="21" y2="3"/>
              <line x1="3" y1="21" x2="10" y2="14"/>
            </svg>
            Minimize
          </button>
        )}

        <div className="header-separator" />

        {/* Simplified Zoom Control */}
        <select className="header-btn" defaultValue="100" title="Zoom level" style={{ padding: '6px 10px', fontSize: '14px' }}>
          <option value="50">50%</option>
          <option value="75">75%</option>
          <option value="100">100%</option>
          <option value="125">125%</option>
          <option value="150">150%</option>
        </select>

        {/* Close button if onClose provided */}
        {onClose && (
          <>
            <div className="header-separator" />
            <button className="header-btn" onClick={onClose}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
              Close
            </button>
          </>
        )}
      </div>
    </div>
  );
}
