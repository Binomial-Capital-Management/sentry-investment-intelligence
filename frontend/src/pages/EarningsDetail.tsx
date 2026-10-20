import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import axios from 'axios';

interface EarningsEvent {
  symbol: string;
  date: string;
  epsActual: number | null;
  epsEstimated: number | null;
  revenueActual: number | null;
  revenueEstimated: number | null;
  lastUpdated: string | null;
}

export default function EarningsDetail() {
  const { symbol, date } = useParams<{ symbol: string; date: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<EarningsEvent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('earnings');

  const apiUrl = (import.meta as any).env?.VITE_API_BASE ||
    (import.meta as any).env?.VITE_API_BASE_URL ||
    (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');

  useEffect(() => {
    const fetchEarningsDetail = async () => {
      try {
        setIsLoading(true);
        const response = await axios.get(`${apiUrl}/v6/market/earnings-calendar`);
        const data = response.data;

        const foundEvent = Object.values(data.calendar as Record<string, any>)
          .flatMap((day: any) => day.earnings)
          .find((e: EarningsEvent) => e.symbol === symbol && e.date === date);

        setEvent(foundEvent || null);
      } catch (error) {
        console.error('Failed to fetch earnings detail:', error);
      } finally {
        setIsLoading(false);
      }
    };

    if (symbol && date) {
      fetchEarningsDetail();
    }
  }, [symbol, date, apiUrl]);

  const formatCurrency = (value: number | null) => {
    if (value === null) return '—';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getReportPeriod = (dateStr: string) => {
    const date = new Date(dateStr);
    const quarter = Math.floor((date.getMonth() + 3) / 3);
    const year = date.getFullYear();
    return `Q${quarter} ${year}`;
  };

  const getEventTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    }) + ' at 7:00 AM EST';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-500">Loading earnings details...</div>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-500 mb-4">Earnings event not found</div>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white border-b">
          <div className="px-6 py-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
            >
              <ArrowLeft size={18} />
              <span className="text-sm">Back to Dashboard</span>
            </button>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <img
                  src={`https://logo.clearbit.com/${event.symbol.toLowerCase()}.com`}
                  alt={event.symbol}
                  className="w-16 h-16 rounded-lg"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    const fallback = (e.target as HTMLImageElement).nextElementSibling as HTMLElement;
                    if (fallback) fallback.style.display = 'flex';
                  }}
                />
                <div
                  className="w-16 h-16 bg-gray-200 rounded-lg hidden items-center justify-center text-xl font-bold text-gray-600"
                >
                  {event.symbol.slice(0, 2)}
                </div>

                <div>
                  <h1 className="text-2xl font-semibold text-gray-900">{event.symbol} Inc.</h1>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <span>{event.symbol}</span>
                    <span>·</span>
                    <span>NYSE</span>
                    <span>·</span>
                    <span>🇺🇸</span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => navigate('/chat')}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                Analyze in Chat
              </button>
            </div>
          </div>
        </div>

        {/* Quarter Selector */}
        <div className="bg-white border-b px-6 py-4">
          <div className="flex gap-3 overflow-x-auto">
            <button className="px-4 py-2 rounded-lg border border-blue-500 bg-blue-50 text-blue-600 text-sm font-medium whitespace-nowrap">
              {getReportPeriod(event.date)} Upcoming
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="p-6">
          <div className="bg-white rounded-lg border">
            {/* Sub Tabs */}
            <div className="border-b px-6 flex gap-6">
              {['Key Financials', 'Profile', 'Chart'].map((tab) => (
                <button
                  key={tab}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    tab === 'Key Financials'
                      ? 'border-gray-900 text-gray-900'
                      : 'border-transparent text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Data Grid - Compact */}
            <div className="p-4">
              <div className="grid grid-cols-2 gap-x-8 gap-y-4">
                {/* Report Date */}
                <div>
                  <div className="text-xs text-gray-600 mb-1">Report Date</div>
                  <div className="text-lg font-medium text-gray-900">{formatDate(event.date)}</div>
                </div>

                {/* Report Period */}
                <div>
                  <div className="text-xs text-gray-600 mb-1">Report Period</div>
                  <div className="text-lg font-medium text-gray-900">{getReportPeriod(event.date)}</div>
                </div>

                {/* Rev Estimate */}
                <div>
                  <div className="text-xs text-gray-600 mb-1">Rev Estimate</div>
                  <div className="text-lg font-medium text-gray-900">
                    {formatCurrency(event.revenueEstimated)}
                  </div>
                </div>

                {/* EPS Estimate */}
                <div>
                  <div className="text-xs text-gray-600 mb-1">EPS Estimate</div>
                  <div className="text-lg font-medium text-gray-900">
                    {event.epsEstimated !== null ? event.epsEstimated.toFixed(2) : '—'}
                  </div>
                </div>
              </div>
            </div>

            {/* Event Info */}
            <div className="p-8 text-center border-t">
              <p className="text-gray-600">Event starts on {getEventTime(event.date)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
