import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UIState } from '@/types';

// Studio artifact types
export interface StudioArtifact {
  id: string;
  type: 'mindmap' | 'report' | 'datatable' | 'slides';
  title: string;
  data: any;
  createdAt: Date;
  sourceCount: number;
}

// Source type for the Sources panel
export interface SelectedSource {
  id: string;
  type: 'file' | 'dataset' | 'table' | 'chart' | 'portfolio' | 'web' | 'note' | 'canvas_tool';
  content: string;
  metadata?: any;
}

// Filing preview for sidebar
export interface FilingPreview {
  id: string;
  title: string;
  url: string;
  formType?: string;
  filingDate?: string;
  ticker?: string;
  content?: string; // HTML content if already fetched
}

// Citation from a filing (highlighted text)
export interface FilingCitation {
  id: string;
  text: string; // The highlighted text
  filingId: string;
  filingTitle: string;
  formType?: string;
  ticker?: string;
  sectionHint?: string; // e.g., "Risk Factors", "MD&A"
}

interface UIStore extends UIState {
  analystMode: boolean;
  theme: 'dark' | 'light';
  compactMode: boolean;
  memoryPanelOpen: boolean;
  studioPanelOpen: boolean;
  filingPreviewOpen: boolean;
  filingPreviews: FilingPreview[];
  activeFilingPreviewId: string | null;
  filingCitations: FilingCitation[];
  studioArtifacts: StudioArtifact[];
  activeStudioArtifact: StudioArtifact | null;
  selectedSources: SelectedSource[];
  setLoading: (loading: boolean, message?: string) => void;
  setActiveModal: (modal: UIState['activeModal']) => void;
  setActiveTab: (tab: UIState['activeTab']) => void;
  setSidebarExpanded: (expanded: boolean) => void;
  setBackendVersion: (v: UIState['backendVersion']) => void;
  setHealthStatus: (s: UIState['healthStatus']) => void;
  toggleAnalystMode: () => void;
  toggleTheme: () => void;
  toggleCompactMode: () => void;
  toggleMemoryPanel: () => void;
  setMemoryPanelOpen: (open: boolean) => void;
  toggleStudioPanel: () => void;
  setStudioPanelOpen: (open: boolean) => void;
  setFilingPreviewOpen: (open: boolean) => void;
  openFilingInSidebar: (filing: FilingPreview) => void;
  closeFilingPreview: (id: string) => void;
  setActiveFilingPreview: (id: string) => void;
  addFilingCitation: (citation: FilingCitation) => void;
  removeFilingCitation: (id: string) => void;
  clearFilingCitations: () => void;
  addStudioArtifact: (artifact: StudioArtifact) => void;
  removeStudioArtifact: (id: string) => void;
  setActiveStudioArtifact: (artifact: StudioArtifact | null) => void;
  clearStudioArtifacts: () => void;
  setSelectedSources: (sources: SelectedSource[]) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      isLoading: false,
      loadingMessage: '',
      activeModal: null,
      activeTab: 'binomial',
      sidebarExpanded: false,
      backendVersion: 'unknown',
      healthStatus: 'healthy',
      analystMode: false,
      theme: 'light',
      compactMode: false,
      memoryPanelOpen: false,
      studioPanelOpen: false,
      filingPreviewOpen: false,
      filingPreviews: [],
      activeFilingPreviewId: null,
      filingCitations: [],
      studioArtifacts: [],
      activeStudioArtifact: null,
      selectedSources: [],

      setLoading: (loading, message = '') =>
        set({ isLoading: loading, loadingMessage: message }),

      setActiveModal: (modal) =>
        set({ activeModal: modal }),

      setActiveTab: (tab) =>
        set({ activeTab: tab }),

      setSidebarExpanded: (expanded) =>
        set({ sidebarExpanded: expanded }),

      setBackendVersion: (v) => set({ backendVersion: v }),
      setHealthStatus: (s) => set({ healthStatus: s }),
      toggleAnalystMode: () => set((state) => ({ analystMode: !state.analystMode })),
      toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
      toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
      toggleMemoryPanel: () => set((state) => ({ memoryPanelOpen: !state.memoryPanelOpen })),
      setMemoryPanelOpen: (open) => set({ memoryPanelOpen: open }),
      toggleStudioPanel: () => set((state) => ({ studioPanelOpen: !state.studioPanelOpen })),
      setStudioPanelOpen: (open) => set({ studioPanelOpen: open }),
      setFilingPreviewOpen: (open) => set((state) => ({ 
        filingPreviewOpen: open,
        // If closing, clear all tabs
        ...(open ? {} : { filingPreviews: [], activeFilingPreviewId: null })
      })),
      openFilingInSidebar: (filing) => set((state) => {
        // Check if already open
        const existing = state.filingPreviews.find(f => f.url === filing.url);
        if (existing) {
          return { activeFilingPreviewId: existing.id, filingPreviewOpen: true, memoryPanelOpen: false };
        }
        // Add new tab (strip content to avoid localStorage bloat)
        const filingWithoutContent = { ...filing, content: undefined };
        return { 
          filingPreviews: [...state.filingPreviews, filingWithoutContent],
          activeFilingPreviewId: filing.id,
          filingPreviewOpen: true,
          memoryPanelOpen: false 
        };
      }),
      closeFilingPreview: (id) => set((state) => {
        const newPreviews = state.filingPreviews.filter(f => f.id !== id);
        const wasActive = state.activeFilingPreviewId === id;
        return {
          filingPreviews: newPreviews,
          activeFilingPreviewId: wasActive 
            ? (newPreviews.length > 0 ? newPreviews[newPreviews.length - 1].id : null)
            : state.activeFilingPreviewId,
          filingPreviewOpen: newPreviews.length > 0
        };
      }),
      setActiveFilingPreview: (id) => set({ activeFilingPreviewId: id }),
      addFilingCitation: (citation) => set((state) => ({
        filingCitations: [...state.filingCitations, citation]
      })),
      removeFilingCitation: (id) => set((state) => ({
        filingCitations: state.filingCitations.filter(c => c.id !== id)
      })),
      clearFilingCitations: () => set({ filingCitations: [] }),
      addStudioArtifact: (artifact) => set((state) => ({ 
        studioArtifacts: [artifact, ...state.studioArtifacts],
        activeStudioArtifact: artifact
      })),
      removeStudioArtifact: (id) => set((state) => ({
        studioArtifacts: state.studioArtifacts.filter(a => a.id !== id),
        activeStudioArtifact: state.activeStudioArtifact?.id === id ? null : state.activeStudioArtifact
      })),
      setActiveStudioArtifact: (artifact) => set({ activeStudioArtifact: artifact }),
      clearStudioArtifacts: () => set({ studioArtifacts: [], activeStudioArtifact: null }),
      setSelectedSources: (sources) => set({ selectedSources: sources }),
    }),
    {
      name: 'sentry-ui-store',
      // Only persist filing previews - not transient UI state
      partialize: (state) => ({
        filingPreviews: state.filingPreviews,
        activeFilingPreviewId: state.activeFilingPreviewId,
        filingPreviewOpen: state.filingPreviews.length > 0 ? state.filingPreviewOpen : false,
      }),
    }
  )
);
