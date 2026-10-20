import { useState, useEffect } from 'react';
import { portfolioApiService } from '../../../services/portfolioApi';
import type { PortfolioOption } from '../types';

interface Props {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}

export default function PortfolioCheckboxList({ selectedIds, onChange }: Props) {
  const [portfolios, setPortfolios] = useState<PortfolioOption[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPortfolios = async () => {
      try {
        const data = await portfolioApiService.listPortfolios();
        setPortfolios(data.map(p => ({
          id: p.id,
          name: p.name,
          value: p.value || 0,
        })));
      } catch (error) {
        console.error('Failed to fetch portfolios:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchPortfolios();
  }, []);

  const handleToggle = (id: string, checked: boolean) => {
    if (checked) {
      onChange([...selectedIds, id]);
    } else {
      onChange(selectedIds.filter(pid => pid !== id));
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.length === portfolios.length) {
      onChange([]);
    } else {
      onChange(portfolios.map(p => p.id));
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="text-center py-4">
        <div className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  if (portfolios.length === 0) {
    return <div className="text-xs text-gray-500">No portfolios found</div>;
  }

  return (
    <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded p-3 bg-gray-50/50">
      {portfolios.map(portfolio => (
        <label
          key={portfolio.id}
          className="flex items-center justify-between p-2 rounded hover:bg-white cursor-pointer transition-colors"
        >
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={selectedIds.includes(portfolio.id)}
              onChange={(e) => handleToggle(portfolio.id, e.target.checked)}
              className="w-3.5 h-3.5 text-gray-900 rounded border-gray-300 focus:ring-gray-900 focus:ring-offset-0"
            />
            <span className="text-sm font-medium text-gray-900">{portfolio.name}</span>
          </div>
          <span className="text-xs text-gray-500">{formatCurrency(portfolio.value)}</span>
        </label>
      ))}

      {portfolios.length > 1 && (
        <button
          onClick={handleSelectAll}
          className="text-xs text-blue-600 hover:text-blue-700 font-medium mt-2 w-full text-left pl-2"
        >
          {selectedIds.length === portfolios.length ? 'Deselect All' : 'Select All'}
        </button>
      )}
    </div>
  );
}
