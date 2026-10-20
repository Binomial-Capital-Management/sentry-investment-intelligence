import { Copy, Check, FileText, Presentation, Sheet, Loader2, Pencil, CheckCircle2 } from 'lucide-react';
import type { Message } from '../../types';

interface ExportButtonsProps {
  message: Message;
  copyFeedback: Record<string, boolean>;
  exportingPdf: Record<string, boolean>;
  exportingPpt: Record<string, boolean>;
  exportingWorkbook: Record<string, boolean>;
  showStyleSelector: boolean;
  availableStyles: Array<{ style_name: string; is_default: boolean }>;
  selectedStyleName: string | null;
  styleSelectorRef: React.RefObject<HTMLDivElement>;
  setShowStyleSelector: (show: boolean) => void;
  setSelectedStyleName: (name: string | null) => void;
  onCopy: () => void;
  onPDFExport: () => void;
  onPPTExport: () => void;
  onWorkbookExport: () => void;
}

const actionBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 24,
  height: 24,
  background: 'transparent',
  border: 'none',
  borderRadius: 'var(--cc-radius-sm)',
  color: 'hsl(var(--cc-text-500))',
  cursor: 'pointer',
  transition: 'background-color 0.15s ease, color 0.15s ease',
};

export function ExportButtons({
  message,
  copyFeedback,
  exportingPdf,
  exportingPpt,
  exportingWorkbook,
  showStyleSelector,
  availableStyles,
  selectedStyleName,
  styleSelectorRef,
  setShowStyleSelector,
  setSelectedStyleName,
  onCopy,
  onPDFExport,
  onPPTExport,
  onWorkbookExport,
}: ExportButtonsProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.125rem', marginTop: '0.5rem' }}>
      {/* Copy */}
      <button
        onClick={onCopy}
        title="Copy message"
        className="cc-btn-ghost"
        style={actionBtnStyle}
      >
        {copyFeedback[message.id] ? (
          <Check size={13} style={{ color: 'hsl(142 71% 45%)' }} strokeWidth={2.5} />
        ) : (
          <Copy size={13} strokeWidth={2} />
        )}
      </button>

      {/* PDF */}
      <button
        onClick={onPDFExport}
        title={exportingPdf[message.id] ? 'Generating PDF...' : 'Export as PDF'}
        disabled={exportingPdf[message.id]}
        className="cc-btn-ghost"
        style={{ ...actionBtnStyle, opacity: exportingPdf[message.id] ? 0.5 : 1 }}
      >
        {exportingPdf[message.id] ? (
          <Loader2 size={13} strokeWidth={2.5} className="animate-spin" />
        ) : (
          <FileText size={13} strokeWidth={2} />
        )}
      </button>

      {/* PowerPoint */}
      <button
        onClick={onPPTExport}
        title={exportingPpt[message.id] ? 'Generating presentation...' : 'Export as PowerPoint'}
        disabled={exportingPpt[message.id]}
        className="cc-btn-ghost"
        style={{ ...actionBtnStyle, opacity: exportingPpt[message.id] ? 0.5 : 1 }}
      >
        {exportingPpt[message.id] ? (
          <Loader2 size={13} strokeWidth={2.5} className="animate-spin" />
        ) : (
          <Presentation size={13} strokeWidth={2} />
        )}
      </button>

      {/* Excel/CSV Workbook */}
      <button
        onClick={onWorkbookExport}
        title={exportingWorkbook[message.id] ? 'Generating workbooks...' : 'Export as Excel/CSV'}
        disabled={exportingWorkbook[message.id]}
        className="cc-btn-ghost"
        style={{ ...actionBtnStyle, opacity: exportingWorkbook[message.id] ? 0.5 : 1 }}
      >
        {exportingWorkbook[message.id] ? (
          <Loader2 size={13} strokeWidth={2.5} className="animate-spin" />
        ) : (
          <Sheet size={13} strokeWidth={2} />
        )}
      </button>

      {/* Export Style Selector */}
      <div style={{ position: 'relative' }} ref={styleSelectorRef}>
        <button
          onClick={() => setShowStyleSelector(!showStyleSelector)}
          title="Select export style"
          className="cc-btn-ghost"
          style={actionBtnStyle}
        >
          <Pencil size={13} strokeWidth={2} />
        </button>

        {showStyleSelector && (
          <div style={{
            position: 'absolute',
            left: 0,
            bottom: '100%',
            marginBottom: 4,
            width: 240,
            backgroundColor: 'hsl(var(--cc-bg-000))',
            border: '0.5px solid hsl(var(--cc-border-200) / 30%)',
            borderRadius: 'var(--cc-radius-2xl)',
            boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
            zIndex: 50,
            maxHeight: 320,
            overflowY: 'auto',
          }}>
            <div style={{
              padding: '0.5rem 0.75rem',
              borderBottom: '1px solid hsl(var(--cc-border-300) / 10%)',
            }}>
              <div style={{
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.688rem',
                fontWeight: 500,
                color: 'hsl(var(--cc-text-200))',
              }}>Export Style</div>
              <div style={{
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.625rem',
                color: 'hsl(var(--cc-text-500))',
                marginTop: 2,
              }}>
                Choose a custom style for PDF/PowerPoint exports
              </div>
            </div>
            <div style={{ padding: '0.25rem' }}>
              {availableStyles.length === 0 ? (
                <div style={{
                  padding: '0.5rem 0.75rem',
                  fontFamily: 'var(--cc-font-ui)',
                  fontSize: '0.688rem',
                  color: 'hsl(var(--cc-text-500))',
                  textAlign: 'center',
                }}>
                  No custom styles available
                </div>
              ) : (
                availableStyles.map((style) => (
                  <button
                    key={style.style_name}
                    onClick={() => {
                      setSelectedStyleName(style.style_name);
                      setShowStyleSelector(false);
                    }}
                    className="cc-btn-ghost"
                    style={{
                      width: '100%',
                      padding: '0.375rem 0.5rem',
                      textAlign: 'left',
                      fontFamily: 'var(--cc-font-ui)',
                      fontSize: '0.688rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: 'transparent',
                      border: 'none',
                      borderRadius: 'var(--cc-radius-lg)',
                      cursor: 'pointer',
                      color: 'hsl(var(--cc-text-200))',
                    }}
                  >
                    <span style={{ fontWeight: 500 }}>
                      {style.style_name}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      {selectedStyleName === style.style_name && (
                        <CheckCircle2 size={14} style={{ color: 'hsl(var(--cc-accent-main-000))' }} />
                      )}
                      {style.is_default && (
                        <span style={{ fontSize: '0.625rem', color: 'hsl(var(--cc-text-500))' }}>(default)</span>
                      )}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
