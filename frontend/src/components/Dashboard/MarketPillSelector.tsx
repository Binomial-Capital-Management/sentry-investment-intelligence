import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Bitcoin, Landmark, Sparkles, RefreshCw, TrendingUp, Rocket } from 'lucide-react';
import axios from 'axios';

interface MarketOption {
  id: string;
  label: string;
  flagImage: string;
  region: string;
}

interface PillOption {
  id: string;
  label: string;
  hasDropdown?: boolean;
  icon?: React.ComponentType<{ size?: number; className?: string }>;
}

interface FGIData {
  fgi: {
    now: {
      value: number;
      valueText: string;
    };
    previousClose?: {
      value: number;
      valueText: string;
    };
  };
  lastUpdated: {
    humanDate: string;
    fetchedAt: string;
  };
  marketStatus: {
    isOpen: boolean;
    statusText: string;
    currentDate: string;
    currentTime: string;
    timezone: string;
  };
}

const marketRegions: MarketOption[] = [
  { id: 'us', label: 'US Markets', flagImage: '/flags/usa.png', region: 'North America' },
  { id: 'eu', label: 'EU Markets', flagImage: '/flags/europeanunion.png', region: 'Europe' },
  { id: 'china', label: 'China', flagImage: '/flags/china.png', region: 'Asia' },
  { id: 'korea', label: 'Korea', flagImage: '/flags/korea.png', region: 'Asia' },
  { id: 'japan', label: 'Japan', flagImage: '/flags/japan.png', region: 'Asia' },
];

const pills: PillOption[] = [
  { id: 'markets', label: 'US Markets', hasDropdown: true },
  { id: 'crypto', label: 'Crypto', icon: Bitcoin },
  { id: 'macro', label: 'Macro & Alternatives', icon: Landmark },
  { id: 'earnings', label: 'Earnings', icon: TrendingUp },
  { id: 'ipos', label: 'Recent IPOs', icon: Rocket },
  { id: 'screener', label: 'AI Screener', icon: Sparkles },
];

interface MarketPillSelectorProps {
  initialMarket?: string;
  initialPill?: string;
  onMarketChange?: (marketId: string) => void;
  onPillChange?: (pillId: string) => void;
}

