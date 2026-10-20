import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { Text } from './Typography';

// Colorful filled icons matching sidebar style
const ColorfulIcons = {
  Search: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="#6b7280"/>
    </svg>
  ),
  Chat: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" fill="#3b82f6"/>
      <circle cx="8" cy="11" r="1.5" fill="#ffffff"/>
      <circle cx="12" cy="11" r="1.5" fill="#ffffff"/>
      <circle cx="16" cy="11" r="1.5" fill="#ffffff"/>
    </svg>
  ),
  Plus: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" fill="#10b981"/>
      <path d="M12 8v8M8 12h8" stroke="white" strokeWidth={2} strokeLinecap="round"/>
    </svg>
  ),
  Settings: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58z" fill="#6b7280"/>
      <circle cx="12" cy="12" r="3" fill="#9ca3af"/>
    </svg>
  ),
  User: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="#3b82f6"/>
    </svg>
  ),
  Chart: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z" fill="#8b5cf6"/>
      <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z" fill="none" stroke="#8b5cf6" strokeWidth="2"/>
    </svg>
  ),
  TrendingUp: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6h-6z" fill="#10b981"/>
    </svg>
  ),
  Shield: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z" fill="#10b981"/>
    </svg>
  ),
  Dollar: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z" fill="#f59e0b"/>
    </svg>
  ),
  Document: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6z" fill="#6366f1"/>
      <path d="M14 2v6h6" fill="#ffffff"/>
    </svg>
  ),
  Code: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z" fill="#ec4899"/>
    </svg>
  ),
  Briefcase: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M20 7h-4V5l-2-2h-4L8 5v2H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zm-10 2c0-.55.45-1 1-1h2c.55 0 1 .45 1 1v9h-4V9zM10 5h4v2h-4V5z" fill="#92400e"/>
      <rect x="11" y="11" width="2" height="3" fill="#fbbf24"/>
    </svg>
  ),
  Building: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z" fill="#f59e0b"/>
    </svg>
  ),
};

// Command interface
interface Command {
  id: string;
  label: string;
  description?: string;
  icon: React.ComponentType<any>;
  action: () => void;
  shortcut?: string;
  category: 'navigation' | 'actions' | 'tools' | 'settings';
  keywords?: string[];
}

// Command categories for organization
const COMMAND_CATEGORIES = {
  navigation: 'Navigation',
  actions: 'Actions',
  tools: 'Tools',
  settings: 'Settings',
};

// Props interface
interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  commands?: Command[];
  placeholder?: string;
  className?: string;
}

