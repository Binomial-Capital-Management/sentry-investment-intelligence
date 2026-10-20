import { Download, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import { dataToCSV, downloadCSV, copyToClipboard, formatAsTable } from '@utils/export';
import toast from 'react-hot-toast';

interface ExportButtonsProps {
  data: any[];
  headers?: string[];
  filename?: string;
  className?: string;
}

export default function ExportButtons({
  data,
  headers,
  filename = 'export',
  className = '',
}: ExportButtonsProps) {
  const [copied, setCopied] = useState(false);

  const handleExportCSV = () => {
    try {
      const csv = dataToCSV(data, headers);
      const timestamp = new Date().toISOString().split('T')[0];
      downloadCSV(`${filename}_${timestamp}.csv`, csv);
      toast.success('Data exported successfully');
    } catch (error) {
      toast.error('Failed to export data');
    }
  };

  const handleCopy = async () => {
    try {
      const tableData = formatAsTable(data, headers);
      const success = await copyToClipboard(tableData);

      if (success) {
        setCopied(true);
        toast.success('Copied to clipboard');
        setTimeout(() => setCopied(false), 2000);
      } else {
        toast.error('Failed to copy to clipboard');
      }
    } catch (error) {
      toast.error('Failed to copy to clipboard');
    }
  };

  if (!data || data.length === 0) return null;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <button
        onClick={handleExportCSV}
        className="flex items-center gap-2 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors text-sm"
        title="Export as CSV"
      >
        <Download className="w-4 h-4" />
        <span>Export</span>
      </button>

      <button
        onClick={handleCopy}
        className="flex items-center gap-2 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors text-sm"
        title="Copy to clipboard"
      >
        {copied ? (
          <Check className="w-4 h-4 text-green-400" />
        ) : (
          <Copy className="w-4 h-4" />
        )}
        <span>{copied ? 'Copied' : 'Copy'}</span>
      </button>
    </div>
  );
}

// Simple copy button for text content
interface CopyButtonProps {
  text: string;
  className?: string;
  label?: string;
}

export function CopyButton({ text, className = '', label = 'Copy' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`inline-flex items-center gap-1 px-2 py-1 text-xs bg-white/10 hover:bg-white/20 text-white rounded transition-colors ${className}`}
      title="Copy to clipboard"
    >
      {copied ? (
        <>
          <Check className="w-3 h-3 text-green-400" />
          <span>Copied</span>
        </>
      ) : (
        <>
          <Copy className="w-3 h-3" />
          <span>{label}</span>
        </>
      )}
    </button>
  );
}
