import { useState, useRef, useEffect } from 'react';
import { Folder, X, MoreHorizontal } from 'lucide-react';
import { useChatStore } from '@stores/chatStore';
import { usePortfolioStore } from '@stores/portfolioStore';

const PortfolioSelector = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const { selectedChatPortfolioId, setSelectedChatPortfolioId } = useChatStore();
  const { savedPortfolios, loadPortfolios } = usePortfolioStore();

  // Load portfolios on mount
  useEffect(() => {
    loadPortfolios();
  }, [loadPortfolios]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Find selected portfolio
  const selectedPortfolio = savedPortfolios.find(p => p.id === selectedChatPortfolioId);

  // If a portfolio is selected, show it as a pill like ChatGPT's file attachment
  if (selectedPortfolio) {
    return (
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '4px 8px',
        background: '#f3f4f6',
        border: '1px solid #d1d5db',
        borderRadius: '12px',
        fontSize: '14px',
        color: '#6b7280',
        maxWidth: '200px',
      }}>
        <Folder size={12} />
        <span style={{
          fontWeight: 500,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {selectedPortfolio.name}
        </span>

        {/* X button to remove */}
        <button
          type="button"
          onClick={() => setSelectedChatPortfolioId(null)}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '0',
            marginLeft: '4px',
            color: '#6b7280',
            fontSize: '16px',
            lineHeight: '1',
          }}
          title="Remove portfolio"
        >
          ×
        </button>
      </div>
    );
  }

  // When no portfolio is selected, return null (button will be in the bottom row)
  return null;
};

export default PortfolioSelector;
