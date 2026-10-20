import { useState, useRef } from 'react';
import { Node } from 'reactflow';
import { Sparkles, Zap, FileText, BarChart3, LineChart, Code, Bitcoin, Scale, Calculator, Database, Paperclip, MessageSquare, Type, Presentation, Cloud } from 'lucide-react';

interface WorkflowToolbarProps {
  selectedNode: Node | null;
  onDeleteNode: () => void;
  onAddAgent: (label: string, operation: string, color: string) => void;
  onAddDataset: (type: string, label: string) => void;
  onAddOutput: (label: string, format: string) => void;
  selectMode: boolean;
  onSelectModeChange: (mode: boolean) => void;
  onToggleAI: () => void;
}

export function WorkflowToolbar({
  selectedNode: _selectedNode,
  onDeleteNode: _onDeleteNode,
  onAddAgent,
  onAddDataset,
  onAddOutput,
  selectMode,
  onSelectModeChange,
  onToggleAI,
}: WorkflowToolbarProps) {
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [showDataMenu, setShowDataMenu] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const exportTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const dataTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    setShowPlusMenu(true);
  };

  const handleMouseLeave = () => {
    hoverTimeoutRef.current = setTimeout(() => {
      setShowPlusMenu(false);
    }, 300); // 300ms delay before closing
  };

  const handleExportMouseEnter = () => {
    if (exportTimeoutRef.current) {
      clearTimeout(exportTimeoutRef.current);
    }
    setShowExportMenu(true);
  };

  const handleExportMouseLeave = () => {
    exportTimeoutRef.current = setTimeout(() => {
      setShowExportMenu(false);
    }, 300);
  };

  const handleDataMouseEnter = () => {
    if (dataTimeoutRef.current) {
      clearTimeout(dataTimeoutRef.current);
    }
    setShowDataMenu(true);
  };

  const handleDataMouseLeave = () => {
    dataTimeoutRef.current = setTimeout(() => {
      setShowDataMenu(false);
    }, 300);
  };

  return (
    <div className="tactical-toolbar">
      {/* Left Section - Main Tools */}
      <div className="toolbar-section left">
        {/* Plus button with dropdown */}
        <div
          className="dropdown-container"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <button
            className="toolbar-btn"
            title="Add"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 5v14M5 12h14"/>
            </svg>
          </button>
          {showPlusMenu && (
            <div className="dropdown-menu modern-agent-menu">
              <div className="dropdown-section-label">
                <svg className="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 00-3-3.87m-4-12a4 4 0 010 7.75"/>
                </svg>
                AGENT NODES
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('GENERALIST', 'General Analysis', '#0078D4');
                  setShowPlusMenu(false);
                }}
              >
                <Sparkles size={18} style={{ color: '#3b82f6', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Generalist</div>
                  <div className="agent-desc">General Analysis</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('RISK SPECIALIST', 'Risk Analysis', '#D13438');
                  setShowPlusMenu(false);
                }}
              >
                <Zap size={18} style={{ color: '#ef4444', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Risk Specialist</div>
                  <div className="agent-desc">Risk Analysis</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('DOCUMENT ANALYST', 'Document Processing', '#8B4F9F');
                  setShowPlusMenu(false);
                }}
              >
                <FileText size={18} style={{ color: '#f59e0b', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Document Analyst</div>
                  <div className="agent-desc">Document Processing</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('COMPARABLE COMPANIES', 'Valuation Analysis', '#107C10');
                  setShowPlusMenu(false);
                }}
              >
                <BarChart3 size={18} style={{ color: '#8b5cf6', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Comparable Companies</div>
                  <div className="agent-desc">Valuation Analysis</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('CHART ANALYST', 'Chart Creation', '#FF8C00');
                  setShowPlusMenu(false);
                }}
              >
                <LineChart size={18} style={{ color: '#06b6d4', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Chart Analyst</div>
                  <div className="agent-desc">Chart Creation</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('QUANT CODING', 'Code Interpreter', '#0078D4');
                  setShowPlusMenu(false);
                }}
              >
                <Code size={18} style={{ color: '#ec4899', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Quant Coding</div>
                  <div className="agent-desc">Code Interpreter</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('ALTERNATIVES CODING', 'Crypto/Forex/Commodities', '#FFB900');
                  setShowPlusMenu(false);
                }}
              >
                <Bitcoin size={18} style={{ color: '#f59e0b', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Alternatives Coding</div>
                  <div className="agent-desc">Crypto/Forex/Commodities</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('INSTITUTIONAL ACTIVITY', 'Institutional Trading', '#107C10');
                  setShowPlusMenu(false);
                }}
              >
                <Scale size={18} style={{ color: '#8b5cf6', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Institutional Activity</div>
                  <div className="agent-desc">Institutional Trading</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('DCF AGENT', 'DCF Valuation', '#D13438');
                  setShowPlusMenu(false);
                }}
              >
                <Calculator size={18} style={{ color: '#059669', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">DCF Agent</div>
                  <div className="agent-desc">DCF Valuation</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('OPTIONS CODING', 'Options Analysis', '#8B4F9F');
                  setShowPlusMenu(false);
                }}
              >
                <LineChart size={18} style={{ color: '#6366f1', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Options Coding</div>
                  <div className="agent-desc">Options Analysis</div>
                </div>
              </div>

              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddAgent('PREDICTION MARKETS', 'Prediction Markets', '#0078D4');
                  setShowPlusMenu(false);
                }}
              >
                <BarChart3 size={18} style={{ color: '#14b8a6', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Prediction Markets</div>
                  <div className="agent-desc">Kalshi, Polymarket Analysis</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Select/Safe mode button */}
        <button
          className={`toolbar-btn ${selectMode ? 'active' : ''}`}
          title={selectMode ? 'Select Mode (Safe)' : 'Enable Select Mode'}
          onClick={() => onSelectModeChange(!selectMode)}
        >
          <svg viewBox="0 0 24 24" fill={selectMode ? 'currentColor' : 'none'} stroke="currentColor">
            <path d="M5 3l14 9-7 2-3 7z" strokeLinejoin="round" strokeLinecap="round"/>
          </svg>
        </button>

        {/* Export button with dropdown */}
        <div
          className="dropdown-container"
          onMouseEnter={handleExportMouseEnter}
          onMouseLeave={handleExportMouseLeave}
        >
          <button className="toolbar-btn" title="Export">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
          </button>
          {showExportMenu && (
            <div className="dropdown-menu modern-agent-menu">
              <div className="dropdown-section-label">
                <svg className="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                OUTPUT NODES
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddOutput('Text Output', 'text');
                  setShowExportMenu(false);
                }}
              >
                <Type size={18} style={{ color: '#10b981', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Text Output</div>
                  <div className="agent-desc">Plain text results</div>
                </div>
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddOutput('PDF Report', 'pdf');
                  setShowExportMenu(false);
                }}
              >
                <FileText size={18} style={{ color: '#ef4444', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">PDF Report</div>
                  <div className="agent-desc">Institutional PDF document</div>
                </div>
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddOutput('PowerPoint', 'presentation');
                  setShowExportMenu(false);
                }}
              >
                <Presentation size={18} style={{ color: '#f59e0b', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">PowerPoint</div>
                  <div className="agent-desc">PPT presentation</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Dataset button */}
        <div
          className="dropdown-container"
          onMouseEnter={handleDataMouseEnter}
          onMouseLeave={handleDataMouseLeave}
        >
          <button
            className="toolbar-btn"
            title="Dataset"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/>
            </svg>
          </button>
          {showDataMenu && (
            <div className="dropdown-menu modern-agent-menu">
              <div className="dropdown-section-label">
                <svg className="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/>
                </svg>
                DATA SOURCES
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddDataset('portfolio', 'Portfolio Data');
                  setShowDataMenu(false);
                }}
              >
                <Database size={18} style={{ color: '#0078D4', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">Portfolio Data</div>
                  <div className="agent-desc">User portfolio holdings</div>
                </div>
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddDataset('upload', 'File Upload');
                  setShowDataMenu(false);
                }}
              >
                <Paperclip size={18} style={{ color: '#10b981', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">File Upload</div>
                  <div className="agent-desc">Upload document or data</div>
                </div>
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddDataset('external_data', 'External Data');
                  setShowDataMenu(false);
                }}
              >
                <Cloud size={18} style={{ color: '#f59e0b', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">External Data</div>
                  <div className="agent-desc">Google Drive, OneDrive</div>
                </div>
              </div>
              <div
                className="dropdown-item modern-agent-item"
                onClick={() => {
                  onAddDataset('prompt', 'User Prompt');
                  setShowDataMenu(false);
                }}
              >
                <MessageSquare size={18} style={{ color: '#8b5cf6', flexShrink: 0 }} />
                <div className="agent-content">
                  <div className="agent-name">User Prompt</div>
                  <div className="agent-desc">Custom text input</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Lightbulb button (AI/Ideas) */}
        <button className="toolbar-btn" title="AI Assistant" onClick={onToggleAI}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
          </svg>
        </button>

        {/* Pencil button (Edit) */}
        <button className="toolbar-btn" title="Edit">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
          </svg>
        </button>
      </div>

      {/* Right Section - Search & Help */}
      <div className="toolbar-section right">
        {/* Search button */}
        <button className="toolbar-btn" title="Search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/>
          </svg>
        </button>

        {/* Help button with question mark in circle */}
        <button className="toolbar-btn" title="Help">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3M12 17h.01"/>
          </svg>
        </button>
      </div>
    </div>
  );
}