// Default commands - these can be customized per app
const DEFAULT_COMMANDS: Command[] = [
  // Navigation
  {
    id: 'nav-chat',
    label: 'Go to Chat',
    description: 'AI-powered investment analysis chat',
    icon: ColorfulIcons.Chat,
    action: () => window.location.href = '/chat',
    category: 'navigation',
    keywords: ['chat', 'ai', 'assistant', 'conversation', 'analysis'],
  },
  {
    id: 'nav-portfolio',
    label: 'Go to Portfolios',
    description: 'Manage and analyze your portfolios',
    icon: ColorfulIcons.TrendingUp,
    action: () => window.location.href = '/portfolio',
    category: 'navigation',
    keywords: ['portfolio', 'holdings', 'positions', 'management'],
  },
  {
    id: 'nav-workflows',
    label: 'Go to Workflows',
    description: 'Visual workflow builder for custom analysis',
    icon: ColorfulIcons.Chart,
    action: () => window.location.href = '/workflows',
    category: 'navigation',
    keywords: ['workflow', 'automation', 'builder', 'visual'],
  },

  // Actions
  {
    id: 'action-new-chat',
    label: 'New Chat Thread',
    description: 'Start a new conversation',
    icon: ColorfulIcons.Plus,
    action: async () => {
      const { useChatStore } = await import('@stores/chatStore');
      const createNewThread = useChatStore.getState().createNewThread;
      await createNewThread('New Chat');
      window.location.href = '/chat';
    },
    shortcut: '⌘J',
    category: 'actions',
    keywords: ['new', 'chat', 'thread', 'conversation'],
  },
  {
    id: 'action-new-portfolio',
    label: 'Create Portfolio',
    description: 'Add a new portfolio',
    icon: ColorfulIcons.Plus,
    action: () => {
      window.location.href = '/portfolio';
      setTimeout(() => {
        const createBtn = document.querySelector('[data-action="create-portfolio"]') as HTMLElement;
        createBtn?.click();
      }, 300);
    },
    category: 'actions',
    keywords: ['new', 'portfolio', 'create', 'add'],
  },

  // Tools - AI Agents (all 9)
  {
    id: 'tool-risk-specialist',
    label: 'Risk Specialist',
    description: 'VaR, Monte Carlo, optimization',
    icon: ColorfulIcons.Shield,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Calculate VaR for my default portfolio';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['risk', 'var', 'monte carlo', 'optimization', 'hedge', 'barra'],
  },
  {
    id: 'tool-comparable-companies',
    label: 'Comparable Companies',
    description: 'Peer valuation & multiples',
    icon: ColorfulIcons.Building,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Analyze comparable companies for AAPL';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['comps', 'valuation', 'multiples', 'peers', 'comparable'],
  },
  {
    id: 'tool-document-analyst',
    label: 'Document Analyst',
    description: 'SEC filings & documents',
    icon: ColorfulIcons.Document,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Analyze the latest 10-K for AAPL';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['document', 'sec', '10-k', '10-q', 'filing', 'earnings'],
  },
  {
    id: 'tool-dcf-agent',
    label: 'DCF Valuation',
    description: 'Discounted cash flow models',
    icon: ColorfulIcons.Dollar,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Build a DCF model for AAPL';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['dcf', 'valuation', 'cash flow', 'intrinsic value', 'wacc'],
  },
  {
    id: 'tool-institutional-activity',
    label: 'Institutional Activity',
    description: '13F filings, insider trading',
    icon: ColorfulIcons.Briefcase,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Show institutional holdings for AAPL';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['institutional', '13f', 'insider', 'holdings', 'smart money'],
  },
  {
    id: 'tool-quant-coding',
    label: 'Quant Coding',
    description: 'Python code interpreter',
    icon: ColorfulIcons.Code,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Write Python code to calculate Sharpe ratio';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['code', 'python', 'quant', 'programming', 'custom', 'interpreter'],
  },
  {
    id: 'tool-alternatives-coding',
    label: 'Alternatives Coding',
    description: 'Alternative investments code',
    icon: ColorfulIcons.Code,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Analyze alternative investment strategies';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['alternatives', 'code', 'crypto', 'commodities', 'real estate'],
  },
  {
    id: 'tool-chart-analyst',
    label: 'Chart Analyst',
    description: 'Financial charts & viz',
    icon: ColorfulIcons.Chart,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.value = 'Create a price chart for AAPL over the last year';
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['chart', 'graph', 'visualization', 'plot', 'technical'],
  },
  {
    id: 'tool-main-agent',
    label: 'General Assistant',
    description: 'Conversational AI & data',
    icon: ColorfulIcons.Chat,
    action: () => {
      window.location.href = '/chat';
      setTimeout(() => {
        const input = document.querySelector('textarea[placeholder*="message"]') as HTMLTextAreaElement;
        if (input) {
          input.focus();
        }
      }, 500);
    },
    category: 'tools',
    keywords: ['general', 'assistant', 'main', 'conversation', 'chat', 'data'],
  },

  // Settings
  {
    id: 'settings-account',
    label: 'Manage Account',
    description: 'Profile, password, security & 2FA',
    icon: ColorfulIcons.User,
    action: () => {
      // Trigger the user menu dropdown which has the Manage Account button
      const userMenuButton = document.querySelector('button[aria-label*="user"]') as HTMLElement;
      if (userMenuButton) {
        userMenuButton.click();
        setTimeout(() => {
          const manageAccountBtn = Array.from(document.querySelectorAll('button'))
            .find(btn => btn.textContent?.includes('Manage Account')) as HTMLElement;
          manageAccountBtn?.click();
        }, 100);
      }
    },
    category: 'settings',
    keywords: ['account', 'profile', 'user', 'settings', 'password', 'security', '2fa'],
  },
  {
    id: 'settings-preferences',
    label: 'Settings',
    description: 'App preferences & configuration',
    icon: ColorfulIcons.Settings,
    action: () => window.location.href = '/settings',
    category: 'settings',
    keywords: ['settings', 'preferences', 'config', 'configuration'],
  },
];

