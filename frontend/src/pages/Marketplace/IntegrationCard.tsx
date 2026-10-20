import React from 'react';
import { useNavigate } from 'react-router-dom';

export interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  status: 'connected' | 'disconnected' | 'coming_soon';
  icon_url?: string;
  long_description?: string;
  features?: string[];
  supported_file_types?: string[];
  setup_guide_url?: string;
  docs_url?: string;
}

interface IntegrationCardProps {
  integration: Integration;
}

export const IntegrationCard: React.FC<IntegrationCardProps> = ({ integration }) => {
  const navigate = useNavigate();
  const [imgError, setImgError] = React.useState(false);

  const handleClick = () => {
    if (integration.status !== 'coming_soon') {
      navigate(`/marketplace/${integration.id}`);
    }
  };

  const isAvailable = integration.status !== 'coming_soon';

  return (
    <div
      onClick={handleClick}
      className={`
        group flex flex-col bg-white rounded-lg border border-[#E1DFDD]
        transition-all duration-200 h-full relative
        ${isAvailable
          ? 'cursor-pointer hover:border-[#0051cc] hover:shadow-[0_2px_4px_rgba(0,0,0,0.08)]'
          : 'opacity-60 cursor-not-allowed bg-[#fafafa]'}
      `}
      style={{
        boxShadow: isAvailable ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
      }}
    >
      <div className="p-4 flex-1 flex flex-col">
        <div className="flex justify-between items-start mb-3">
          {/* Logo Box - Reduced size */}
          <div className={`w-10 h-10 rounded border border-[#E1DFDD] flex items-center justify-center shrink-0 ${
            integration.icon_url && !imgError ? 'bg-white p-1.5' : 'bg-[#F3F2F1] text-xs font-bold text-[#605E5C]'
          }`}>
            {integration.icon_url && !imgError ? (
              <img
                src={integration.icon_url}
                alt=""
                className="w-full h-full object-contain"
                onError={() => setImgError(true)}
              />
            ) : (
              <span>{integration.name.substring(0, 2).toUpperCase()}</span>
            )}
          </div>

          {/* Minimal Status Badge - Smaller */}
          {integration.status === 'connected' && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold text-emerald-700 uppercase tracking-wide border border-emerald-100 bg-emerald-50">
              Active
            </span>
          )}
          {integration.status === 'coming_soon' && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold text-[#605E5C] uppercase tracking-wide border border-[#E1DFDD] bg-[#F3F2F1]">
              Soon
            </span>
          )}
        </div>

        {/* Title - Reduced size */}
        <h3 className="text-[14px] font-semibold text-[#323130] mb-1.5 group-hover:text-[#0051cc] transition-colors truncate">
          {integration.name}
        </h3>

        {/* Description - Reduced size */}
        <p className="text-[12px] text-[#605E5C] leading-snug line-clamp-2 mb-3 flex-grow">
          {integration.description}
        </p>

        {/* Footer - Compact */}
        <div className="mt-auto pt-2.5 border-t border-[#E1DFDD] flex items-center justify-between">
          <span className="text-[10px] font-semibold text-[#605E5C] uppercase tracking-wide">
            {integration.category}
          </span>

          {isAvailable && (
            <span className="text-[11px] font-semibold text-[#0051cc] opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              {integration.status === 'connected' ? 'Manage' : 'Add'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
