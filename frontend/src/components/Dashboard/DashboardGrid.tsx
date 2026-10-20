import { useState } from 'react';
import AggregatedPortfolioChart from './AggregatedPortfolioChart';

const DashboardGrid = () => {
  // Sample data for demonstration
  const [portfolioValue] = useState(1234567.89);
  const [dailyChange] = useState(12345.67);
  const [percentChange] = useState(1.02);
  const [riskScore] = useState(73);

  return (
    <div className="px-6 py-4 grid gap-4" style={{ gridTemplateColumns: 'repeat(12, minmax(0, 1fr))' }}>
      {/* Metric Cards Row */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 col-span-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500 font-medium">Portfolio Value</p>
            <p className="text-2xl font-semibold text-gray-900 mt-1">
              ${portfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
          <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 col-span-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500 font-medium">Daily Change</p>
            <p className="text-2xl font-semibold text-emerald-600 mt-1">
              +${dailyChange.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
            <p className="text-sm text-emerald-600 mt-1">+{percentChange}%</p>
          </div>
          <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
            <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 col-span-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500 font-medium">Risk Score</p>
            <p className="text-2xl font-semibold text-gray-900 mt-1">{riskScore}/100</p>
            <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 rounded-full"
                style={{ width: `${riskScore}%` }}
              />
            </div>
          </div>
          <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
            <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 col-span-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500 font-medium">Active Positions</p>
            <p className="text-2xl font-semibold text-gray-900 mt-1">24</p>
            <p className="text-sm text-gray-500 mt-1">Across 5 sectors</p>
          </div>
          <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
            <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Chart Areas */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 col-span-8">
        <AggregatedPortfolioChart />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 col-span-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Holdings</h3>
        <div className="space-y-3">
          {[
            { symbol: 'AAPL', name: 'Apple Inc.', value: 234567.89, change: 2.3 },
            { symbol: 'MSFT', name: 'Microsoft Corp.', value: 198765.43, change: -0.8 },
            { symbol: 'GOOGL', name: 'Alphabet Inc.', value: 156789.01, change: 1.5 },
            { symbol: 'AMZN', name: 'Amazon.com Inc.', value: 145678.90, change: 3.2 },
          ].map((holding) => (
            <div key={holding.symbol} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                  <span className="text-xs font-bold text-blue-600">{holding.symbol[0]}</span>
                </div>
                <div>
                  <p className="font-medium text-gray-900">{holding.symbol}</p>
                  <p className="text-xs text-gray-500">{holding.name}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-medium text-gray-900">${(holding.value / 1000).toFixed(1)}K</p>
                <p className={`text-xs ${holding.change > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {holding.change > 0 ? '+' : ''}{holding.change}%
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DashboardGrid;
