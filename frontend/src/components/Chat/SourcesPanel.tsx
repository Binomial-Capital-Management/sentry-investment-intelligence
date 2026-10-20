/**
 * SourcesPanel - NotebookLM-style sources panel
 * 
 * Supports pinning:
 * - Files (PDF, Word, Excel, CSV)
 * - Datasets from Data Workspace
 * - Tables/Sheets from Data Workspace
 * - Charts from Data Workspace
 * - Portfolios
 * - Web sources (search)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import memoryApiService from '@/services/memoryApi';
import WebSearchModal from './WebSearchModal';
import FilingSearchModal, { type FilingSource } from './FilingSearchModal';
import { useUIStore } from '@/stores/uiStore';

// Professional SVG Icons
const Icons = {
  Plus: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  FileText: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Database: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <ellipse cx="12" cy="5" rx="9" ry="3" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Check: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Loader: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`}>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeOpacity="0.25"/>
      <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Search: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  Globe: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Zap: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Close: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Trash: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Table: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Chart: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M18 20V10M12 20V4M6 20v-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Briefcase: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="2" y="7" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M12 12v.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Sparkle: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M12 3l2.24 5.66L20 10l-5.76 1.34L12 17l-2.24-5.66L4 10l5.76-1.34L12 3z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Link: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  Building: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M9 9v.01M9 12v.01M9 15v.01M9 18v.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  PanelRight: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M15 3v18" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
};
import { uploadService } from '@/services/upload';
import { useDataWorkspaceStore, DatasetConfig } from '@/stores/dataWorkspaceStore';
import { useChatStore } from '@/stores/chatStore';
import type { MemoryNote } from '@/types/memory';
import toast from 'react-hot-toast';

interface SourcesPanelProps {
  sessionId: string;
  onClose?: () => void;
}

interface Source {
  id: string;
  type: 'file' | 'dataset' | 'table' | 'chart' | 'portfolio' | 'web' | 'note' | 'canvas_tool' | 'sec_filing';
  title: string;
  subtitle?: string;
  selected: boolean;
  data: any;
}

// Canvas process type (matches Canvas.tsx)
interface CanvasProcess {
  id: string;
  tool_id: string;
  tickers: string[];
  weights?: number[];
  metrics: Record<string, any>;
  metric_cards?: { id: string; label: string; value: string; type?: string; sentiment?: string }[];
  charts: Record<string, any>;
  stats_table?: { category: string; metric: string; value: string; pct?: string }[];
  name?: string;
  created_at?: string;
}

type AddMenuSection = 'main' | 'datasets' | 'portfolios' | 'ai-outputs' | 'canvas-tools';

const SourcesPanel: React.FC<SourcesPanelProps> = ({ sessionId, onClose }) => {
  const [sources, setSources] = useState<Source[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [addMenuSection, setAddMenuSection] = useState<AddMenuSection>('main');
  const [isUploading, setIsUploading] = useState(false);
  const [showWebSearchModal, setShowWebSearchModal] = useState(false);
  const [showFilingSearchModal, setShowFilingSearchModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addMenuRef = useRef<HTMLDivElement>(null);
  
  // Filing preview sidebar
  const openFilingInSidebar = useUIStore((s) => s.openFilingInSidebar);
  
  // Get data from Data Workspace
  const { tabs, datasets: globalDatasets, activeTabId } = useDataWorkspaceStore();
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0];
  
  // Get AI outputs from current thread
  const { threads, currentThreadId } = useChatStore();
  const currentThread = threads.find(t => t.id === currentThreadId);
  const aiOutputs = React.useMemo(() => {
    if (!currentThread?.messages) return [];
    // Get only assistant messages (AI outputs)
    return currentThread.messages
      .filter(m => m.role === 'assistant' && m.content && m.content.length > 50) // Filter meaningful outputs
      .slice(-10) // Last 10 AI outputs
      .reverse() // Most recent first
      .map((msg) => ({
        id: msg.id,
        preview: msg.content.slice(0, 150).replace(/[#*_`]/g, '') + '...', // Clean preview
        timestamp: msg.timestamp,
        fullContent: msg.content,
      }));
  }, [currentThread?.messages]);
  
  // Get all datasets - check multiple locations where they might be stored
  const availableDatasets = React.useMemo(() => {
    // First try: sheets in active tab
    if (activeTab?.sheets && activeTab.sheets.length > 0) {
      const sheetDatasets = activeTab.sheets.flatMap(s => s.datasets || []);
      if (sheetDatasets.length > 0) return sheetDatasets;
    }
    // Second try: legacy datasets on tab
    if (activeTab?.datasets && activeTab.datasets.length > 0) {
      return activeTab.datasets;
    }
    // Third try: global datasets from store
    if (globalDatasets && globalDatasets.length > 0) {
      return globalDatasets;
    }
    // Fourth try: all datasets from all tabs
    const allTabDatasets = tabs.flatMap(t => {
      const fromSheets = t.sheets?.flatMap(s => s.datasets || []) || [];
      const fromTab = t.datasets || [];
      return [...fromSheets, ...fromTab];
    });
    return allTabDatasets;
  }, [activeTab, globalDatasets, tabs]);

  // Portfolios
  const [portfolios, setPortfolios] = useState<{ id: string; name: string; holdings: number }[]>([]);
  
  // Canvas processes (tool outputs)
  const [canvasProcesses, setCanvasProcesses] = useState<CanvasProcess[]>([]);
  
  useEffect(() => {
    // Fetch portfolios
    const fetchPortfolios = async () => {
      try {
        const response = await fetch('/api/portfolios');
        if (response.ok) {
          const data = await response.json();
          setPortfolios(data?.map((p: any) => ({
            id: p.id,
            name: p.name,
            holdings: p.holdings?.length || p.tickers?.length || 0
          })) || []);
        }
      } catch (e) {
        console.warn('Could not fetch portfolios');
      }
    };
    fetchPortfolios();
    
    // Fetch canvas processes (tool outputs)
    const fetchCanvasProcesses = async () => {
      try {
        const response = await fetch('/api/canvas/processes');
        if (response.ok) {
          const data = await response.json();
          setCanvasProcesses(data?.processes || data || []);
        }
      } catch (e) {
        console.warn('Could not fetch canvas processes');
      }
    };
    fetchCanvasProcesses();
  }, []);

  // Load sources from memory notes
  const loadSources = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await memoryApiService.getNotes(sessionId);
      const notes = response.notes || [];
      const sourcesFromNotes: Source[] = notes.map(note => {
        const refType = note.reference_type;
        const metaSource = note.reference_metadata?.source;
        
        // Determine type - check metadata.source for canvas_tool / ai_output
        let type: Source['type'] = 'note';
        if (metaSource === 'canvas_tool') type = 'canvas_tool';
        else if (refType === 'dataset') type = 'dataset';
        else if (refType === 'file') type = 'file';
        else if (refType === 'table') type = 'table';
        else if (refType === 'chart') type = 'chart';
        else if (refType === 'portfolio') type = 'portfolio';
        else if (refType === 'sec_filing') type = 'sec_filing';
        else if (refType === 'web') type = 'web';
        
        // Safely extract title - ensure it's a string
        const metaTitle = note.reference_metadata?.title;
        const metaFilename = note.reference_metadata?.filename;
        const title = (typeof metaTitle === 'string' && metaTitle) 
          ? metaTitle 
          : (typeof metaFilename === 'string' && metaFilename)
            ? metaFilename
            : note.content.substring(0, 50);
        
        const subtitle = typeof note.reference_metadata?.subtitle === 'string' 
          ? note.reference_metadata.subtitle 
          : undefined;
        
        return {
          id: note.id,
          type,
          title,
          subtitle,
          selected: true,
          data: note,
        };
      });
      setSources(sourcesFromNotes);
    } catch (error) {
      console.error('Failed to load sources:', error);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  // Close add menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
        setAddMenuSection('main');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Toggle source selection
  const toggleSource = (id: string) => {
    setSources(prev => prev.map(s => 
      s.id === id ? { ...s, selected: !s.selected } : s
    ));
  };

  // Select/deselect all
  const toggleAll = () => {
    const allSelected = sources.every(s => s.selected);
    setSources(prev => prev.map(s => ({ ...s, selected: !allSelected })));
  };

  // Handle file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setShowAddMenu(false);
    setAddMenuSection('main');

    try {
      // uploadFiles returns an array
      const uploadResults = await uploadService.uploadFiles([file]);
      const uploadResult = uploadResults[0];
      // Let the backend auto-detect best extraction method (no override)
      await memoryApiService.pinFileToMemory(sessionId, uploadResult.id, {
        index: true
      });
      toast.success(`Added ${file.name}`);
      await loadSources();
    } catch (error) {
      console.error('Upload failed:', error);
      toast.error('Failed to add source');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Handle dataset pin
  const handlePinDataset = async (dataset: DatasetConfig) => {
    setShowAddMenu(false);
    setAddMenuSection('main');
    setIsUploading(true);

    try {
      await memoryApiService.createNote(sessionId, {
        content: `Dataset: ${dataset.symbol} - ${dataset.endpoint}\nFields: ${dataset.fields.join(', ')}`,
        reference_type: 'dataset',
        reference_metadata: {
          title: `${dataset.symbol} ${dataset.endpoint}`,
          subtitle: `${dataset.fields.length} fields`,
          dataset_id: dataset.id,
          symbol: dataset.symbol,
          endpoint: dataset.endpoint,
          fields: dataset.fields,
        }
      });
      toast.success(`Added ${dataset.symbol} dataset`);
      await loadSources();
    } catch (error) {
      console.error('Failed to pin dataset:', error);
      toast.error('Failed to add dataset');
    } finally {
      setIsUploading(false);
    }
  };

  // Handle portfolio pin
  const handlePinPortfolio = async (portfolio: { id: string; name: string; holdings: number }) => {
    setShowAddMenu(false);
    setAddMenuSection('main');
    setIsUploading(true);

    try {
      // Fetch portfolio details
      const response = await fetch(`/api/portfolios/${portfolio.id}`);
      const details = response.ok ? await response.json() : null;
      
      const holdingsCount = details?.holdings?.length || details?.tickers?.length || 0;
      const holdingsList = details?.holdings?.map((h: any) => h.ticker).join(', ') || details?.tickers?.join(', ') || '';
      
      await memoryApiService.createNote(sessionId, {
        content: `Portfolio: ${portfolio.name}\nHoldings: ${holdingsCount} positions\nTickers: ${holdingsList}`,
        reference_type: 'portfolio',
        reference_metadata: {
          title: portfolio.name,
          subtitle: `${portfolio.holdings} holdings`,
          portfolio_id: portfolio.id,
          holdings: details?.holdings,
        }
      });
      toast.success(`Added portfolio "${portfolio.name}"`);
      await loadSources();
    } catch (error) {
      console.error('Failed to pin portfolio:', error);
      toast.error('Failed to add portfolio');
    } finally {
      setIsUploading(false);
    }
  };

  // Handle adding web sources from the modal
  const handleAddWebSources = async (webSources: { id: number; title: string; url: string; snippet: string; domain: string }[]) => {
    for (const source of webSources) {
      await memoryApiService.createNote(sessionId, {
        content: `${source.title}\n\n${source.snippet}\n\nSource: ${source.url}`,
        reference_type: 'web',
        reference_metadata: {
          title: source.title,
          subtitle: source.domain,
          url: source.url,
          snippet: source.snippet,
        }
      });
    }
    await loadSources();
  };

  // Handle adding SEC filing sources from the modal - now with full indexing
  const handleAddFilingSources = async (filingSources: FilingSource[]) => {
    for (const source of filingSources) {
      try {
        // Use the new pinSECFilingToMemory which fetches, chunks, and indexes
        await memoryApiService.pinSECFilingToMemory(sessionId, {
          link: source.url,
          title: source.title,
          formType: source.formType,
          filingDate: source.filingDate,
          cik: source.cik,
          accessionNumber: source.accessionNumber,
          ticker: source.title?.split(' ')[0], // Extract ticker from title
        });
      } catch (error) {
        console.error('Failed to index SEC filing:', error);
        // Fallback to simple note if indexing fails
        await memoryApiService.createNote(sessionId, {
          content: `SEC Filing: ${source.title}\n\nForm: ${source.formType}\nFiled: ${source.filingDate}\nCIK: ${source.cik}\nAccession: ${source.accessionNumber}\n\n${source.snippet}\n\nSource: ${source.url}`,
          reference_type: 'web',
          reference_metadata: {
            title: source.title,
            subtitle: `SEC ${source.formType}`,
            url: source.url,
            snippet: source.snippet,
            source: 'sec_filing',
            cik: source.cik,
            accession_number: source.accessionNumber,
            form_type: source.formType,
            filing_date: source.filingDate,
          }
        });
      }
    }
    await loadSources();
  };

  // Handle pinning AI output as source
  const handlePinAIOutput = async (output: { id: string; preview: string; timestamp: Date; fullContent: string }) => {
    setShowAddMenu(false);
    setAddMenuSection('main');
    setIsUploading(true);

    try {
      // Create a meaningful title from the first line or heading
      const lines = output.fullContent.split('\n').filter(l => l.trim());
      let title = lines[0]?.replace(/^#+\s*/, '').replace(/\*\*/g, '').slice(0, 60) || 'AI Analysis';
      if (title.length >= 60) title += '...';
      
      await memoryApiService.createNote(sessionId, {
        content: output.fullContent,
        reference_type: 'text', // Tool outputs are stored as text type
        reference_metadata: {
          title: title,
          subtitle: `AI output from ${new Date(output.timestamp).toLocaleDateString()}`,
          source: 'ai_output',
          message_id: output.id,
        }
      });
      toast.success('Added AI output as source');
      await loadSources();
    } catch (error) {
      console.error('Failed to pin AI output:', error);
      toast.error('Failed to add AI output');
    } finally {
      setIsUploading(false);
    }
  };

  // Handle pinning Canvas tool output as source
  const handlePinCanvasProcess = async (process: CanvasProcess) => {
    setShowAddMenu(false);
    setAddMenuSection('main');
    setIsUploading(true);

    try {
      // Build a comprehensive content string from the process data
      const contentParts: string[] = [];
      
      // Title
      const processName = process.name || `${process.tool_id} Analysis`;
      contentParts.push(`# ${processName}`);
      contentParts.push(`**Tickers:** ${process.tickers.join(', ')}`);
      contentParts.push(`**Tool:** ${process.tool_id}`);
      contentParts.push('');
      
      // Metric cards (key metrics)
      if (process.metric_cards && process.metric_cards.length > 0) {
        contentParts.push('## Key Metrics');
        process.metric_cards.forEach(card => {
          contentParts.push(`- **${card.label}:** ${card.value}`);
        });
        contentParts.push('');
      }
      
      // Stats table
      if (process.stats_table && process.stats_table.length > 0) {
        contentParts.push('## Statistics');
        let currentCategory = '';
        process.stats_table.forEach(row => {
          if (row.category !== currentCategory) {
            currentCategory = row.category;
            contentParts.push(`\n### ${currentCategory}`);
          }
          const pctStr = row.pct ? ` (${row.pct})` : '';
          contentParts.push(`- ${row.metric}: ${row.value}${pctStr}`);
        });
        contentParts.push('');
      }
      
      // Core metrics (flattened)
      if (process.metrics && Object.keys(process.metrics).length > 0) {
        contentParts.push('## Detailed Metrics');
        const metricsToShow = Object.entries(process.metrics)
          .filter(([k, v]) => !k.startsWith('_') && v !== null && typeof v !== 'object')
          .slice(0, 20); // Limit to avoid huge content
        metricsToShow.forEach(([key, value]) => {
          const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          contentParts.push(`- **${formattedKey}:** ${value}`);
        });
      }
      
      const content = contentParts.join('\n');
      
      await memoryApiService.createNote(sessionId, {
        content,
        reference_type: 'text', // Store as text for full content
        reference_metadata: {
          title: processName,
          subtitle: `${process.tool_id} · ${process.tickers.length} ticker${process.tickers.length !== 1 ? 's' : ''}`,
          source: 'canvas_tool',
          process_id: process.id,
          tool_id: process.tool_id,
          tickers: process.tickers,
        }
      });
      toast.success(`Added "${processName}" as source`);
      await loadSources();
    } catch (error) {
      console.error('Failed to pin canvas process:', error);
      toast.error('Failed to add tool output');
    } finally {
      setIsUploading(false);
    }
  };

  // Delete source
  const handleDeleteSource = async (source: Source, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await memoryApiService.deleteNote(sessionId, source.id);
      toast.success('Source removed');
      await loadSources();
    } catch (error) {
      console.error('Failed to delete source:', error);
      toast.error('Failed to remove source');
    }
  };

  // Store selected sources in UI store
  const setSelectedSources = useUIStore((state) => state.setSelectedSources);
  const selectedIds = sources.filter(s => s.selected).map(s => s.id).join(',');
  
  useEffect(() => {
    const selectedSources = sources.filter(s => s.selected);
    const sourcesForStore = selectedSources.map(s => ({
      id: s.id,
      type: s.type,
      content: (s.data as MemoryNote)?.content || s.title,
      metadata: (s.data as MemoryNote)?.reference_metadata,
    }));
    setSelectedSources(sourcesForStore);
  }, [selectedIds, sources, setSelectedSources]);

  const getSourceIcon = (type: Source['type']) => {
    switch (type) {
      case 'file': return <Icons.FileText size={16} className="text-red-500" />;
      case 'dataset': return <Icons.Database size={16} className="text-blue-500" />;
      case 'table': return <Icons.Table size={16} className="text-green-500" />;
      case 'chart': return <Icons.Chart size={16} className="text-purple-500" />;
      case 'portfolio': return <Icons.Briefcase size={16} className="text-amber-500" />;
      case 'web': return <Icons.Link size={16} className="text-cyan-500" />;
      case 'canvas_tool': return <Icons.Chart size={16} className="text-emerald-500" />;
      case 'sec_filing': return <Icons.Building size={16} className="text-indigo-500" />;
      default: return <Icons.FileText size={16} className="text-gray-500" />;
    }
  };

  // Render add menu content based on section
  const renderAddMenuContent = () => {
    if (addMenuSection === 'datasets') {
      return (
        <div className="max-h-64 overflow-y-auto">
          <button
            onClick={() => setAddMenuSection('main')}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-blue-600 hover:bg-gray-50 border-b border-gray-100"
          >
            ← Back
          </button>
          {availableDatasets.length > 0 ? (
            availableDatasets.map((dataset: any) => (
              <button
                key={dataset.id}
                onClick={() => handlePinDataset(dataset)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left"
              >
                <Icons.Database size={16} className="text-blue-500" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">{dataset.symbol}</div>
                  <div className="text-xs text-gray-500 truncate">{dataset.endpoint} · {dataset.fields?.length || 0} fields</div>
                </div>
              </button>
            ))
          ) : (
            <div className="p-4 text-center text-sm text-gray-500">No datasets in workspace</div>
          )}
        </div>
      );
    }

    if (addMenuSection === 'portfolios') {
      return (
        <div className="max-h-64 overflow-y-auto">
          <button
            onClick={() => setAddMenuSection('main')}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-blue-600 hover:bg-gray-50 border-b border-gray-100"
          >
            ← Back
          </button>
          {portfolios.length > 0 ? (
            portfolios.map(portfolio => (
              <button
                key={portfolio.id}
                onClick={() => handlePinPortfolio(portfolio)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left"
              >
                <Icons.Briefcase size={16} className="text-amber-500" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">{portfolio.name}</div>
                  <div className="text-xs text-gray-500 truncate">{portfolio.holdings} holdings</div>
                </div>
              </button>
            ))
          ) : (
            <div className="p-4 text-center text-sm text-gray-500">No portfolios found</div>
          )}
        </div>
      );
    }

    // AI Outputs submenu (chat responses)
    if (addMenuSection === 'ai-outputs') {
      return (
        <div className="max-h-80 overflow-y-auto">
          <button
            onClick={() => setAddMenuSection('main')}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-blue-600 hover:bg-gray-50 border-b border-gray-100"
          >
            ← Back
          </button>
          {aiOutputs.length > 0 ? (
            aiOutputs.map(output => (
              <button
                key={output.id}
                onClick={() => handlePinAIOutput(output)}
                className="w-full flex items-start gap-3 px-4 py-3 hover:bg-gray-50 text-left border-b border-gray-100"
              >
                <Icons.Sparkle size={16} className="text-purple-500 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-800 line-clamp-2">{output.preview}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {new Date(output.timestamp).toLocaleString()}
                  </div>
                </div>
              </button>
            ))
          ) : (
            <div className="p-4 text-center text-sm text-gray-500">
              No AI outputs in this chat yet
            </div>
          )}
        </div>
      );
    }

    // Canvas Tool Outputs submenu (from Data Workspace/Canvas)
    if (addMenuSection === 'canvas-tools') {
      return (
        <div className="max-h-80 overflow-y-auto">
          <button
            onClick={() => setAddMenuSection('main')}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-blue-600 hover:bg-gray-50 border-b border-gray-100"
          >
            ← Back
          </button>
          {canvasProcesses.length > 0 ? (
            canvasProcesses.map(process => (
              <button
                key={process.id}
                onClick={() => handlePinCanvasProcess(process)}
                className="w-full flex items-start gap-3 px-4 py-3 hover:bg-gray-50 text-left border-b border-gray-100"
              >
                <Icons.Chart size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {process.name || `${process.tool_id} Analysis`}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {process.tickers.slice(0, 3).join(', ')}{process.tickers.length > 3 ? '...' : ''} · {process.tool_id}
                  </div>
                  {process.created_at && (
                    <div className="text-xs text-gray-400 mt-0.5">
                      {new Date(process.created_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </button>
            ))
          ) : (
            <div className="p-4 text-center text-sm text-gray-500">
              No tool outputs in Canvas yet. Run an analysis in the Data Workspace first.
            </div>
          )}
        </div>
      );
    }

    // Main menu
    return (
      <>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left"
        >
          <Icons.FileText size={18} className="text-red-500" />
          <div>
            <div className="text-sm font-medium text-gray-800">Upload file</div>
            <div className="text-xs text-gray-500">PDF, Word, Excel, CSV</div>
          </div>
        </button>
        <button
          onClick={() => setAddMenuSection('datasets')}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left border-t border-gray-100"
        >
          <Icons.Database size={18} className="text-blue-500" />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-800">Dataset</div>
            <div className="text-xs text-gray-500">From Data Workspace</div>
          </div>
          <span className="text-xs text-gray-400">{availableDatasets.length}</span>
        </button>
        <button
          onClick={() => setAddMenuSection('portfolios')}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left border-t border-gray-100"
        >
          <Icons.Briefcase size={18} className="text-amber-500" />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-800">Portfolio</div>
            <div className="text-xs text-gray-500">Your portfolios</div>
          </div>
          <span className="text-xs text-gray-400">{portfolios.length}</span>
        </button>
        <button
          onClick={() => setAddMenuSection('canvas-tools')}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left border-t border-gray-100"
        >
          <Icons.Chart size={18} className="text-emerald-500" />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-800">Canvas Tool Output</div>
            <div className="text-xs text-gray-500">Analysis results from Canvas</div>
          </div>
          <span className="text-xs text-gray-400">{canvasProcesses.length}</span>
        </button>
        <button
          onClick={() => setAddMenuSection('ai-outputs')}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left border-t border-gray-100"
        >
          <Icons.Sparkle size={18} className="text-purple-500" />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-800">Chat AI Output</div>
            <div className="text-xs text-gray-500">From this chat</div>
          </div>
          <span className="text-xs text-gray-400">{aiOutputs.length}</span>
        </button>
        <button
          onClick={() => {
            setShowAddMenu(false);
            setShowFilingSearchModal(true);
          }}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left border-t border-gray-100"
        >
          <Icons.Building size={18} className="text-indigo-500" />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-800">SEC Filings</div>
            <div className="text-xs text-gray-500">10-K, 10-Q, 8-K from EDGAR</div>
          </div>
        </button>
        <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
          <p className="text-xs text-gray-500">
            To pin tables or charts, use the "Pin to Sources" button in the Data Workspace.
          </p>
        </div>
      </>
    );
  };

  return (
    <div className="flex flex-col h-full bg-white" style={{ fontFamily: "'Google Sans', sans-serif" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <span className="font-medium text-gray-900 text-base">Sources</span>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <Icons.Close size={18} className="text-gray-500" />
          </button>
        )}
      </div>

      {/* Add Sources Button */}
      <div className="px-4 pt-4 pb-2" ref={addMenuRef}>
        <div className="relative">
          <button
            onClick={() => {
              setShowAddMenu(!showAddMenu);
              setAddMenuSection('main');
            }}
            disabled={isUploading}
            className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed border-gray-300 rounded-full text-sm text-gray-600 hover:border-gray-400 hover:bg-gray-50 transition-colors"
          >
            {isUploading ? (
              <Icons.Loader size={16} />
            ) : (
              <Icons.Plus size={16} />
            )}
            Add sources
          </button>

          {/* Add Menu Dropdown */}
          {showAddMenu && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-lg z-20 overflow-hidden">
              {renderAddMenuContent()}
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg"
          onChange={handleFileUpload}
          className="hidden"
        />
      </div>


      {/* Web Search Button */}
      <div className="px-4 py-2">
        <button
          onClick={() => setShowWebSearchModal(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
        >
          <Icons.Globe size={16} />
          Search the web
        </button>
      </div>

      {/* Select All */}
      {sources.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-100">
          <button
            onClick={toggleAll}
            className="flex items-center gap-2 text-sm text-gray-700"
          >
            <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
              sources.every(s => s.selected) 
                ? 'bg-blue-500 border-blue-500' 
                : 'border-gray-300'
            }`}>
              {sources.every(s => s.selected) && <Icons.Check size={10} className="text-white" />}
            </div>
            Select all sources
          </button>
        </div>
      )}

      {/* Sources List */}
      <div className="flex-1 overflow-y-auto px-2">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Icons.Loader size={24} className="text-gray-400" />
          </div>
        ) : sources.length > 0 ? (
          <div className="py-1">
            {sources.map(source => {
              // Check if this is an SEC filing (by type or metadata)
              const meta = source.data?.reference_metadata;
              const isSECFiling = source.type === 'sec_filing' || 
                meta?.form_type || 
                meta?.accession_number ||
                (meta?.url && meta.url.includes('sec.gov'));
              const hasPreviewUrl = meta?.url;
              
              return (
                <div
                  key={source.id}
                  onClick={() => toggleSource(source.id)}
                  className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer group border-b border-gray-100 last:border-b-0"
                >
                  {/* Checkbox - smaller, subtle */}
                  <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors flex-shrink-0 ${
                    source.selected 
                      ? 'bg-blue-500 border-blue-500' 
                      : 'border-gray-300 hover:border-gray-400'
                  }`}>
                    {source.selected && <Icons.Check size={10} className="text-white" />}
                  </div>

                  {/* Title and metadata */}
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] text-gray-800 truncate font-medium">{source.title}</div>
                    {source.subtitle && (
                      <div className="text-[11px] text-gray-400 truncate">{source.subtitle}</div>
                    )}
                  </div>

                  {/* View in Sidebar button - for SEC filings */}
                  {isSECFiling && hasPreviewUrl && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openFilingInSidebar({
                          id: source.id,
                          title: source.title,
                          url: meta.url,
                          formType: meta.form_type,
                          filingDate: meta.filing_date,
                          ticker: meta.ticker,
                        });
                      }}
                      className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-gray-100 rounded transition-all text-gray-400 hover:text-gray-600"
                      title="View in sidebar"
                    >
                      <Icons.PanelRight size={14} />
                    </button>
                  )}

                  {/* Delete button */}
                  <button
                    onClick={(e) => handleDeleteSource(source, e)}
                    className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-gray-100 rounded transition-all text-gray-400 hover:text-red-500"
                  >
                    <Icons.Trash size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full py-12 text-center">
            <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
              <Icons.Plus size={20} className="text-gray-400" />
            </div>
            <p className="text-sm text-gray-600 mb-1">No sources yet</p>
            <p className="text-xs text-gray-500">Add files or datasets to get started</p>
          </div>
        )}
      </div>

      {/* Web Search Modal */}
      {showWebSearchModal && (
        <WebSearchModal
          sessionId={sessionId}
          onClose={() => setShowWebSearchModal(false)}
          onAddSources={handleAddWebSources}
        />
      )}

      {/* SEC Filings Search Modal */}
      {showFilingSearchModal && (
        <FilingSearchModal
          sessionId={sessionId}
          onClose={() => setShowFilingSearchModal(false)}
          onAddSources={handleAddFilingSources}
        />
      )}
    </div>
  );
};

export default SourcesPanel;