export const MarketPillSelector: React.FC<MarketPillSelectorProps> = ({
  initialMarket = 'us',
  initialPill = 'markets',
  onMarketChange,
  onPillChange,
}) => {
  const [selectedMarket, setSelectedMarket] = useState<MarketOption>(
    () => marketRegions.find(m => m.id === initialMarket) || marketRegions[0],
  );
  const [selectedPill, setSelectedPill] = useState<string>(initialPill);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [fgiData, setFgiData] = useState<FGIData | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch Fear & Greed Index data
  const fetchFGI = async (forceRefresh: boolean = false) => {
    try {
      setIsRefreshing(true);
      const apiUrl = (import.meta as any).env?.VITE_API_BASE ||
        (import.meta as any).env?.VITE_API_BASE_URL ||
        (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');

      if (forceRefresh) {
        // Call refresh endpoint to fetch fresh data from API
        await axios.post(`${apiUrl}/v6/market/fear-greed-index/refresh`);
        // After refresh, fetch the updated data from the GET endpoint
        // since refresh returns a different response structure
        const response = await axios.get(`${apiUrl}/v6/market/fear-greed-index`);
        setFgiData(response.data);
      } else {
        // Just get cached data from database
        const response = await axios.get(`${apiUrl}/v6/market/fear-greed-index`);
        setFgiData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch Fear & Greed Index:', error);
      // Fail silently - component will show "Mixed" as fallback
    } finally {
      setIsRefreshing(false);
    }
  };

  // Fetch on mount
  useEffect(() => {
    fetchFGI();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarketSelect = (market: MarketOption) => {
    setSelectedMarket(market);
    setIsDropdownOpen(false);
    onMarketChange?.(market.id);
  };

  const handlePillClick = (pillId: string) => {
    setSelectedPill(pillId);
    if (pillId === 'markets') {
      setIsDropdownOpen(!isDropdownOpen);
    }
    onPillChange?.(pillId);
  };

  const getMarketStatus = () => {
    return fgiData?.marketStatus?.statusText || 'Market Closed';
  };

  const getFormattedDate = () => {
    return fgiData?.marketStatus?.currentDate || formatDate();
  };

  const getSentiment = () => {
    return fgiData?.fgi?.now?.valueText || 'Mixed';
  };

  const getLastUpdated = () => {
    if (!fgiData?.lastUpdated?.fetchedAt) return '';
    const date = new Date(fgiData.lastUpdated.fetchedAt);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getBarColor = (value: number) => {
    // Color gradient based on CNN Fear & Greed Index standard ranges (0-100)
    if (value <= 24) {
      // 0-24: Extreme Fear → Red
      return 'bg-red-500';
    } else if (value <= 44) {
      // 25-44: Fear → Orange
      return 'bg-orange-500';
    } else if (value <= 55) {
      // 45-55: Neutral → Yellow
      return 'bg-yellow-500';
    } else if (value <= 74) {
      // 56-74: Greed → Lime
      return 'bg-lime-500';
    } else {
      // 75-100: Extreme Greed → Green
      return 'bg-green-500';
    }
  };

  const renderSentimentBars = () => {
    if (!fgiData) {
      // Fallback: show mixed sentiment bars (current behavior)
      return (
        <>
          <div className="w-0.5 h-3 bg-orange-400 rounded-sm" />
          <div className="w-0.5 h-3 bg-amber-500 rounded-sm" />
          <div className="w-0.5 h-3 bg-yellow-500 rounded-sm" />
          <div className="w-0.5 h-3 bg-orange-500 rounded-sm" />
          <div className="w-0.5 h-3 bg-amber-400 rounded-sm" />
          <div className="w-0.5 h-3 bg-yellow-400 rounded-sm" />
          <div className="w-0.5 h-3 bg-orange-400 rounded-sm" />
          <div className="w-0.5 h-3 bg-amber-500 rounded-sm" />
        </>
      );
    }

    const value = fgiData?.fgi?.now?.value ?? 50;
    const fillPercentage = value / 100;
    const totalBars = 8;
    const filledBars = Math.ceil(fillPercentage * totalBars);
    const barColor = getBarColor(value);

    return Array.from({ length: totalBars }, (_, index) => (
      <div
        key={index}
        className={`w-0.5 h-3 rounded-sm ${
          index < filledBars ? barColor : 'bg-gray-300'
        }`}
      />
    ));
  };

  const formatDate = () => {
    const now = new Date();
    return now.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="flex flex-col md:flex-row items-start md:items-center justify-between py-3 bg-white gap-3">
      {/* Left side - Pills */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {pills.map((pill) => (
          <div key={pill.id} className="relative" ref={pill.id === 'markets' ? dropdownRef : null}>
            <button
              onClick={() => handlePillClick(pill.id)}
              className={`
                flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium
                transition-all duration-200 border whitespace-nowrap
                ${
                  selectedPill === pill.id
                    ? 'border-blue-500 text-blue-600 bg-blue-50'
                    : 'border-gray-300 text-gray-700 bg-transparent hover:border-gray-400 hover:bg-gray-50'
                }
              `}
            >
              {pill.id === 'markets' && (
                <img src={selectedMarket.flagImage} alt="" className="w-4 h-3 object-cover rounded-sm" />
              )}
              {pill.icon && pill.id !== 'markets' && (
                <pill.icon
                  size={16}
                  className={`flex-shrink-0 ${
                    pill.id === 'earnings' ? 'text-blue-600' :
                    pill.id === 'ipos' ? 'text-indigo-600' :
                    pill.id === 'crypto' ? 'text-orange-500' :
                    pill.id === 'macro' ? 'text-emerald-600' :
                    pill.id === 'screener' ? 'text-purple-600' :
                    ''
                  }`}
                />
              )}
              <span>{pill.id === 'markets' ? selectedMarket.label : pill.label}</span>
              {pill.id === 'screener' && (
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 rounded">
                  Beta
                </span>
              )}
              {pill.hasDropdown && (
                <ChevronDown
                  size={14}
                  className={`transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`}
                />
              )}
            </button>

            {/* Dropdown menu */}
            {pill.id === 'markets' && isDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-40 bg-white border border-gray-200 rounded shadow-lg overflow-hidden z-50">
                {marketRegions.map((market) => (
                  <button
                    key={market.id}
                    onClick={() => handleMarketSelect(market)}
                    className={`
                      w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs
                      transition-colors
                      ${
                        selectedMarket.id === market.id
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-gray-700 hover:bg-gray-50'
                      }
                    `}
                  >
                    <img src={market.flagImage} alt="" className="w-4 h-3 object-cover rounded-sm" />
                    <span className="font-medium">{market.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Right side - Market status and sentiment */}
      <div className="flex items-center gap-3 md:gap-4 text-xs">
        <div className="flex items-center gap-2 text-gray-500">
          <span className="font-medium hidden sm:inline">{getFormattedDate()}, EST</span>
          <span className="font-medium sm:hidden">{getFormattedDate()}</span>
          <span className="text-gray-300 hidden sm:inline">·</span>
          <span className="font-medium text-gray-600">{getMarketStatus()}</span>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5">
              {renderSentimentBars()}
            </div>
            <span className="text-gray-600 font-medium">{getSentiment()}</span>
          </div>

          {fgiData && (
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <span className="text-gray-300">·</span>
              <span>Updated {getLastUpdated()}</span>
              <button
                onClick={() => fetchFGI(true)}
                disabled={isRefreshing}
                className="p-1 hover:bg-gray-100 rounded transition-colors disabled:opacity-50"
                title="Refresh sentiment data from source"
              >
                <RefreshCw size={12} className={`${isRefreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
