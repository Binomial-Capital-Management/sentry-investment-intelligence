import { useState, useEffect, useRef, useCallback } from 'react';
import { chatAPI, API_BASE } from '@/services/api';
import { copyMessageContent } from '@/utils/export';
import type { SavedProcess, Message } from '../types';

interface UseMessageExportOptions {
  process: SavedProcess | null;
  currentThreadId: string | null;
  getToken: () => Promise<string | null>;
  isLoaded: boolean;
}

interface ExportStyle {
  style_name: string;
  is_default: boolean;
}

interface UseMessageExportReturn {
  copyFeedback: Record<string, boolean>;
  exportingPdf: Record<string, boolean>;
  exportingPpt: Record<string, boolean>;
  exportingWorkbook: Record<string, boolean>;
  showStyleSelector: boolean;
  availableStyles: ExportStyle[];
  selectedStyleName: string | null;
  styleSelectorRef: React.RefObject<HTMLDivElement>;
  setShowStyleSelector: (show: boolean) => void;
  setSelectedStyleName: (name: string | null) => void;
  handleCopy: (message: Message) => Promise<void>;
  handlePDFExport: (message: Message) => Promise<void>;
  handlePPTExport: (message: Message) => Promise<void>;
  handleWorkbookExport: (message: Message) => Promise<void>;
}

export function useMessageExport({
  process,
  currentThreadId,
  getToken,
  isLoaded,
}: UseMessageExportOptions): UseMessageExportReturn {
  const [copyFeedback, setCopyFeedback] = useState<Record<string, boolean>>({});
  const [exportingPdf, setExportingPdf] = useState<Record<string, boolean>>({});
  const [exportingPpt, setExportingPpt] = useState<Record<string, boolean>>({});
  const [exportingWorkbook, setExportingWorkbook] = useState<Record<string, boolean>>({});
  const [showStyleSelector, setShowStyleSelector] = useState(false);
  const [availableStyles, setAvailableStyles] = useState<ExportStyle[]>([]);
  const [selectedStyleName, setSelectedStyleName] = useState<string | null>(null);
  const styleSelectorRef = useRef<HTMLDivElement>(null);

  // Load export styles when auth is ready
  useEffect(() => {
    if (!isLoaded) return;
    const loadStyles = async () => {
      try {
        const token = await getToken();
        const response = await fetch(`${API_BASE}/api/user-settings/export-styles`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await response.json();
        setAvailableStyles(data.styles || []);
        const defaultStyle = data.styles?.find((s: any) => s.is_default);
        if (defaultStyle) {
          setSelectedStyleName(defaultStyle.style_name);
        }
      } catch (error) {
        console.error('Failed to load export styles:', error);
      }
    };
    loadStyles();
  }, [isLoaded, getToken]);

  // Handle clicks outside style selector dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (styleSelectorRef.current && !styleSelectorRef.current.contains(event.target as Node)) {
        setShowStyleSelector(false);
      }
    };
    if (showStyleSelector) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showStyleSelector]);

  const handleCopy = useCallback(async (message: Message) => {
    const messageDiv = document.createElement('div');
    messageDiv.innerHTML = message.content;
    const success = await copyMessageContent(messageDiv);
    if (success) {
      setCopyFeedback(prev => ({ ...prev, [message.id]: true }));
      setTimeout(() => setCopyFeedback(prev => ({ ...prev, [message.id]: false })), 2000);
    }
  }, []);

  const handlePDFExport = useCallback(async (message: Message) => {
    if (exportingPdf[message.id]) return;

    try {
      setExportingPdf(prev => ({ ...prev, [message.id]: true }));
      const payload = {
        mode: 'canvas',
        content: message.content,
        metadata: {
          process_id: process?.id,
          tool_id: process?.tool_id,
          tickers: process?.tickers,
          thread_id: currentThreadId,
        },
      };

      const blob = await chatAPI.exportPdf(payload, 'gamma_pdf', selectedStyleName || undefined);

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `canvas_${process?.tool_id || 'analysis'}_${new Date().toISOString().split('T')[0]}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Gamma PDF export failed:', error);
    } finally {
      setExportingPdf(prev => ({ ...prev, [message.id]: false }));
    }
  }, [exportingPdf, process, currentThreadId, selectedStyleName]);

  const handlePPTExport = useCallback(async (message: Message) => {
    if (exportingPpt[message.id]) return;

    try {
      setExportingPpt(prev => ({ ...prev, [message.id]: true }));
      const payload = {
        mode: 'canvas',
        content: message.content,
        metadata: {
          process_id: process?.id,
          tool_id: process?.tool_id,
          tickers: process?.tickers,
          thread_id: currentThreadId,
        },
      };

      const blob = await chatAPI.exportPowerpoint(payload, 'gamma_pptx', selectedStyleName || undefined);

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `canvas_${process?.tool_id || 'analysis'}_${new Date().toISOString().split('T')[0]}.pptx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('PowerPoint export failed:', error);
    } finally {
      setExportingPpt(prev => ({ ...prev, [message.id]: false }));
    }
  }, [exportingPpt, process, currentThreadId, selectedStyleName]);

  const handleWorkbookExport = useCallback(async (message: Message) => {
    if (exportingWorkbook[message.id]) return;

    try {
      setExportingWorkbook(prev => ({ ...prev, [message.id]: true }));
      const payload = {
        message_id: message.id,
        content: message.content,
        metadata: {
          process_id: process?.id,
          tool_id: process?.tool_id,
          tickers: process?.tickers,
          thread_id: currentThreadId,
        },
      };

      const blob = await chatAPI.exportWorkbook(payload);

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `canvas_workbooks_${message.id.substring(0, 8)}_${new Date().toISOString().split('T')[0]}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Workbook export failed:', error);
    } finally {
      setExportingWorkbook(prev => ({ ...prev, [message.id]: false }));
    }
  }, [exportingWorkbook, process, currentThreadId]);

  return {
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
    handleCopy,
    handlePDFExport,
    handlePPTExport,
    handleWorkbookExport,
  };
}
