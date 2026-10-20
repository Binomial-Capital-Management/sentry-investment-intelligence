/**
 * FilingSearchModal - SEC filings browser
 * 
 * Main modal component that orchestrates filing search, preview, and management.
 * Sub-components are extracted into separate files for maintainability.
 */

import React, { useRef, useMemo } from 'react';
import toast from 'react-hot-toast';
import { useUIStore } from '@/stores/uiStore';
import memoryApiService from '@/services/memoryApi';

// Import from Filings module
import {
  Filing,
  FilingSource,
  Transcript,
  FilingFilters,
  InstitutionResult,
  useTickerSearch,
  useFilingsList,
  useFilingPreview,
  useDocumentSearch,
  useTranscriptsList,
  useTranscriptPreview,
  useInstitutionSearch,
  useInstitutionFilings,
  useHoldings,
  modalStyles,
  searchStyles,
  listStyles,
  previewStyles,
  buttonStyles,
  formatDate,
  groupFilings,
  MarkdownViewer,
} from '../../Filings';

// Import sub-components
import { SearchIcon, CloseIcon, FileIcon } from './icons';
import { EmptyState, LoadingSpinner } from './UIComponents';
import { TickerChip, TickerDropdown, InstitutionChip, InstitutionDropdown } from './SearchComponents';
import { FilingFiltersPanel } from './FilterPanel';
import { FilingSection, TranscriptSection } from './FilingSections';
import { PreviewHeader, TranscriptPreviewHeader } from './PreviewComponents';
import { TranscriptViewer } from './TranscriptViewer';
import { ExpandedPreviewModal, ExpandedTranscriptModal } from './ExpandedModals';

interface FilingSearchModalProps {
  sessionId: string;
  onClose: () => void;
  onAddSources: (sources: FilingSource[]) => Promise<void>;
}

