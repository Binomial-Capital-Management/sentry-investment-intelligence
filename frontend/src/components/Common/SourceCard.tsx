import React from 'react';

interface SourceCardProps {
  source: {
    id: string;
    title: string;
    url: string;
    snippet?: string;
    domain?: string;
    index?: number;
    score?: number;
  };
  compact?: boolean;
}

const SourceCard: React.FC<SourceCardProps> = ({ source, compact = false }) => {
  const getDomainFromUrl = (url: string) => {
    try {
      const domain = new URL(url).hostname;
      return domain.replace('www.', '');
    } catch {
      return source.domain || '';
    }
  };

  if (compact) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200 hover:scale-[1.02] bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/30"
      >
        <span className="font-medium">[{source.index || source.id}]</span>
        <span className="truncate max-w-[200px]">{source.title}</span>
        {source.domain && (
          <span className="text-xs opacity-70">• {getDomainFromUrl(source.url)}</span>
        )}
      </a>
    );
  }

  return (
    <div className="source-card group">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="source-card-title group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors"
          >
            {source.index && (
              <span className="inline-block mr-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                [{source.index}]
              </span>
            )}
            {source.title}
          </a>
          <div className="source-card-url mt-1">
            {getDomainFromUrl(source.url)}
          </div>
        </div>
        {source.score && source.score > 0 && (
          <div className="ml-4">
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {Math.round(source.score * 100)}% relevant
            </div>
          </div>
        )}
      </div>
      {source.snippet && (
        <p className="source-card-snippet">
          {source.snippet}
        </p>
      )}
    </div>
  );
};

export default SourceCard;
