import React, { useState, useEffect } from 'react';
import { Calendar, ChevronLeft, ChevronRight, RefreshCw, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import TradingViewProfile from './TradingViewProfile';
import TradingViewFinancials from './TradingViewFinancials';
import TradingViewTechnical from './TradingViewTechnical';
import TradingViewChart from './TradingViewChart';

interface EarningsEvent {
  symbol: string;
  date: string;
  epsActual: number | null;
  epsEstimated: number | null;
  revenueActual: number | null;
  revenueEstimated: number | null;
  lastUpdated: string | null;
}

interface DayData {
  date: string;
  count: number;
  earnings: EarningsEvent[];
}

interface EarningsCalendarData {
  calendar: Record<string, DayData>;
  summary: {
    totalEvents: number;
    dateRange: { from: string; to: string } | null;
    lastFetched: string | null;
  };
}

export const EarningsCalendar: React.FC = () => {
  const navigate = useNavigate();
  const [calendarData, setCalendarData] = useState<EarningsCalendarData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [weekOffset, setWeekOffset] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<EarningsEvent | null>(null);
  const [activeTab, setActiveTab] = useState<'metrics' | 'chart'>('metrics');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [pickerMonthIndex, setPickerMonthIndex] = useState(0);

  const apiUrl = (import.meta as any).env?.VITE_API_BASE ||
    (import.meta as any).env?.VITE_API_BASE_URL ||
    (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');

  const logoDevToken = (import.meta as any).env?.VITE_LOGODEV_TOKEN;

  const getCompanyLogoUrl = (symbol: string) => {
    if (!logoDevToken) {
      console.warn('Logo.dev token not configured');
      return `https://logo.clearbit.com/${symbol.toLowerCase()}.com`;
    }
    return `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${logoDevToken}`;
  };

  useEffect(() => {
    fetchEarningsCalendar();
  }, []);


  const fetchEarningsCalendar = async () => {
    try {
      setIsLoading(true);
      const response = await axios.get(`${apiUrl}/v6/market/earnings-calendar`);
      setCalendarData(response.data);

      // Navigate to today's week and select appropriate date
      const dates = Object.keys(response.data.calendar).sort();
      const today = new Date().toISOString().split('T')[0];
      
      // Find today or the closest future date with earnings
      let targetIndex = dates.indexOf(today);
      if (targetIndex < 0) {
        targetIndex = dates.findIndex(date => date >= today);
        if (targetIndex < 0) {
          targetIndex = 0; // No future dates, go to first
        }
      }
      
      if (dates.length > 0) {
        // Set week offset to show the week containing today/target date
        setWeekOffset(Math.floor(targetIndex / 7));
        setSelectedDate(dates[targetIndex]);
      }
    } catch (error) {
      console.error('Failed to fetch earnings calendar:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const refreshCalendar = async () => {
    try {
      setIsRefreshing(true);
      await axios.post(`${apiUrl}/v6/market/earnings-calendar/refresh`);
      await fetchEarningsCalendar();
    } catch (error) {
      console.error('Failed to refresh earnings calendar:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const getWeekDates = () => {
    if (!calendarData) return [];
    const allDates = Object.keys(calendarData.calendar).sort();
    const startIndex = weekOffset * 7;
    return allDates.slice(startIndex, startIndex + 7);
  };

  const getTotalWeeks = () => {
    if (!calendarData) return 0;
    const allDates = Object.keys(calendarData.calendar).sort();
    return Math.ceil(allDates.length / 7);
  };

  const canGoBack = weekOffset > 0;
  const canGoForward = weekOffset < getTotalWeeks() - 1;

  const isOnCurrentWeek = () => {
    if (!calendarData) return false;
    const dates = Object.keys(calendarData.calendar).sort();
    const today = new Date().toISOString().split('T')[0];

    let targetIndex = dates.indexOf(today);
    if (targetIndex < 0) {
      targetIndex = dates.findIndex(date => date >= today);
      if (targetIndex < 0) return false;
    }

    const currentWeekIndex = Math.floor(targetIndex / 7);
    return weekOffset === currentWeekIndex;
  };

  const goToToday = () => {
    if (!calendarData) return;
    const dates = Object.keys(calendarData.calendar).sort();
    const today = new Date().toISOString().split('T')[0];

    // Find today's date or the next closest date
    let targetIndex = dates.indexOf(today);

    if (targetIndex < 0) {
      // Today not found, find the closest future date
      targetIndex = dates.findIndex(date => date >= today);
      if (targetIndex < 0) {
        // No future dates, go to first date
        targetIndex = 0;
      }
    }

    if (dates.length > 0) {
      setWeekOffset(Math.floor(targetIndex / 7));
      setSelectedDate(dates[targetIndex]);
    }
  };

  const formatDayName = (dateStr: string) => {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', { weekday: 'short' });
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getQuarterAndTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const quarter = Math.floor((date.getMonth() + 3) / 3);
    const year = date.getFullYear().toString().slice(-2);

    // Default to 4:00 PM for after-market (most common)
    return `Q${quarter} '${year}  4:00 PM`;
  };

  const getCompanyLogos = (earnings: EarningsEvent[]) => {
    // Show first 3-4 company logos as circular icons
    const visibleLogos = earnings.slice(0, 4);

    // Color palette for fallback circles
    const colors = ['bg-orange-500', 'bg-blue-500', 'bg-red-500', 'bg-green-500', 'bg-purple-500', 'bg-yellow-500'];

    return (
      <div className="flex -space-x-1.5">
        {visibleLogos.map((event, index) => (
          <div key={`${event.symbol}-${index}`} className="relative">
            <img
              src={getCompanyLogoUrl(event.symbol)}
              alt={event.symbol}
              className="w-5 h-5 rounded-full border-2 border-white bg-white"
              onError={(e) => {
                // Fallback to colored circle with symbol initials
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
              }}
            />
            <div
              className={`w-5 h-5 rounded-full border-2 border-white ${colors[index % colors.length]} hidden items-center justify-center text-[9px] font-bold text-white`}
            >
              {event.symbol.slice(0, 1)}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const formatCurrency = (value: number | null) => {
    if (value === null) return '—';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 2,
    }).format(value);
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
    }) + ' at 7:00 AM GMT+2';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-500">Loading earnings calendar...</div>
      </div>
    );
  }

  // If an event is selected, show detail view
  if (selectedEvent) {
    return (
      <div className="bg-white rounded-lg w-full max-w-full overflow-hidden">
        {/* Header */}
        <div className="border-b">
          <div className="px-6 py-4">
            <button
              onClick={() => setSelectedEvent(null)}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
            >
              <ArrowLeft size={18} />
              <span className="text-sm">Back to Calendar</span>
            </button>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <img
                  src={getCompanyLogoUrl(selectedEvent.symbol)}
                  alt={selectedEvent.symbol}
                  className="w-16 h-16 rounded-lg"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    const fallback = (e.target as HTMLImageElement).nextElementSibling as HTMLElement;
                    if (fallback) fallback.style.display = 'flex';
                  }}
                />
                <div className="w-16 h-16 bg-gray-200 rounded-lg hidden items-center justify-center text-xl font-bold text-gray-600">
                  {selectedEvent.symbol.slice(0, 2)}
                </div>

                <div>
                  <h1 className="text-2xl font-semibold text-gray-900">{selectedEvent.symbol} Inc.</h1>
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-1">
                    <span>{selectedEvent.symbol}</span>
                    <span>·</span>
                    <span>NYSE</span>
                    <span>·</span>
                    <span>🇺🇸</span>
                  </div>
                  <div className="text-sm text-gray-500">
                    Event starts on {getEventTime(selectedEvent.date)}
                  </div>
                </div>
              </div>

              <button
                onClick={() => {
                  navigate('/chat', {
                    state: {
                      initialMessage: `Conduct me a detailed analysis for ${selectedEvent.symbol}`,
                    },
                  });
                }}
                className="px-4 py-1.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded hover:border-gray-400 transition-colors"
              >
                Analyze in Chat
              </button>
            </div>
          </div>
        </div>

        {/* Quarter Selector */}
        <div className="border-b px-6 py-4">
          <div className="flex gap-3 overflow-x-auto">
            <button className="px-4 py-2 rounded-lg border border-blue-500 bg-blue-50 text-blue-600 text-sm font-medium whitespace-nowrap">
              {getReportPeriod(selectedEvent.date)} Upcoming
            </button>
          </div>
        </div>

        {/* Data Grid */}
        <div className="p-6">
          <div className="grid grid-cols-3 gap-x-12 gap-y-8">
            {/* Report Date */}
            <div>
              <div className="text-sm text-gray-600 mb-2">Report Date</div>
              <div className="text-2xl font-normal text-gray-900">{formatDate(selectedEvent.date)}</div>
            </div>

            {/* Rev Estimate */}
            <div>
              <div className="text-sm text-gray-600 mb-2">Rev Estimate</div>
              <div className="text-2xl font-normal text-gray-900">
                {formatCurrency(selectedEvent.revenueEstimated)}
              </div>
            </div>

            {/* Avg 1d Change */}
            <div>
              <div className="text-sm text-gray-600 mb-2 flex items-center gap-1">
                Avg 1d Change
                <span className="text-gray-400 cursor-help">ⓘ</span>
              </div>
              <div className="text-2xl font-normal text-gray-900">—</div>
            </div>

            {/* Report Period */}
            <div>
              <div className="text-sm text-gray-600 mb-2">Report Period</div>
              <div className="text-2xl font-normal text-gray-900">{getReportPeriod(selectedEvent.date)}</div>
            </div>

            {/* EPS Estimate */}
            <div>
              <div className="text-sm text-gray-600 mb-2">EPS Estimate</div>
              <div className="text-2xl font-normal text-gray-900">
                {selectedEvent.epsEstimated !== null ? selectedEvent.epsEstimated.toFixed(2) : '—'}
              </div>
            </div>

            {/* Implied Move 1d */}
            <div>
              <div className="text-sm text-gray-600 mb-2 flex items-center gap-1">
                Implied Move 1d
                <span className="text-gray-400 cursor-help">ⓘ</span>
              </div>
              <div className="text-2xl font-normal text-gray-900">—</div>
            </div>
          </div>
        </div>

        {/* Sub Tabs */}
        <div className="border-t px-6 flex gap-6">
          <button
            onClick={() => setActiveTab('metrics')}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'metrics'
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Key Metrics
          </button>
          <button
            onClick={() => setActiveTab('chart')}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'chart'
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Chart
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'metrics' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <TradingViewProfile symbol={selectedEvent.symbol} />
              <TradingViewFinancials symbol={selectedEvent.symbol} />
              <TradingViewTechnical symbol={selectedEvent.symbol} />
            </div>
          ) : (
            <TradingViewChart symbol={selectedEvent.symbol} />
          )}
        </div>
      </div>
    );
  }

  // Calendar view
  const weekDates = getWeekDates();
  const selectedDayData = selectedDate ? calendarData?.calendar[selectedDate] : null;

  return (
    <div className="flex flex-col h-full bg-white rounded-lg w-full max-w-full relative" style={{ overflow: 'visible' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b">
        <h2 className="text-xl font-semibold text-gray-800">Earnings Calendar</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              // Find current month index
              if (!showDatePicker && calendarData) {
                const datesByMonth: { [key: string]: Set<string> } = {};
                Object.keys(calendarData.calendar).forEach(date => {
                  const monthKey = date.substring(0, 7);
                  if (!datesByMonth[monthKey]) {
                    datesByMonth[monthKey] = new Set();
                  }
                  datesByMonth[monthKey].add(date);
                });
                const months = Object.keys(datesByMonth).sort();
                const today = new Date().toISOString().split('T')[0];
                const currentMonthKey = today.substring(0, 7);
                const monthIndex = months.indexOf(currentMonthKey);
                setPickerMonthIndex(monthIndex >= 0 ? monthIndex : 0);
              }
              setShowDatePicker(!showDatePicker);
            }}
            className={`p-1.5 rounded-md transition-colors ${
              showDatePicker
                ? 'text-blue-600 bg-blue-50'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
            title="Show full calendar"
          >
            <Calendar size={14} />
          </button>
          <button
            onClick={refreshCalendar}
            disabled={isRefreshing}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Refresh earnings data"
          >
            <RefreshCw size={14} className={`${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setWeekOffset(Math.max(0, weekOffset - 1))}
            disabled={!canGoBack}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-md disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={14} />
          </button>
          {!isOnCurrentWeek() && (
            <button
              onClick={goToToday}
              className="px-2.5 py-1 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-md transition-colors"
            >
              Today
            </button>
          )}
          <button
            onClick={() => setWeekOffset(weekOffset + 1)}
            disabled={!canGoForward}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-md disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Date Picker Popup */}
      {showDatePicker && calendarData && (() => {
        // Group dates by month
        const datesByMonth: { [key: string]: Set<string> } = {};
        Object.keys(calendarData.calendar).forEach(date => {
          const monthKey = date.substring(0, 7); // YYYY-MM
          if (!datesByMonth[monthKey]) {
            datesByMonth[monthKey] = new Set();
          }
          datesByMonth[monthKey].add(date);
        });

        const months = Object.keys(datesByMonth).sort();
        const currentMonthKey = months[pickerMonthIndex] || months[0];
        const [year, month] = currentMonthKey.split('-');
        const firstDay = new Date(parseInt(year), parseInt(month) - 1, 1);
        const lastDay = new Date(parseInt(year), parseInt(month), 0);
        const daysInMonth = lastDay.getDate();
        const startDayOfWeek = firstDay.getDay(); // 0 = Sunday

        const canGoPrevMonth = pickerMonthIndex > 0;
        const canGoNextMonth = pickerMonthIndex < months.length - 1;

        return (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-[100]"
              onClick={() => setShowDatePicker(false)}
            />

            {/* Popup */}
            <div className="absolute top-16 right-6 z-[101] bg-white rounded-lg border border-gray-300 shadow-xl w-80">
              <div className="p-3">
                {/* Header with navigation */}
                <div className="flex items-center justify-between mb-3 pb-2 border-b">
                  <button
                    onClick={() => setPickerMonthIndex(Math.max(0, pickerMonthIndex - 1))}
                    disabled={!canGoPrevMonth}
                    className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft size={16} />
                  </button>

                  <span className="text-sm font-semibold text-gray-700">
                    {firstDay.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                  </span>

                  <button
                    onClick={() => setShowDatePicker(false)}
                    className="p-1 text-gray-400 hover:text-gray-600"
                  >
                    ✕
                  </button>

                  <button
                    onClick={() => setPickerMonthIndex(Math.min(months.length - 1, pickerMonthIndex + 1))}
                    disabled={!canGoNextMonth}
                    className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>

                {/* Day headers */}
                <div className="grid grid-cols-7 gap-1 mb-1">
                  {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, i) => (
                    <div key={i} className="text-center text-[10px] font-semibold text-gray-400 py-1">
                      {day}
                    </div>
                  ))}
                </div>

                {/* Calendar grid */}
                <div className="grid grid-cols-7 gap-1">
                  {/* Empty cells for days before month starts */}
                  {Array.from({ length: startDayOfWeek }).map((_, i) => (
                    <div key={`empty-${i}`} className="aspect-square" />
                  ))}

                  {/* Days of the month */}
                  {Array.from({ length: daysInMonth }).map((_, i) => {
                    const dayNum = i + 1;
                    const dateStr = `${year}-${month}-${dayNum.toString().padStart(2, '0')}`;
                    const dayData = calendarData.calendar[dateStr];
                    const hasEarnings = dayData && dayData.count > 0;
                    const isToday = dateStr === new Date().toISOString().split('T')[0];
                    const isCurrentlySelected = dateStr === selectedDate;

                    return (
                      <button
                        key={dayNum}
                        onClick={() => {
                          if (!hasEarnings) return;
                          const allDates = Object.keys(calendarData.calendar).sort();
                          const dateIndex = allDates.indexOf(dateStr);
                          setWeekOffset(Math.floor(dateIndex / 7));
                          setSelectedDate(dateStr);
                          setShowDatePicker(false);
                        }}
                        disabled={!hasEarnings}
                        className={`
                          aspect-square p-1 rounded text-[11px] transition-colors flex flex-col items-center justify-center
                          ${!hasEarnings
                            ? 'text-gray-300 cursor-not-allowed'
                            : isCurrentlySelected
                              ? 'bg-blue-100 border-2 border-blue-500 font-bold text-blue-700'
                              : isToday
                                ? 'bg-blue-500 text-white font-bold hover:bg-blue-600'
                                : 'bg-gray-50 hover:bg-gray-100 text-gray-900'
                          }
                        `}
                      >
                        <span className="font-semibold">{dayNum}</span>
                        {hasEarnings && (
                          <span className={`text-[8px] font-medium mt-0.5 ${
                            isToday && !isCurrentlySelected ? 'text-white' : 'text-blue-600'
                          }`}>
                            {dayData.count}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </>
        );
      })()}

      {/* Week selector */}
      <div className="grid grid-cols-7 gap-1 px-6 py-2">
        {weekDates.map((date) => {
          const dayData = calendarData?.calendar[date];
          const isSelected = selectedDate === date;
          const hasEarnings = dayData && dayData.count > 0;

          return (
            <button
              key={date}
              onClick={() => setSelectedDate(date)}
              className={`
                flex flex-col overflow-hidden rounded-md
                transition-all
                ${isSelected
                  ? 'border border-blue-500'
                  : hasEarnings
                    ? 'border border-gray-300 hover:border-gray-400'
                    : 'border border-gray-200'
                }
              `}
            >
              {/* Gray header */}
              <div className="bg-gray-100 w-full py-1">
                <span className="text-[10px] font-medium text-gray-600">
                  {formatDayName(date)}
                </span>
              </div>

              {/* White body */}
              <div className="bg-white flex flex-col items-center px-1.5 py-1.5">
                <span className={`text-xs font-bold mb-0.5 ${isSelected ? 'text-blue-600' : 'text-gray-900'}`}>
                  {formatDate(date)}
                </span>

                {hasEarnings ? (
                  <div className="flex flex-col items-center gap-0.5">
                    {getCompanyLogos(dayData.earnings)}
                    <span className={`text-[9px] font-medium ${isSelected ? 'text-blue-600' : 'text-gray-700'}`}>
                      {dayData.count} Calls
                    </span>
                  </div>
                ) : (
                  <span className="text-[9px] text-gray-400">No Calls</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Earnings list */}
      <div className="flex-1 overflow-y-auto">
        {selectedDayData && selectedDayData.earnings.length > 0 ? (
          <div className="divide-y divide-gray-100">
            {selectedDayData.earnings.map((event, index) => (
              <div
                key={`${event.symbol}-${index}`}
                onClick={() => setSelectedEvent(event)}
                className="flex items-center gap-3 px-6 py-2.5 hover:bg-gray-50 transition-colors cursor-pointer"
              >
                {/* Company logo */}
                <img
                  src={getCompanyLogoUrl(event.symbol)}
                  alt={event.symbol}
                  className="w-8 h-8 rounded-full"
                  onError={(e) => {
                    // Fallback to placeholder with symbol initials
                    (e.target as HTMLImageElement).style.display = 'none';
                    const fallback = (e.target as HTMLImageElement).nextElementSibling as HTMLElement;
                    if (fallback) fallback.style.display = 'flex';
                  }}
                />
                <div
                  className="w-8 h-8 bg-gray-200 rounded-full hidden items-center justify-center text-xs font-bold text-gray-600"
                >
                  {event.symbol.slice(0, 2)}
                </div>

                {/* Company info */}
                <div className="flex-1">
                  <div className="font-medium text-sm text-gray-900">
                    {event.symbol}
                  </div>
                  <div className="text-xs text-gray-500">
                    {event.symbol}
                  </div>
                </div>

                {/* Quarter and time */}
                <div className="text-xs font-medium text-gray-600">
                  {getQuarterAndTime(event.date)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center py-32">
            <span className="text-gray-400 text-lg">No Earnings Calls</span>
          </div>
        )}
      </div>
    </div>
  );
};
