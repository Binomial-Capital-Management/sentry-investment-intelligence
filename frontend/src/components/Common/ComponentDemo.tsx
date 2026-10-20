import React from 'react';
import { DataTable, DataTableColumn } from './DataTable';
import { CommandPalette, useCommandPalette } from './CommandPalette';
import { Heading, Text } from './Typography';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// Sample portfolio data for demonstration
interface PortfolioHolding {
  symbol: string;
  name: string;
  shares: number;
  price: number;
  marketValue: number;
  dayChange: number;
  dayChangePercent: number;
  weight: number;
}

const sampleData: PortfolioHolding[] = [
  {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    shares: 150,
    price: 182.52,
    marketValue: 27378,
    dayChange: 2.45,
    dayChangePercent: 1.36,
    weight: 0.274,
  },
  {
    symbol: 'MSFT',
    name: 'Microsoft Corporation',
    shares: 85,
    price: 378.85,
    marketValue: 32202.25,
    dayChange: -5.23,
    dayChangePercent: -1.36,
    weight: 0.322,
  },
  {
    symbol: 'GOOGL',
    name: 'Alphabet Inc.',
    shares: 45,
    price: 138.21,
    marketValue: 6219.45,
    dayChange: 0.00,
    dayChangePercent: 0.00,
    weight: 0.062,
  },
  {
    symbol: 'AMZN',
    name: 'Amazon.com Inc.',
    shares: 25,
    price: 151.94,
    marketValue: 3798.50,
    dayChange: 1.87,
    dayChangePercent: 1.25,
    weight: 0.038,
  },
  {
    symbol: 'TSLA',
    name: 'Tesla Inc.',
    shares: 120,
    price: 248.50,
    marketValue: 29820,
    dayChange: -12.45,
    dayChangePercent: -4.77,
    weight: 0.298,
  },
];

// Custom render function for change indicators
const renderChange = (value: number, _row: PortfolioHolding) => {
  const isPositive = value > 0;
  const isNegative = value < 0;
  // const isNeutral = value === 0;

  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  const color = isPositive ? 'var(--success)' : isNegative ? 'var(--danger)' : 'var(--text-muted)';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end' }}>
      <Icon size={14} style={{ color }} />
      <span style={{ color, fontFamily: 'var(--font-mono-institutional)' }}>
        {Math.abs(value).toFixed(2)}%
      </span>
    </div>
  );
};

// Table columns configuration
const columns: DataTableColumn<PortfolioHolding>[] = [
  {
    key: 'symbol',
    label: 'Symbol',
    align: 'left',
    sortable: true,
    width: 80,
  },
  {
    key: 'name',
    label: 'Name',
    align: 'left',
    sortable: true,
  },
  {
    key: 'shares',
    label: 'Shares',
    align: 'right',
    format: 'number',
    sortable: true,
    width: 100,
  },
  {
    key: 'price',
    label: 'Price',
    align: 'right',
    format: 'currency',
    sortable: true,
    width: 120,
  },
  {
    key: 'marketValue',
    label: 'Market Value',
    align: 'right',
    format: 'currency',
    sortable: true,
    width: 140,
  },
  {
    key: 'dayChange',
    label: 'Day Change',
    align: 'right',
    format: 'currency',
    sortable: true,
    width: 120,
  },
  {
    key: 'dayChangePercent',
    label: 'Day Change %',
    align: 'right',
    sortable: true,
    width: 120,
    render: renderChange,
  },
  {
    key: 'weight',
    label: 'Weight',
    align: 'right',
    format: 'percentage',
    sortable: true,
    width: 100,
  },
];

