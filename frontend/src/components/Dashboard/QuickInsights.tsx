import { useEffect, useState } from 'react';
import { RefreshCw, Sparkles } from 'lucide-react';
import { getInsights, generateInsights, type PageType, type Insight } from '@/services/insightsApi';

interface QuickInsightsProps {
  pageType: PageType;
  region?: string;  // For markets page: 'us', 'eu', 'china', 'korea', 'japan'
}

const QuickInsights = ({ pageType, region }: QuickInsightsProps) => {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRegenerating, setIsRegenerating] = useState(false);

  useEffect(() => {
    loadInsights();
  }, [pageType, region]);

  const loadInsights = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getInsights(pageType, region, false, 6);
      setInsights(response.insights);
    } catch (err: any) {
      console.error('Failed to load insights:', err);
      setError(err.message || 'Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    try {
      setIsRegenerating(true);
      setError(null);
      await generateInsights({
        page_type: pageType,
        region: region,
        force_regenerate: true,
      });
      await new Promise(resolve => setTimeout(resolve, 2000));
      await loadInsights();
    } catch (err: any) {
      console.error('Failed to regenerate insights:', err);
      setError(err.message || 'Failed to regenerate insights');
    } finally {
      setIsRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white border border-gray-300 rounded p-4">
        <div className="text-center py-6 text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white border border-gray-300 rounded p-4">
        <div className="text-center py-4">
          <p className="text-red-600 text-sm">{error}</p>
          <button onClick={loadInsights} className="mt-2 text-xs text-blue-600 hover:underline">
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (insights.length === 0) {
    return (
      <div className="bg-white border border-gray-300 rounded p-4">
        <div className="text-center py-4">
          <p className="text-gray-500 text-sm mb-3">No insights yet</p>
          <button
            onClick={handleRegenerate}
            disabled={isRegenerating}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 rounded"
          >
            <RefreshCw className={`h-3 w-3 ${isRegenerating ? 'animate-spin' : ''}`} />
            {isRegenerating ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>
    );
  }

  // Display insights
  return (
    <div className="bg-white border border-gray-300 rounded p-4">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-500" />
          <span className="text-xs text-gray-600">
            Updated {new Date(insights[0]?.generated_at).toLocaleString([], {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <button
          onClick={handleRegenerate}
          disabled={isRegenerating}
          className="inline-flex items-center gap-1.5 px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-50 rounded transition-colors"
          title="Regenerate insights"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* Insights list */}
      <div className="space-y-3">
        {insights.map((insight) => (
          <div key={insight.id} className="flex items-start gap-3 py-2">
            <div className="flex-shrink-0 w-1.5 h-1.5 bg-blue-500 rounded-full mt-2"></div>
            <p className="text-gray-700 text-sm leading-relaxed flex-1">
              {insight.content.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default QuickInsights;
