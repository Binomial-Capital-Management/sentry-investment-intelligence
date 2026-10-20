import { useState, useEffect } from 'react';
import { X, FileSpreadsheet, AlertCircle, CheckCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/services/api';
import { ExcelPreviewModal, type TableSelections } from '@/components/KnowledgeGraph';
import { FileUploader } from '@/components/KnowledgeGraph';

interface PortfolioImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type Step = 'upload' | 'select' | 'confirm';

export const PortfolioImportModal = ({ isOpen, onClose, onSuccess }: PortfolioImportModalProps) => {
  const [step, setStep] = useState<Step>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [rawData, setRawData] = useState<unknown[][]>([]);
  const [selections, setSelections] = useState<TableSelections | null>(null);
  const [portfolioName, setPortfolioName] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setStep('upload');
      setFile(null);
      setRawData([]);
      setSelections(null);
      setPortfolioName('');
      setWarnings([]);
    }
  }, [isOpen]);

  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile);
    setPortfolioName(selectedFile.name.replace(/\.[^/.]+$/, '')); // Remove extension
    setStep('select');
  };

  const handleSelectionComplete = (userSelections: TableSelections) => {
    setSelections(userSelections);
    setStep('confirm');
  };

  const handleRawDataChange = (data: unknown[][]) => {
    setRawData(data);
  };

  const extractPortfolioData = () => {
    if (!selections || !rawData) {
      throw new Error('No selections or data available');
    }

    // Extract header cells to identify ticker and weight columns
    const headerCellsArray = Array.from(selections.headerCells);
    const dataRegion = selections.dataRegion;

    if (!dataRegion) {
      throw new Error('No data region selected');
    }

    // Find ticker column (assume first header cell column or identifier column)
    const tickerColumnIndex = selections.identifierCells.size > 0
      ? parseInt(Array.from(selections.identifierCells)[0].split(',')[1])
      : parseInt(headerCellsArray[0]?.split(',')[1] || '0');

    // Find weight column (look for numeric columns in header)
    // For now, assume second column or null for equal weighting
    const weightColumnIndex = headerCellsArray.length > 1
      ? parseInt(headerCellsArray[1].split(',')[1])
      : null;

    return {
      tickerColumnIndex,
      weightColumnIndex,
      skipHeaderRows: dataRegion.startRow,
    };
  };

  const handleImport = async () => {
    if (!portfolioName.trim()) {
      toast.error('Please enter a portfolio name');
      return;
    }

    setIsImporting(true);
    setWarnings([]);

    try {
      const { tickerColumnIndex, weightColumnIndex, skipHeaderRows } = extractPortfolioData();

      const response = await api.post('/api/portfolios/import', {
        name: portfolioName.trim(),
        file_data: rawData,
        ticker_column_index: tickerColumnIndex,
        weight_column_index: weightColumnIndex,
        skip_header_rows: skipHeaderRows,
      });

      if (response.data.warnings && response.data.warnings.length > 0) {
        setWarnings(response.data.warnings);
        toast.success(
          `Portfolio "${portfolioName}" created with ${response.data.tickers_imported} tickers (${response.data.warnings.length} warnings)`,
        );
      } else {
        toast.success(`Portfolio "${portfolioName}" created with ${response.data.tickers_imported} tickers`);
      }

      onSuccess();

      // Close after showing warnings
      if (response.data.warnings && response.data.warnings.length > 0) {
        setTimeout(() => onClose(), 3000);
      } else {
        onClose();
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      const errorMsg = err.response?.data?.detail || 'Failed to import portfolio';
      toast.error(errorMsg);
    } finally {
      setIsImporting(false);
    }
  };

  if (!isOpen) return null;

  // Step 1: File upload
  if (step === 'upload') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="text-[#002447]" size={24} />
              <h2 className="text-xl font-semibold text-[#1F2937]">
                Import Portfolio from CSV/Excel
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          <div className="p-6">
            <FileUploader onFileSelect={handleFileSelect} />
            <p className="mt-4 text-sm text-gray-600">
              Upload a CSV or Excel file containing your portfolio holdings.
              The next step will let you select which columns contain ticker symbols and weights.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Step 2: Cell selection with ExcelPreviewModal
  if (step === 'select') {
    return (
      <ExcelPreviewModal
        file={file}
        isOpen={true}
        onClose={() => setStep('upload')}
        onStartParsing={handleSelectionComplete}
        onRawDataChange={handleRawDataChange}
      />
    );
  }

  // Step 3: Confirmation and naming
  if (step === 'confirm') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="text-green-600" size={24} />
              <h2 className="text-xl font-semibold text-[#1F2937]">Confirm Portfolio Import</h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              disabled={isImporting}
            >
              <X size={20} />
            </button>
          </div>

          <div className="p-6 space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Portfolio Name
              </label>
              <input
                type="text"
                value={portfolioName}
                onChange={(e) => setPortfolioName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-[#002447]"
                placeholder="My Portfolio"
                disabled={isImporting}
              />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-blue-900 mb-2">Selected Data</h3>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• Header cells: {selections?.headerCells.size || 0}</li>
                <li>• Identifier cells: {selections?.identifierCells.size || 0}</li>
                <li>
                  • Data region: Rows {selections?.dataRegion?.startRow} - {selections?.dataRegion?.endRow}, Columns{' '}
                  {selections?.dataRegion?.startCol} - {selections?.dataRegion?.endCol}
                </li>
              </ul>
            </div>

            {warnings.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <AlertCircle className="text-yellow-600 flex-shrink-0 mt-0.5" size={16} />
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-yellow-800 mb-1">Import Warnings</h4>
                    <ul className="text-xs text-yellow-700 space-y-0.5 max-h-32 overflow-y-auto">
                      {warnings.map((warning, idx) => (
                        <li key={idx}>• {warning}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50">
            <button
              onClick={() => setStep('select')}
              disabled={isImporting}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors disabled:opacity-50"
            >
              ← Back to Selection
            </button>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                disabled={isImporting}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleImport}
                disabled={!portfolioName.trim() || isImporting}
                className="px-4 py-2 text-sm font-medium text-white bg-[#002447] hover:bg-[#001a33] rounded-md
                  transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isImporting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Importing...
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={16} />
                    Import Portfolio
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
};