export const ComponentDemo: React.FC = () => {
  const commandPalette = useCommandPalette();

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <Heading level="h1" style={{ marginBottom: '8px' }}>
          Component Demo
        </Heading>
        <Text variant="lead" color="secondary">
          Demonstration of DataTable and CommandPalette components with institutional design patterns.
        </Text>
        <div style={{ marginTop: '16px' }}>
          <Text variant="body-sm" color="muted">
            Press <kbd style={{
              padding: '2px 6px',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: '3px',
              fontFamily: 'var(--font-mono-institutional)',
              fontSize: 'var(--fs-base)',
            }}>⌘ + K</kbd> to open the command palette
          </Text>
        </div>
      </div>

      {/* DataTable Demo Section */}
      <div style={{ marginBottom: '48px' }}>
        <Heading level="h2" style={{ marginBottom: '16px' }}>
          Portfolio Holdings - Dense Data Table
        </Heading>
        <Text variant="body" color="secondary" style={{ marginBottom: '24px' }}>
          Professional data table with sorting, formatting, hover states, and monospace numbers.
          Features 32px row height for density, right-aligned financial data, and subtle zebra striping.
        </Text>

        <DataTable
          columns={columns}
          data={sampleData}
          density="compact"
          sortable={true}
          zebra={true}
          stickyHeader={false}
        />
      </div>

      {/* Features List */}
      <div style={{ marginBottom: '48px' }}>
        <Heading level="h2" style={{ marginBottom: '16px' }}>
          Features Demonstrated
        </Heading>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '24px',
        }}>
          <div style={{
            padding: '20px',
            backgroundColor: 'var(--bg-surface)',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
          }}>
            <Heading level="h4" style={{ marginBottom: '8px' }}>
              DataTable Features
            </Heading>
            <ul style={{
              margin: 0,
              paddingLeft: '16px',
              color: 'var(--text-secondary)',
              fontSize: '13px',
              lineHeight: 1.5,
            }}>
              <li>Right-aligned monospace numbers</li>
              <li>Sortable columns with visual indicators</li>
              <li>28-32px compact row height</li>
              <li>Custom render functions</li>
              <li>Multiple format types (currency, percentage, etc.)</li>
              <li>Loading skeleton states</li>
              <li>Hover effects and zebra striping</li>
              <li>Empty state handling</li>
            </ul>
          </div>

          <div style={{
            padding: '20px',
            backgroundColor: 'var(--bg-surface)',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
          }}>
            <Heading level="h4" style={{ marginBottom: '8px' }}>
              CommandPalette Features
            </Heading>
            <ul style={{
              margin: 0,
              paddingLeft: '16px',
              color: 'var(--text-secondary)',
              fontSize: '13px',
              lineHeight: 1.5,
            }}>
              <li>⌘/Ctrl + K keyboard activation</li>
              <li>Fuzzy search with scoring</li>
              <li>Keyboard navigation (arrows, enter, escape)</li>
              <li>Categorized commands</li>
              <li>Visual shortcuts display</li>
              <li>Click outside to close</li>
              <li>Smooth animations</li>
              <li>Customizable command sets</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Usage Instructions */}
      <div style={{
        padding: '24px',
        backgroundColor: 'var(--accent-subtle)',
        borderRadius: '8px',
        border: '1px solid color-mix(in oklab, var(--accent), transparent 80%)',
      }}>
        <Heading level="h3" style={{ marginBottom: '12px' }}>
          Integration Usage
        </Heading>
        <Text variant="body" style={{ marginBottom: '16px' }}>
          These components follow institutional design patterns and can be used throughout the application:
        </Text>
        <div style={{
          fontFamily: 'var(--font-mono-institutional)',
          fontSize: 'var(--fs-base)',
          backgroundColor: 'var(--bg-card)',
          padding: '16px',
          borderRadius: '4px',
          marginTop: '12px',
          color: 'var(--text-primary)',
        }}>
          {`// DataTable usage
<DataTable
  columns={portfolioColumns}
  data={portfolioData}
  density="compact"
  sortable={true}
/>

// CommandPalette integration
const palette = useCommandPalette();
<CommandPalette 
  isOpen={palette.isOpen} 
  onClose={palette.close}
  commands={customCommands}
/>`}
        </div>
      </div>

      {/* Command Palette */}
      <CommandPalette
        isOpen={commandPalette.isOpen}
        onClose={commandPalette.close}
      />
    </div>
  );
};

export default ComponentDemo;
