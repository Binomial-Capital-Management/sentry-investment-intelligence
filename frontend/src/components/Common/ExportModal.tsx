import React, { useState } from 'react';
import { chatAPI } from '@services/api';
import Modal from './Modal';

interface ExportModalProps {
  open: boolean;
  onClose: () => void;
  context?: {
    messageId?: string;
    hasSources?: boolean;
    hasCharts?: boolean;
    charts?: any[];  // Actual chart data for export
    sources?: any[];  // Actual sources for export
  };
}

const ExportModal: React.FC<ExportModalProps> = ({ open, onClose, context }) => {
  const [isExporting, setIsExporting] = useState(false);
  const [exportingType, setExportingType] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [selectedTier, setSelectedTier] = useState<'free' | 'gamma_pdf' | 'gamma_pptx'>('free');

  const download = async (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportChat = async () => {
    setIsExporting(true);
    setExportingType('chat');
    setStatusMessage('Generating professional report...');

    try {
      const payload: any = { mode: 'chat' };
      if (context?.messageId) payload.message_id = context.messageId;

      // Simulate progress updates (since we can't get real progress from backend)
      setTimeout(() => setStatusMessage('Formatting content with AI...'), 1000);
      setTimeout(() => setStatusMessage('Creating document...'), 2000);

      const blob = await chatAPI.exportPdf(payload, selectedTier);
      const extension = selectedTier === 'gamma_pptx' ? 'pptx' : 'pdf';
      await download(blob, `chat_export.${extension}`);
      onClose();
    } catch (error) {
      setStatusMessage('Export failed. Please try again.');
      setTimeout(() => {
        setIsExporting(false);
        setStatusMessage('');
      }, 2000);
    }
  };

  const exportTemplate = async (template: string) => {
    setIsExporting(true);
    setExportingType(template);
    setStatusMessage('Generating professional report...');

    try {
      const payload: any = { mode: 'analysis', template, include: { charts: !!context?.hasCharts, sources: !!context?.hasSources } };

      // Simulate progress updates
      setTimeout(() => setStatusMessage('Analyzing data with AI...'), 1000);
      setTimeout(() => setStatusMessage('Creating document...'), 2000);

      const blob = await chatAPI.exportPdf(payload, selectedTier);
      const extension = selectedTier === 'gamma_pptx' ? 'pptx' : 'pdf';
      await download(blob, `${template}_report.${extension}`);
      onClose();
    } catch (error) {
      setStatusMessage('Export failed. Please try again.');
      setTimeout(() => {
        setIsExporting(false);
        setStatusMessage('');
      }, 2000);
    }
  };

  return (
    <Modal title="Export Report" open={open} onClose={!isExporting ? onClose : () => {}}>
      <div className="space-y-4">
        {isExporting ? (
          // Loading state
          <div className="py-8 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 mb-4">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
            <div className="text-lg font-medium mb-2">Generating Report</div>
            <div className="text-sm text-gray-600">{statusMessage}</div>
            <div className="text-xs text-gray-400 mt-4">
              Using AI to create professional institutional-grade PDF
            </div>
          </div>
        ) : (
          // Normal state
          <>
            {/* Export Tier Selector */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-700">Export Format</div>
              <div className="flex gap-2">
                <button
                  className={`flex-1 px-3 py-2 rounded-lg border text-left transition-colors ${
                    selectedTier === 'free' ? 'border-blue-500 bg-blue-50' : 'hover:border-blue-300'
                  }`}
                  onClick={() => setSelectedTier('free')}
                >
                  <div className="font-medium text-sm">Free PDF</div>
                  <div className="text-xs text-gray-500">Institutional-style report (Playwright)</div>
                </button>
                <button
                  className={`flex-1 px-3 py-2 rounded-lg border text-left transition-colors ${
                    selectedTier === 'gamma_pdf' ? 'border-purple-500 bg-purple-50' : 'hover:border-purple-300'
                  }`}
                  onClick={() => setSelectedTier('gamma_pdf')}
                >
                  <div className="font-medium text-sm flex items-center gap-1">
                    <span>Premium PDF</span>
                    <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">PRO</span>
                  </div>
                  <div className="text-xs text-gray-500">Gamma presentation (PDF)</div>
                </button>
                <button
                  className={`flex-1 px-3 py-2 rounded-lg border text-left transition-colors ${
                    selectedTier === 'gamma_pptx' ? 'border-orange-500 bg-orange-50' : 'hover:border-orange-300'
                  }`}
                  onClick={() => setSelectedTier('gamma_pptx')}
                >
                  <div className="font-medium text-sm flex items-center gap-1">
                    <span>Premium PPTX</span>
                    <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">PRO</span>
                  </div>
                  <div className="text-xs text-gray-500">Editable PowerPoint</div>
                </button>
              </div>
            </div>

            <div className="border-t pt-3">
              <div className="text-sm text-gray-600 mb-3">Choose a report template. AI will format your content professionally.</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button
                className="px-3 py-2 rounded-lg border hover:border-blue-500 text-left transition-colors"
                onClick={exportChat}
                disabled={isExporting}
              >
                <div className="font-medium">Chat Export</div>
                <div className="text-xs text-gray-500">Export this answer as {selectedTier === 'gamma_pptx' ? 'PPTX' : 'PDF'}</div>
              </button>
              <button
                className="px-3 py-2 rounded-lg border hover:border-blue-500 text-left transition-colors"
                onClick={() => exportTemplate('var')}
                disabled={isExporting}
              >
                <div className="font-medium">VaR Report</div>
                <div className="text-xs text-gray-500">95%/99% VaR, CVaR, assumptions</div>
              </button>
              <button
                className="px-3 py-2 rounded-lg border hover:border-blue-500 text-left transition-colors"
                onClick={() => exportTemplate('montecarlo')}
                disabled={isExporting}
              >
                <div className="font-medium">Monte Carlo</div>
                <div className="text-xs text-gray-500">Sim paths, bands, histograms</div>
              </button>
              <button
                className="px-3 py-2 rounded-lg border hover:border-blue-500 text-left transition-colors"
                onClick={() => exportTemplate('efficient_frontier')}
                disabled={isExporting}
              >
                <div className="font-medium">Efficient Frontier</div>
                <div className="text-xs text-gray-500">Frontier + allocations</div>
              </button>
              <button
                className="px-3 py-2 rounded-lg border hover:border-blue-500 text-left transition-colors"
                onClick={() => exportTemplate('barra')}
                disabled={isExporting}
              >
                <div className="font-medium">Barra Factors</div>
                <div className="text-xs text-gray-500">Exposures and attribution</div>
              </button>
              <button
                className="px-3 py-2 rounded-lg border hover:border-blue-500 text-left transition-colors"
                onClick={() => exportTemplate('mixed')}
                disabled={isExporting}
              >
                <div className="font-medium">Mixed</div>
                <div className="text-xs text-gray-500">Combine sections</div>
              </button>
            </div>
            <div className="pt-2 border-t">
              <button
                className="px-3 py-2 rounded-lg border w-full hover:border-blue-500 text-left transition-colors"
                disabled={isExporting}
              >
                <div className="font-medium">Build Custom Report</div>
                <div className="text-xs text-gray-500">Pick metrics, charts, portfolio</div>
              </button>
            </div>
            <div className="text-xs text-gray-400">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-blue-500">ℹ️</span>
                <span>Reports use AI to create professional formatting (takes ~3 seconds)</span>
              </div>
              {context?.hasSources ? 'Sources available to include.' : 'No sources detected.'}
              {context?.hasCharts ? ' Charts available.' : ' No charts detected.'}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};

export default ExportModal;