// Fuzzy search utility
const fuzzySearch = (query: string, commands: Command[]): Command[] => {
  if (!query.trim()) return commands;

  const normalizedQuery = query.toLowerCase().trim();

  return commands
    .map(command => {
      let score = 0;

      // Check label match
      if (command.label.toLowerCase().includes(normalizedQuery)) {
        score += 100;
      }

      // Check description match
      if (command.description?.toLowerCase().includes(normalizedQuery)) {
        score += 50;
      }

      // Check keywords match
      if (command.keywords?.some(keyword => keyword.toLowerCase().includes(normalizedQuery))) {
        score += 75;
      }

      // Check for partial matches
      const labelWords = command.label.toLowerCase().split(' ');
      const queryWords = normalizedQuery.split(' ');

      queryWords.forEach(queryWord => {
        labelWords.forEach(labelWord => {
          if (labelWord.startsWith(queryWord)) {
            score += 25;
          }
        });
      });

      return { command, score };
    })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .map(({ command }) => command);
};

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  commands = DEFAULT_COMMANDS,
  placeholder = 'Type a command or search...',
  className = '',
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter commands based on search query
  const filteredCommands = useMemo(() => {
    return fuzzySearch(query, commands);
  }, [query, commands]);

  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, Command[]> = {};

    filteredCommands.forEach(command => {
      if (!groups[command.category]) {
        groups[command.category] = [];
      }
      groups[command.category].push(command);
    });

    return groups;
  }, [filteredCommands]);

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev =>
            prev < filteredCommands.length - 1 ? prev + 1 : 0,
          );
          break;

        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev =>
            prev > 0 ? prev - 1 : filteredCommands.length - 1,
          );
          break;

        case 'Enter':
          e.preventDefault();
          if (filteredCommands[selectedIndex]) {
            filteredCommands[selectedIndex].action();
            onClose();
          }
          break;

        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, onClose]);

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen, onClose]);

  // Scroll selected item into view
  useEffect(() => {
    const selectedElement = document.querySelector('.command-item.selected');
    if (selectedElement) {
      selectedElement.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'var(--overlay-backdrop)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          paddingTop: '15vh',
        }}
      >
        <motion.div
          ref={containerRef}
          initial={{ opacity: 0, scale: 0.95, y: -20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
          className={`command-palette ${className}`}
          style={{
            width: '90%',
            maxWidth: '640px',
            maxHeight: '60vh',
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(0, 0, 0, 0.05)',
            overflow: 'hidden',
          }}
        >
          {/* Search Input */}
          <div
            style={{
              padding: '20px 24px',
              borderBottom: '1px solid #f3f4f6',
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
              background: '#fafafa',
            }}
          >
            <ColorfulIcons.Search />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder}
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                background: 'transparent',
                fontSize: '15px',
                color: '#111827',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
                fontWeight: 500,
              }}
            />
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                backgroundColor: '#ffffff',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#6b7280',
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              ⌘K
            </div>
          </div>

          {/* Results */}
          <div
            style={{
              maxHeight: 'calc(60vh - 80px)',
              overflowY: 'auto',
              padding: '12px',
            }}
          >
            {filteredCommands.length === 0 ? (
              <div
                style={{
                  padding: '64px 24px',
                  textAlign: 'center',
                }}
              >
                <div style={{
                  fontSize: '14px',
                  color: '#9ca3af',
                  fontWeight: 500,
                }}>
                  No commands found
                </div>
                <div style={{
                  fontSize: '12px',
                  color: '#d1d5db',
                  marginTop: '4px',
                }}>
                  Try a different search term
                </div>
              </div>
            ) : (
              Object.entries(groupedCommands).map(([category, categoryCommands]) => (
                <div key={category}>
                  {/* Category Header */}
                  <div
                    style={{
                      padding: '12px 12px 8px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    <Text
                      variant="overline"
                      color="muted"
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: '#9ca3af',
                      }}
                    >
                      {COMMAND_CATEGORIES[category as keyof typeof COMMAND_CATEGORIES]}
                    </Text>
                  </div>

                  {/* Commands */}
                  {categoryCommands.map((command) => {
                    const globalIndex = filteredCommands.indexOf(command);
                    const isSelected = globalIndex === selectedIndex;

                    return (
                      <motion.div
                        key={command.id}
                        className={`command-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          command.action();
                          onClose();
                        }}
                        style={{
                          padding: '12px 12px',
                          margin: '2px 0',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          backgroundColor: isSelected ? '#f3f4f6' : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          transition: 'all 0.15s ease',
                          border: isSelected ? '1px solid #e5e7eb' : '1px solid transparent',
                        }}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                        whileHover={{
                          backgroundColor: '#f9fafb',
                          scale: 1.01,
                        }}
                      >
                        <div style={{ flexShrink: 0 }}>
                          <command.icon />
                        </div>

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: '14px',
                            fontWeight: 500,
                            color: isSelected ? '#111827' : '#374151',
                            marginBottom: command.description ? '2px' : 0,
                          }}>
                            {command.label}
                          </div>
                          {command.description && (
                            <div style={{
                              fontSize: '12px',
                              color: '#9ca3af',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}>
                              {command.description}
                            </div>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                          {command.shortcut && (
                            <div style={{
                              padding: '3px 8px',
                              backgroundColor: '#ffffff',
                              border: '1px solid #e5e7eb',
                              borderRadius: '5px',
                              fontSize: '11px',
                              fontWeight: 600,
                              color: '#6b7280',
                            }}>
                              {command.shortcut}
                            </div>
                          )}
                          <ArrowRight
                            size={14}
                            style={{
                              color: '#9ca3af',
                              opacity: isSelected ? 1 : 0,
                              transition: 'opacity 0.15s ease',
                            }}
                          />
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

// Hook for command palette keyboard shortcut
export const useCommandPalette = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen(prev => !prev),
  };
};

export default CommandPalette;