const FilingSearchModal: React.FC<FilingSearchModalProps> = ({ sessionId, onClose, onAddSources }) => {
  // Hooks
  const ticker = useTickerSearch();
  const filingsList = useFilingsList();
  const transcriptsList = useTranscriptsList();
  const transcriptPreview = useTranscriptPreview();
  const preview = useFilingPreview();
  const docSearch = useDocumentSearch();
  const institutionSearch = useInstitutionSearch();
  const institutionFilings = useInstitutionFilings();
  const holdings = useHoldings();
  
  // Sidebar preview
  const openFilingInSidebar = useUIStore((s) => s.openFilingInSidebar);
  
  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const expandedIframeRef = useRef<HTMLIFrameElement>(null);
  const previewIframeRef = useRef<HTMLIFrameElement>(null);
  
  // State
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [isAdding, setIsAdding] = React.useState(false);
  const [previewType, setPreviewType] = React.useState<'filing' | 'transcript'>('filing');
  const [showFilters, setShowFilters] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState<'company' | '13f'>('company');
  const [thirteenFViewMode, setThirteenFViewMode] = React.useState<'holdings' | 'document'>('holdings');
  const [thirteenFDocContent, setThirteenFDocContent] = React.useState('');

  // Computed
  const groupedFilings = useMemo(() => groupFilings(filingsList.filings), [filingsList.filings]);

  // ==========================================================================
  // Handlers
  // ==========================================================================
  
  const handleTickerSelect = (t: typeof ticker.tickerResults[0]) => {
    ticker.selectTicker(t);
    filingsList.fetchFilings(t.symbol, filingsList.filters);
    transcriptsList.fetchTranscripts(t.symbol);
    preview.clearPreview();
    transcriptPreview.clearPreview();
    setPreviewType('filing');
  };

  const handleFilterChange = (newFilters: FilingFilters) => {
    filingsList.setFilters(newFilters);
    if (ticker.selectedTicker) {
      filingsList.fetchFilings(ticker.selectedTicker.symbol, newFilters);
    }
  };

  const handleClearTicker = () => {
    ticker.clearTicker();
    filingsList.setFilings([]);
    transcriptsList.setTranscripts([]);
    preview.clearPreview();
    transcriptPreview.clearPreview();
    setPreviewType('filing');
    searchInputRef.current?.focus();
  };

  const handlePreview = (filing: Filing) => {
    preview.loadPreview(filing);
    transcriptPreview.clearPreview();
    setPreviewType('filing');
  };

  const handleTranscriptPreview = (transcript: Transcript) => {
    transcriptPreview.loadTranscript(transcript);
    preview.clearPreview();
    setPreviewType('transcript');
  };

  const handleTabChange = (tab: 'company' | '13f') => {
    setActiveTab(tab);
  };

  const handleInstitutionSelect = (inst: InstitutionResult) => {
    institutionSearch.selectInstitution(inst);
    institutionFilings.fetchFilings(inst.cik);
  };

  const handleClearInstitution = () => {
    institutionSearch.clearInstitution();
    institutionFilings.clearFilings();
    holdings.clearHoldings();
  };

  const handleFilingSelect = (filing: typeof institutionFilings.filings[0]) => {
    if (!institutionSearch.selectedInstitution) return;
    institutionFilings.selectFiling(filing);
    setThirteenFViewMode('holdings');
    setThirteenFDocContent('');
    const filingDate = new Date(filing.date);
    const year = filingDate.getFullYear();
    const quarter = Math.ceil((filingDate.getMonth() + 1) / 3);
    holdings.fetchHoldings(institutionSearch.selectedInstitution.cik, year, quarter);
  };

  // Load 13F document from SEC link - properly parses the XML
  const load13FDocument = async (secLink: string) => {
    if (!secLink) return;
    setThirteenFDocContent('');
    try {
      const response = await fetch(`/api/filings/13f-document?link=${encodeURIComponent(secLink)}`);
      if (response.ok) {
        const html = await response.text();
        setThirteenFDocContent(html);
      } else {
        const fallbackResponse = await fetch(`/api/filings/preview?link=${encodeURIComponent(secLink)}`);
        if (fallbackResponse.ok) {
          const html = await fallbackResponse.text();
          setThirteenFDocContent(html);
        } else {
          throw new Error('Failed to load document');
        }
      }
    } catch (error) {
      console.error('13F document load error:', error);
      setThirteenFDocContent(`
        <div style="padding: 60px; text-align: center; font-family: -apple-system, sans-serif;">
          <p style="color: #666; margin-bottom: 16px;">Unable to load preview</p>
          <a href="${secLink}" target="_blank" rel="noopener" style="color: #2563eb; text-decoration: none;">Open in SEC EDGAR →</a>
        </div>
      `);
    }
  };

  const handleThirteenFViewModeChange = (mode: 'holdings' | 'document') => {
    setThirteenFViewMode(mode);
    if (mode === 'document' && holdings.secLink) {
      load13FDocument(holdings.secLink);
    }
  };
  
  React.useEffect(() => {
    if (thirteenFViewMode === 'document' && holdings.secLink) {
      load13FDocument(holdings.secLink);
    }
  }, [holdings.secLink]);

  // ==========================================================================
  // Add Handlers
  // ==========================================================================

  const handleAddSelected = async () => {
    const selected = filingsList.filings.filter(f => f.selected);
    if (selected.length === 0) return;
    
    setIsAdding(true);
    try {
      const sources: FilingSource[] = selected.map((filing, idx) => ({
        id: `${Date.now()}-${idx}`,
        title: `${ticker.selectedTicker?.symbol || ''} ${filing.type} - ${formatDate(filing.filingDate)}`,
        url: filing.link,
        snippet: `${filing.description} filed on ${formatDate(filing.filingDate)}`,
        domain: 'sec.gov',
        cik: filing.cik,
        accessionNumber: filing.accessionNumber,
        formType: filing.type,
        filingDate: filing.filingDate,
      }));
      await onAddSources(sources);
      toast.success(`Added ${selected.length} filing${selected.length > 1 ? 's' : ''}`);
      onClose();
    } catch {
      toast.error('Failed to add filings');
    } finally {
      setIsAdding(false);
    }
  };

  const handleAdd13F = async () => {
    if (!institutionSearch.selectedInstitution || !institutionFilings.selectedFiling) return;
    
    const filing = institutionFilings.selectedFiling;
    const quarter = Math.ceil((new Date(filing.date).getMonth() + 1) / 3);
    const year = new Date(filing.date).getFullYear();
    
    setIsAdding(true);
    try {
      await memoryApiService.pin13FFilingToMemory(sessionId, {
        title: `${institutionSearch.selectedInstitution.name} 13F-HR Q${quarter} ${year}`,
        institutionName: institutionSearch.selectedInstitution.name,
        cik: institutionSearch.selectedInstitution.cik,
        year,
        quarter,
        totalValue: holdings.totalValue,
        holdingsCount: holdings.holdings.length,
        holdings: holdings.holdings.map((h: any) => ({
          symbol: h.symbol,
          securityName: h.securityName,
          shares: h.shares,
          value: h.value,
          weight: h.weight,
        })),
        secLink: holdings.secLink,
      });
      toast.success('Added 13F filing');
      onClose();
    } catch (error) {
      console.error('Failed to add 13F filing:', error);
      toast.error('Failed to add 13F filing');
    } finally {
      setIsAdding(false);
    }
  };

  const handleAddTranscript = async () => {
    if (!transcriptPreview.previewTranscript || !ticker.selectedTicker) return;
    
    const transcript = transcriptPreview.previewTranscript;
    
    setIsAdding(true);
    try {
      await memoryApiService.pinTranscriptToMemory(sessionId, {
        ticker: ticker.selectedTicker.symbol,
        year: transcript.year,
        quarter: transcript.quarter,
        title: `${ticker.selectedTicker.symbol} Q${transcript.quarter} ${transcript.year} Earnings Call`,
      });
      toast.success('Added transcript');
      onClose();
    } catch (error) {
      console.error('Failed to add transcript:', error);
      toast.error('Failed to add transcript');
    } finally {
      setIsAdding(false);
    }
  };

  const handleExportPdf = async (filing: Filing) => {
    if (!ticker.selectedTicker) return;
    const year = filing.filingDate ? parseInt(filing.filingDate.substring(0, 4)) : undefined;
    try {
      await preview.exportPdf(ticker.selectedTicker.symbol, filing.type, year);
      toast.success('PDF downloaded successfully');
    } catch (error: any) {
      toast.error(error.message || 'Failed to export PDF');
    }
  };

  const handleCloseExpanded = () => {
    setIsExpanded(false);
    docSearch.reset();
  };

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <div style={modalStyles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={modalStyles.modal}>
        {/* Header with Tabs */}
        <div style={{ borderBottom: '1px solid #e5e5e5' }}>
          <div style={modalStyles.header}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
              {/* Tab Bar */}
              <div style={{ display: 'flex', gap: '4px', background: '#f0f0f0', borderRadius: '6px', padding: '3px' }}>
                <button
                  onClick={() => handleTabChange('company')}
                  style={{
                    padding: '6px 14px',
                    fontSize: '12px',
                    fontWeight: 500,
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: activeTab === 'company' ? '#fff' : 'transparent',
                    color: activeTab === 'company' ? '#333' : '#666',
                    boxShadow: activeTab === 'company' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                  }}
                >
                  Company Filings
                </button>
                <button
                  onClick={() => handleTabChange('13f')}
                  style={{
                    padding: '6px 14px',
                    fontSize: '12px',
                    fontWeight: 500,
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: activeTab === '13f' ? '#fff' : 'transparent',
                    color: activeTab === '13f' ? '#333' : '#666',
                    boxShadow: activeTab === '13f' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                  }}
                >
                  13F Holdings
                </button>
              </div>
              
              {/* Search - Company Tab */}
              {activeTab === 'company' && (
                <div style={{ ...searchStyles.wrap, flex: 1 }}>
                  <SearchIcon />
                  {ticker.selectedTicker && (
                    <TickerChip ticker={ticker.selectedTicker} onClear={handleClearTicker} />
                  )}
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={ticker.searchQuery}
                    onChange={(e) => ticker.setSearchQuery(e.target.value.toUpperCase())}
                    onFocus={() => ticker.tickerResults.length > 0 && !ticker.selectedTicker && ticker.setShowDropdown(true)}
                    placeholder="Search by ticker..."
                    style={searchStyles.input}
                    autoFocus
                  />
                  {ticker.showDropdown && ticker.tickerResults.length > 0 && !ticker.selectedTicker && (
                    <TickerDropdown results={ticker.tickerResults} onSelect={handleTickerSelect} />
                  )}
                </div>
              )}
              
              {/* Search - 13F Tab */}
              {activeTab === '13f' && (
                <div style={{ ...searchStyles.wrap, flex: 1, position: 'relative' }}>
                  <SearchIcon />
                  {institutionSearch.selectedInstitution && (
                    <InstitutionChip
                      institution={institutionSearch.selectedInstitution}
                      onClear={handleClearInstitution}
                    />
                  )}
                  <input
                    type="text"
                    value={institutionSearch.searchQuery}
                    onChange={(e) => institutionSearch.setSearchQuery(e.target.value)}
                    onFocus={() => institutionSearch.searchResults.length > 0 && !institutionSearch.selectedInstitution && institutionSearch.setShowDropdown(true)}
                    placeholder={institutionSearch.selectedInstitution ? '' : 'Search institutions...'}
                    style={searchStyles.input}
                    disabled={!!institutionSearch.selectedInstitution}
                  />
                  {institutionSearch.showDropdown && institutionSearch.searchResults.length > 0 && !institutionSearch.selectedInstitution && (
                    <InstitutionDropdown
                      results={institutionSearch.searchResults}
                      onSelect={handleInstitutionSelect}
                    />
                  )}
                </div>
              )}
            </div>
            <button onClick={onClose} style={buttonStyles.icon}>
              <CloseIcon size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          
          {/* Company Filings Tab */}
          {activeTab === 'company' && (
            <div style={listStyles.container}>
              {!ticker.selectedTicker ? (
                <EmptyState message="Search for a company" icon={<SearchIcon size={36} />} />
              ) : filingsList.isLoading && transcriptsList.isLoading ? (
                <LoadingSpinner />
              ) : (
                <>
                  <FilingFiltersPanel
                    filters={filingsList.filters}
                    onChange={handleFilterChange}
                    isOpen={showFilters}
                    onToggle={() => setShowFilters(!showFilters)}
                  />
                  {groupedFilings.mostRecent.length > 0 && (
                    <FilingSection
                      title="Most Recent"
                      filings={groupedFilings.mostRecent}
                      previewFiling={previewType === 'filing' ? preview.previewFiling : null}
                      onToggle={filingsList.toggleFiling}
                      onPreview={handlePreview}
                    />
                  )}
                  {groupedFilings.financials.length > 0 && (
                    <FilingSection
                      title="Financials (10-K & 10-Q)"
                      filings={groupedFilings.financials}
                      previewFiling={previewType === 'filing' ? preview.previewFiling : null}
                      onToggle={filingsList.toggleFiling}
                      onPreview={handlePreview}
                      showPeriod
                    />
                  )}
                  {groupedFilings.other.length > 0 && (
                    <FilingSection
                      title="Other Filings"
                      filings={groupedFilings.other}
                      previewFiling={previewType === 'filing' ? preview.previewFiling : null}
                      onToggle={filingsList.toggleFiling}
                      onPreview={handlePreview}
                      defaultExpanded={false}
                    />
                  )}
                  {transcriptsList.transcripts.length > 0 && (
                    <TranscriptSection
                      title="Earnings Calls"
                      transcripts={transcriptsList.transcripts}
                      previewTranscript={previewType === 'transcript' ? transcriptPreview.previewTranscript : null}
                      onToggle={transcriptsList.toggleTranscript}
                      onPreview={handleTranscriptPreview}
                      defaultExpanded={false}
                    />
                  )}
                </>
              )}
            </div>
          )}

          {/* 13F Holdings Tab */}
          {activeTab === '13f' && (
            <div style={listStyles.container}>
              {!institutionSearch.selectedInstitution ? (
                <EmptyState message="Search for an institution" icon={<SearchIcon size={36} />} />
              ) : institutionFilings.isLoading ? (
                <LoadingSpinner />
              ) : institutionFilings.filings.length === 0 ? (
                <EmptyState message="No filings found" icon={<FileIcon />} />
              ) : (
                <>
                  <div style={listStyles.sectionHeader}>
                    13F Filings ({institutionFilings.filings.length})
                  </div>
                  {institutionFilings.filings.map((filing, idx) => {
                    const isActive = institutionFilings.selectedFiling?.date === filing.date;
                    const quarter = Math.ceil((new Date(filing.date).getMonth() + 1) / 3);
                    const year = new Date(filing.date).getFullYear();
                    return (
                      <div
                        key={idx}
                        style={{
                          ...listStyles.row,
                          background: isActive ? '#f0f7ff' : 'transparent',
                          borderLeft: isActive ? '3px solid #1976d2' : '3px solid transparent',
                        }}
                        onClick={() => handleFilingSelect(filing)}
                        onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#fafafa'; }}
                        onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
                            Q{quarter} {year}
                          </div>
                          <div style={{ fontSize: '11px', color: '#888', marginTop: '2px' }}>
                            Filed: {formatDate(filing.filingDate)}
                          </div>
                        </div>
                        <span style={{ fontSize: '11px', color: '#999' }}>
                          {formatDate(filing.date)}
                        </span>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          )}

          {/* Preview Panel */}
          <div style={previewStyles.container}>
            {activeTab === '13f' ? (
              // 13F Tab Preview
              institutionFilings.selectedFiling ? (
                <ThirteenFPreview
                  selectedFiling={institutionFilings.selectedFiling}
                  holdings={holdings}
                  thirteenFViewMode={thirteenFViewMode}
                  thirteenFDocContent={thirteenFDocContent}
                  onViewModeChange={handleThirteenFViewModeChange}
                />
              ) : institutionSearch.selectedInstitution ? (
                <EmptyState message="Select a filing to view holdings" icon={<FileIcon />} />
              ) : (
                <EmptyState message="Search for an institution" icon={<FileIcon />} />
              )
            ) : previewType === 'transcript' && transcriptPreview.previewTranscript ? (
              // Transcript Preview
              <>
                <TranscriptPreviewHeader
                  transcript={transcriptPreview.previewTranscript}
                  onExpand={() => setIsExpanded(true)}
                />
                <div style={previewStyles.content}>
                  {transcriptPreview.isLoading ? (
                    <LoadingSpinner />
                  ) : transcriptPreview.transcriptContent ? (
                    <TranscriptViewer content={transcriptPreview.transcriptContent.content} />
                  ) : (
                    <EmptyState message="Failed to load transcript" icon={<FileIcon />} />
                  )}
                </div>
              </>
            ) : preview.previewFiling ? (
              // Filing Preview
              <>
                <PreviewHeader
                  filing={preview.previewFiling}
                  viewMode={preview.viewMode}
                  onViewModeChange={preview.setViewMode}
                  currentPage={preview.currentPage}
                  totalPages={preview.totalPages}
                  onPageChange={preview.setCurrentPage}
                  onExpand={() => setIsExpanded(true)}
                  onExportPdf={ticker.selectedTicker ? () => handleExportPdf(preview.previewFiling!) : undefined}
                  isExportingPdf={preview.isExportingPdf}
                />
                <div style={previewStyles.content}>
                  {preview.isLoading ? (
                    <LoadingSpinner />
                  ) : preview.viewMode === 'markdown' && preview.markdownContent ? (
                    <MarkdownViewer
                      content={preview.markdownContent}
                      pages={preview.markdownPages}
                      currentPage={preview.currentPage}
                      totalPages={preview.totalPages}
                      onPageChange={preview.setCurrentPage}
                    />
                  ) : (
                    <iframe
                      ref={previewIframeRef}
                      srcDoc={preview.previewContent}
                      sandbox="allow-same-origin allow-scripts"
                      style={{ width: '100%', height: '100%', border: 'none' }}
                      title="Preview"
                    />
                  )}
                </div>
              </>
            ) : (
              <EmptyState message="Select a filing to preview" icon={<FileIcon />} />
            )}
          </div>
        </div>

        {/* Footer */}
        <div style={modalStyles.footer}>
          {activeTab === 'company' ? (
            <CompanyTabFooter
              filingsList={filingsList}
              preview={preview}
              previewType={previewType}
              transcriptPreview={transcriptPreview}
              ticker={ticker}
              isAdding={isAdding}
              onAddSelected={handleAddSelected}
              onAddTranscript={handleAddTranscript}
              openFilingInSidebar={openFilingInSidebar}
              onClose={onClose}
            />
          ) : (
            <ThirteenFTabFooter
              institutionSearch={institutionSearch}
              institutionFilings={institutionFilings}
              holdings={holdings}
              isAdding={isAdding}
              onAdd13F={handleAdd13F}
              openFilingInSidebar={openFilingInSidebar}
              onClose={onClose}
            />
          )}
        </div>
      </div>

      {/* Expanded Modal - Filing */}
      {isExpanded && previewType === 'filing' && preview.previewFiling && (
        <ExpandedPreviewModal
          filing={preview.previewFiling}
          ticker={ticker.selectedTicker}
          viewMode={preview.viewMode}
          markdownContent={preview.markdownContent}
          markdownPages={preview.markdownPages}
          previewContent={preview.previewContent}
          currentPage={preview.currentPage}
          totalPages={preview.totalPages}
          onPageChange={preview.setCurrentPage}
          docSearch={docSearch}
          iframeRef={expandedIframeRef}
          onClose={handleCloseExpanded}
        />
      )}

      {/* Expanded Modal - Transcript */}
      {isExpanded && previewType === 'transcript' && transcriptPreview.transcriptContent && (
        <ExpandedTranscriptModal
          transcript={transcriptPreview.previewTranscript!}
          content={transcriptPreview.transcriptContent.content}
          ticker={ticker.selectedTicker}
          onClose={handleCloseExpanded}
        />
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

// =============================================================================
// Footer Components (extracted for readability)
// =============================================================================

const CompanyTabFooter: React.FC<{
  filingsList: ReturnType<typeof useFilingsList>;
  preview: ReturnType<typeof useFilingPreview>;
  previewType: 'filing' | 'transcript';
  transcriptPreview: ReturnType<typeof useTranscriptPreview>;
  ticker: ReturnType<typeof useTickerSearch>;
  isAdding: boolean;
  onAddSelected: () => void;
  onAddTranscript: () => void;
  openFilingInSidebar: any;
  onClose: () => void;
}> = ({
  filingsList,
  preview,
  previewType,
  transcriptPreview,
  ticker,
  isAdding,
  onAddSelected,
  onAddTranscript,
  openFilingInSidebar,
  onClose,
}) => (
  <>
    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
      <span style={{ fontSize: '13px', color: '#666' }}>{filingsList.selectedCount} selected</span>
      {filingsList.selectedCount > 0 && (
        <button onClick={filingsList.clearSelection} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', color: '#888' }}>
          Clear selection
        </button>
      )}
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      {preview.previewFiling && (
        <button 
          onClick={() => {
            openFilingInSidebar({
              id: `filing-${Date.now()}`,
              title: `${ticker.selectedTicker?.symbol || ''} ${preview.previewFiling?.type} - ${formatDate(preview.previewFiling?.filingDate || '')}`,
              url: preview.previewFiling?.link || '',
              formType: preview.previewFiling?.type,
              filingDate: preview.previewFiling?.filingDate,
              ticker: ticker.selectedTicker?.symbol,
              content: preview.previewContent,
            });
            onClose();
          }}
          style={{ 
            padding: '6px 10px', 
            background: 'transparent', 
            border: 'none', 
            fontSize: '12px', 
            color: '#6b7280',
            cursor: 'pointer',
            textDecoration: 'underline',
            textUnderlineOffset: '2px'
          }}
        >
          Open in sidebar
        </button>
      )}
      {previewType === 'transcript' && transcriptPreview.previewTranscript ? (
        <button onClick={onAddTranscript} disabled={isAdding} style={buttonStyles.primary(true)}>
          {isAdding ? 'Adding...' : 'Add Transcript'}
        </button>
      ) : (
        <button onClick={onAddSelected} disabled={filingsList.selectedCount === 0 || isAdding} style={buttonStyles.primary(filingsList.selectedCount > 0)}>
          {isAdding ? 'Adding...' : `Add ${filingsList.selectedCount} file${filingsList.selectedCount !== 1 ? 's' : ''}`}
        </button>
      )}
    </div>
  </>
);

const ThirteenFTabFooter: React.FC<{
  institutionSearch: ReturnType<typeof useInstitutionSearch>;
  institutionFilings: ReturnType<typeof useInstitutionFilings>;
  holdings: ReturnType<typeof useHoldings>;
  isAdding: boolean;
  onAdd13F: () => void;
  openFilingInSidebar: any;
  onClose: () => void;
}> = ({
  institutionSearch,
  institutionFilings,
  holdings,
  isAdding,
  onAdd13F,
  openFilingInSidebar,
  onClose,
}) => (
  <>
    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
      {institutionFilings.selectedFiling && (
        <span style={{ fontSize: '13px', color: '#666' }}>
          Q{Math.ceil((new Date(institutionFilings.selectedFiling.date).getMonth() + 1) / 3)} {new Date(institutionFilings.selectedFiling.date).getFullYear()} selected
        </span>
      )}
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      {holdings.secLink && (
        <button 
          onClick={() => {
            openFilingInSidebar({
              id: `13f-${Date.now()}`,
              title: `${institutionSearch.selectedInstitution?.name} 13F-HR ${institutionFilings.selectedFiling?.date ? `Q${Math.ceil((new Date(institutionFilings.selectedFiling.date).getMonth() + 1) / 3)} ${new Date(institutionFilings.selectedFiling.date).getFullYear()}` : ''}`,
              url: holdings.secLink,
              formType: '13F-HR',
              filingDate: institutionFilings.selectedFiling?.date,
              ticker: undefined,
            });
            onClose();
          }}
          style={{ 
            padding: '6px 10px', 
            background: 'transparent', 
            border: 'none', 
            fontSize: '12px', 
            color: '#6b7280',
            cursor: 'pointer',
            textDecoration: 'underline',
            textUnderlineOffset: '2px'
          }}
        >
          Open in sidebar
        </button>
      )}
      <button 
        onClick={onAdd13F} 
        disabled={!institutionFilings.selectedFiling || isAdding} 
        style={buttonStyles.primary(!!institutionFilings.selectedFiling)}
      >
        {isAdding ? 'Adding...' : 'Add 13F Filing'}
      </button>
    </div>
  </>
);

// =============================================================================
// 13F Preview Component
// =============================================================================

const ThirteenFPreview: React.FC<{
  selectedFiling: { date: string; filingDate: string };
  holdings: ReturnType<typeof useHoldings>;
  thirteenFViewMode: 'holdings' | 'document';
  thirteenFDocContent: string;
  onViewModeChange: (mode: 'holdings' | 'document') => void;
}> = ({ selectedFiling, holdings, thirteenFViewMode, thirteenFDocContent, onViewModeChange }) => (
  <>
    <div style={previewStyles.header}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
        <span style={{ padding: '3px 8px', background: '#e8f5e9', color: '#2e7d32', fontSize: '11px', fontWeight: 500, borderRadius: '4px' }}>13F</span>
        <span style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
          Q{Math.ceil((new Date(selectedFiling.date).getMonth() + 1) / 3)} {new Date(selectedFiling.date).getFullYear()}
        </span>
        <div style={{ display: 'flex', background: '#f0f0f0', borderRadius: '6px', padding: '2px', marginLeft: '12px' }}>
          <button
            onClick={() => onViewModeChange('holdings')}
            style={{
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 500,
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              background: thirteenFViewMode === 'holdings' ? '#fff' : 'transparent',
              color: thirteenFViewMode === 'holdings' ? '#333' : '#666',
              boxShadow: thirteenFViewMode === 'holdings' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            Holdings
          </button>
          <button
            onClick={() => onViewModeChange('document')}
            disabled={!holdings.secLink}
            style={{
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 500,
              border: 'none',
              borderRadius: '4px',
              cursor: holdings.secLink ? 'pointer' : 'not-allowed',
              background: thirteenFViewMode === 'document' ? '#fff' : 'transparent',
              color: thirteenFViewMode === 'document' ? '#333' : '#666',
              boxShadow: thirteenFViewMode === 'document' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
              opacity: holdings.secLink ? 1 : 0.5,
            }}
          >
            Document
          </button>
        </div>
        {thirteenFViewMode === 'holdings' && holdings.totalValue > 0 && (
          <span style={{ fontSize: '12px', color: '#666', marginLeft: 'auto' }}>
            Total: ${(holdings.totalValue / 1000000).toLocaleString()}M
          </span>
        )}
      </div>
      {holdings.secLink && (
        <a 
          href={holdings.secLink} 
          target="_blank" 
          rel="noopener noreferrer"
          style={{ fontSize: '11px', color: '#1976d2', textDecoration: 'none', marginLeft: '12px' }}
        >
          SEC →
        </a>
      )}
    </div>
    <div style={{ flex: 1, overflow: 'auto', padding: '0' }}>
      {thirteenFViewMode === 'holdings' ? (
        holdings.isLoading ? (
          <LoadingSpinner />
        ) : holdings.holdings.length === 0 ? (
          <EmptyState message="No holdings data" icon={<FileIcon />} />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: '#f8f9fa', position: 'sticky', top: 0 }}>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#555', borderBottom: '1px solid #e5e5e5' }}>Symbol</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#555', borderBottom: '1px solid #e5e5e5' }}>Security</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#555', borderBottom: '1px solid #e5e5e5' }}>Class</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: '#555', borderBottom: '1px solid #e5e5e5' }}>Shares</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: '#555', borderBottom: '1px solid #e5e5e5' }}>Value</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: '#555', borderBottom: '1px solid #e5e5e5' }}>Weight</th>
              </tr>
            </thead>
            <tbody>
              {holdings.holdings.map((h: any, idx: number) => (
                <tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 600, color: '#1976d2' }}>{h.symbol || '—'}</td>
                  <td style={{ padding: '10px 12px', color: '#555', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.securityName}</td>
                  <td style={{ padding: '10px 12px', color: '#888', fontSize: '11px' }}>{h.titleOfClass || '—'}</td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', color: '#333' }}>{h.shares.toLocaleString()}</td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', color: '#333' }}>${(h.value / 1000).toLocaleString()}K</td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', color: '#333' }}>{(h.weight * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : thirteenFDocContent ? (
        <iframe
          srcDoc={thirteenFDocContent}
          sandbox="allow-same-origin allow-scripts"
          style={{ width: '100%', height: '100%', border: 'none' }}
          title="13F Filing"
        />
      ) : (
        <LoadingSpinner />
      )}
    </div>
  </>
);

export default FilingSearchModal;
