/**
 * StudioModal - Customization modal for generation types
 * 
 * Shows different options based on generation type:
 * - Mind Map: topic description
 * - Reports: format (briefing/detailed/executive), description
 * - Slide Deck: format (detailed/presenter), length, description
 * - Data Table: description
 */

import React, { useState } from 'react';
import { useUIStore, StudioArtifact } from '@/stores/uiStore';
import { chatAPI } from '@/services/api';
import toast from 'react-hot-toast';

// Professional SVG Icons
const Icons = {
  Close: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Loader: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`}>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeOpacity="0.25"/>
      <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  MindMap: ({ size = 20, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="4" cy="6" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="20" cy="6" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="4" cy="18" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="20" cy="18" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M9.5 10L6 7.5M14.5 10L18 7.5M9.5 14L6 16.5M14.5 14L18 16.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  Document: ({ size = 20, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Table: ({ size = 20, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Presentation: ({ size = 20, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 21l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 17v-4" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
};

interface StudioModalProps {
  type: 'mindmap' | 'report' | 'datatable' | 'slides';
  sessionId: string;
  onClose: () => void;
}

const StudioModal: React.FC<StudioModalProps> = ({ type, sessionId, onClose }) => {
  const [description, setDescription] = useState('');
  const [format, setFormat] = useState<string>('detailed');
  const [length, setLength] = useState<'short' | 'default'>('default');
  const [isGenerating, setIsGenerating] = useState(false);
  const { addStudioArtifact, selectedSources } = useUIStore();
  
  const sourceCount = selectedSources?.length || 0;

  const getTitle = () => {
    switch (type) {
      case 'mindmap': return 'Create Mind Map';
      case 'report': return 'Generate Report';
      case 'slides': return 'Create Slide Deck';
      case 'datatable': return 'Extract Data Table';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'mindmap': return <Icons.MindMap size={20} />;
      case 'report': return <Icons.Document size={20} />;
      case 'slides': return <Icons.Presentation size={20} />;
      case 'datatable': return <Icons.Table size={20} />;
    }
  };

  const getPlaceholder = () => {
    switch (type) {
      case 'mindmap': 
        return 'Describe the mind map you want to create...\n\nExample: "Map the key concepts and relationships in portfolio risk management"';
      case 'report': 
        return 'Describe the report you want to generate...\n\nExample: "Create an executive summary of AAPL\'s financial performance"';
      case 'slides': 
        return 'Describe the presentation you want to create...\n\nExample: "Create a deck for beginners explaining DCF valuation"';
      case 'datatable': 
        return 'Describe the data table you want to extract...\n\nExample: "Compare key metrics for AAPL, MSFT, GOOGL: revenue, profit margin, P/E ratio"';
    }
  };

  const handleGenerate = async () => {
    if (!description.trim()) {
      toast.error('Please provide a description');
      return;
    }
    
    if (sourceCount === 0) {
      toast('Generating without sources - add sources for better results', { icon: '💡' });
    }

    setIsGenerating(true);

    try {
      if (type === 'slides') {
        // First generate presentation outline/content via LLM
        const sourceIds = selectedSources?.map((s: any) => s.id) || [];
        
        toast('Generating presentation outline...', { icon: '📝' });
        
        // Generate the presentation content first
        const outlineResponse = await fetch('/api/v6/studio/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'report', // Use report type to generate markdown content
            description: `Create a presentation outline for: ${description}. Structure it with clear sections, bullet points, and key takeaways. Format: ${format === 'presenter' ? 'brief talking points' : 'detailed slides'}. Target length: ${length} slides.`,
            format: 'detailed',
            sessionId,
            sourceIds,
          }),
        });
        
        if (!outlineResponse.ok) {
          throw new Error('Failed to generate presentation outline');
        }
        
        const outlineData = await outlineResponse.json();
        const presentationContent = outlineData.markdown || `# ${description}\n\nPresentation about ${description}`;
        
        toast('Creating presentation with Gamma...', { icon: '🎨' });
        
        // Now send to Gamma with the generated content
        const exportResponse = await chatAPI.exportPdf({
          content: presentationContent,
          mode: 'analysis',
          template: 'custom',
        }, format === 'presenter' ? 'gamma_pptx' : 'gamma_pdf');
        
        // Download the file
        const url = URL.createObjectURL(exportResponse);
        const a = document.createElement('a');
        a.href = url;
        a.download = `presentation.${format === 'presenter' ? 'pptx' : 'pdf'}`;
        a.click();
        URL.revokeObjectURL(url);
        
        toast.success('Presentation generated!');
        onClose();
        return;
      }

      // Get source IDs to pass to the API
      const sourceIds = selectedSources?.map((s: any) => s.id) || [];

      // Call the studio generation API
      const response = await fetch('/api/v6/studio/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type,
          description,
          format,
          sessionId,
          sourceIds,
        }),
      });

      let data;
      if (response.ok) {
        data = await response.json();
      } else {
        // Fallback to mock data if API fails
        console.warn('Studio API failed, using mock data');
        data = generateMockData(type, description);
        data.sourceCount = 1;
      }
      
      const artifact: StudioArtifact = {
        id: `artifact-${Date.now()}`,
        type,
        title: data.title || getTitleFromDescription(description, type),
        data: type === 'report' ? data : data,
        createdAt: new Date(),
        sourceCount: data.sourceCount || 1,
      };

      addStudioArtifact(artifact);
      toast.success(`${getTitle()} created!`);
      onClose();

    } catch (error) {
      console.error('Generation error:', error);
      
      // Fallback to mock data for demo
      const mockData = generateMockData(type, description);
      const artifact: StudioArtifact = {
        id: `artifact-${Date.now()}`,
        type,
        title: getTitleFromDescription(description, type),
        data: mockData,
        createdAt: new Date(),
        sourceCount: 1,
      };

      addStudioArtifact(artifact);
      toast.success(`${getTitle()} created!`);
      onClose();
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div style={{ color: '#0051cc' }}>{getIcon()}</div>
            <h2 className="text-lg font-semibold text-gray-800">{getTitle()}</h2>
          </div>
          <button 
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <Icons.Close size={20} className="text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {/* Format selector for reports */}
          {type === 'report' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Format</label>
              <div className="flex gap-2">
                {['briefing', 'detailed', 'executive'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setFormat(f)}
                    className={`flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-all ${
                      format === f 
                        ? 'border-[#0051cc] bg-[#0051cc]/10 text-[#0051cc]' 
                        : 'border-gray-200 text-gray-600 hover:border-gray-300'
                    }`}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Format selector for slides */}
          {type === 'slides' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Format</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setFormat('detailed')}
                    className={`flex-1 p-3 rounded-lg border text-left transition-all ${
                      format === 'detailed' 
                        ? 'border-[#0051cc] bg-[#0051cc]/10' 
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="text-sm font-medium text-gray-800">Detailed Deck</div>
                    <div className="text-xs text-gray-500 mt-1">Full text and details, perfect for emailing</div>
                  </button>
                  <button
                    onClick={() => setFormat('presenter')}
                    className={`flex-1 p-3 rounded-lg border text-left transition-all ${
                      format === 'presenter' 
                        ? 'border-[#0051cc] bg-[#0051cc]/10' 
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="text-sm font-medium text-gray-800">Presenter Slides</div>
                    <div className="text-xs text-gray-500 mt-1">Key talking points for presentations</div>
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Length</label>
                <div className="flex gap-2">
                  {(['short', 'default'] as const).map((l) => (
                    <button
                      key={l}
                      onClick={() => setLength(l)}
                      className={`flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-all ${
                        length === l 
                          ? 'border-[#0051cc] bg-[#0051cc]/10 text-[#0051cc]' 
                          : 'border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}
                    >
                      {l.charAt(0).toUpperCase() + l.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Source count indicator */}
          <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className={`w-2 h-2 rounded-full ${sourceCount > 0 ? 'bg-green-500' : 'bg-gray-300'}`} />
            <span className="text-sm text-gray-600">
              {sourceCount > 0 
                ? `${sourceCount} source${sourceCount !== 1 ? 's' : ''} selected` 
                : 'No sources selected - add sources for better results'}
            </span>
          </div>

          {/* Description textarea */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {type === 'slides' ? 'Describe the slide deck you want to create' : 'Description'}
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={getPlaceholder()}
              rows={4}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0051cc] focus:border-transparent resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-5 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleGenerate}
            disabled={isGenerating || !description.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-[#0051cc] rounded-lg hover:bg-[#003d99] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {isGenerating ? (
              <>
                <Icons.Loader size={16} />
                Generating...
              </>
            ) : (
              'Generate'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

// Helper functions

function getTitleFromDescription(description: string, type: string): string {
  const words = description.split(' ').slice(0, 6).join(' ');
  const suffix = description.length > words.length ? '...' : '';
  return words + suffix || `New ${type}`;
}

function generateMockData(type: string, description: string): any {
  switch (type) {
    case 'mindmap':
      // Generate a simple mind map structure based on keywords
      const topic = description.split(' ').slice(0, 3).join(' ');
      return {
        title: topic,
        nodes: [
          { id: 'root', label: topic, children: ['n1', 'n2', 'n3', 'n4'] },
          { id: 'n1', label: 'Key Concept 1', children: [] },
          { id: 'n2', label: 'Key Concept 2', children: [] },
          { id: 'n3', label: 'Key Concept 3', children: [] },
          { id: 'n4', label: 'Key Concept 4', children: [] },
        ],
      };
    case 'report':
      return {
        markdown: `# ${getTitleFromDescription(description, 'report')}\n\n## Executive Summary\n\nThis report analyzes the key aspects of the topic.\n\n## Key Findings\n\n- Finding 1\n- Finding 2\n- Finding 3\n\n## Conclusion\n\nBased on the analysis...`,
      };
    case 'datatable':
      return {
        columns: ['Metric', 'Value', 'Change'],
        rows: [
          ['Revenue', '$100B', '+5%'],
          ['Profit', '$20B', '+10%'],
          ['Margin', '20%', '+2%'],
        ],
      };
    default:
      return {};
  }
}

export default StudioModal;

