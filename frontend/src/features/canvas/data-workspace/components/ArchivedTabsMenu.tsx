import { useState, useRef, useCallback } from 'react';
import { Archive, ChevronDown, Trash2 } from 'lucide-react';
import type { ArchivedTab } from '../hooks/useTabPersistence';

interface ArchivedTabsMenuProps {
  archivedTabs: ArchivedTab[];
  onOpen: () => void;
  onRestore: (processId: string) => void;
  onPermanentDelete: (processId: string) => void;
}

const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';
const BG_300 = '210 10% 87%';
const TEXT_100 = '60 2.6% 7.6%';

const ghostBtnCSS = `
.archived-menu-item:hover:not(:disabled) { background-color: hsl(${BG_300}) !important; color: hsl(${TEXT_100}) !important; }
.archived-menu-item:active:not(:disabled) { background-color: hsl(${BG_300}) !important; }
`;

function formatRelativeDate(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function ArchivedTabsMenu({
  archivedTabs,
  onOpen,
  onRestore,
  onPermanentDelete,
}: ArchivedTabsMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const [canScrollUp, setCanScrollUp] = useState(false);
  const [canScrollDown, setCanScrollDown] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const updateScrollFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollUp(el.scrollTop > 2);
    setCanScrollDown(el.scrollTop + el.clientHeight < el.scrollHeight - 2);
  }, []);

  const handleToggle = () => {
    if (!isOpen) {
      onOpen();
      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        const zoom = 1.2;
        setMenuPos({ top: rect.bottom / zoom + 2, left: rect.left / zoom });
      }
    }
    setIsOpen(!isOpen);
  };

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleToggle}
        className="flex items-center gap-1.5 px-2.5 h-7 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
        style={{
          fontFamily: FONT_UI,
          backgroundColor: isOpen ? 'rgba(0,0,0,0.1)' : 'transparent',
          color: `hsl(${TEXT_200} / 85%)`,
        }}
        onMouseEnter={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.backgroundColor = 'rgba(0,0,0,0.1)'; }}
        onMouseLeave={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
        title="Archived tabs"
      >
        <Archive size={13} strokeWidth={2} style={{ color: `hsl(${TEXT_200} / 60%)` }} />
        <span className="truncate">Archived</span>
        <ChevronDown
          size={13}
          strokeWidth={2}
          className={`flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          style={{ color: `hsl(${TEXT_200} / 45%)` }}
        />
      </button>

      {isOpen && (
        <>
          <style>{ghostBtnCSS}</style>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div
            style={{
              position: 'fixed',
              top: menuPos.top,
              left: menuPos.left,
              width: 240,
              backgroundColor: '#fff',
              border: `0.5px solid hsl(${BORDER_200} / 30%)`,
              borderRadius: '1rem',
              boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
              zIndex: 50,
              padding: '0.375rem',
            }}
          >
            <div style={{
              padding: '0.375rem 0.625rem 0.25rem',
              fontSize: '0.563rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: `hsl(${TEXT_200} / 35%)`,
              fontFamily: FONT_UI,
              fontWeight: 600,
            }}>
              Archived Tabs
            </div>

            <div style={{ position: 'relative' }}>
              {canScrollUp && (
                <div style={{
                  position: 'absolute', top: 0, left: 0, right: 0, height: 24,
                  background: 'linear-gradient(to bottom, white, transparent)',
                  zIndex: 1, pointerEvents: 'none', borderRadius: '0.5rem 0.5rem 0 0',
                }} />
              )}
              {canScrollDown && (
                <div style={{
                  position: 'absolute', bottom: 0, left: 0, right: 0, height: 24,
                  background: 'linear-gradient(to top, white, transparent)',
                  zIndex: 1, pointerEvents: 'none', borderRadius: '0 0 0.5rem 0.5rem',
                }} />
              )}
              <div
                ref={(el) => { (scrollRef as any).current = el; if (el) requestAnimationFrame(updateScrollFades); }}
                onScroll={updateScrollFades}
                style={{ overflow: 'auto', maxHeight: 320 }}
              >
                {archivedTabs.length === 0 ? (
                  <div style={{
                    padding: '1.5rem 0.625rem',
                    textAlign: 'center',
                    fontSize: '0.688rem',
                    color: `hsl(${TEXT_200} / 40%)`,
                    fontFamily: FONT_UI,
                  }}>
                    No archived tabs
                  </div>
                ) : (
                  archivedTabs.map(tab => (
                    <div key={tab.id}>
                      <button
                        className="archived-menu-item group"
                        onClick={() => { if (confirmDeleteId !== tab.id) { onRestore(tab.id); setIsOpen(false); } }}
                        style={{
                          width: '100%',
                          padding: '0.375rem 0.625rem',
                          fontFamily: FONT_UI,
                          fontSize: '0.688rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          color: `hsl(${TEXT_200})`,
                          background: 'transparent',
                          border: 'none',
                          borderRadius: '0.5rem',
                          cursor: 'pointer',
                          textAlign: 'left',
                          transition: 'background-color 0.1s ease',
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontWeight: 500,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }} title={tab.name}>
                            {tab.name}
                          </div>
                          <div style={{
                            fontSize: '0.563rem',
                            color: `hsl(${TEXT_200} / 40%)`,
                            marginTop: 1,
                          }}>
                            {formatRelativeDate(tab.archivedAt)}
                            {tab.datasetCount > 0 && ` · ${tab.datasetCount} datasets`}
                          </div>
                        </div>

                        <div
                          onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(tab.id); }}
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                          style={{
                            padding: 3,
                            borderRadius: '0.375rem',
                            color: `hsl(${TEXT_200} / 40%)`,
                            flexShrink: 0,
                            cursor: 'pointer',
                            transition: 'background-color 0.1s ease, color 0.1s ease',
                          }}
                          onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'hsl(0 60% 95%)'; e.currentTarget.style.color = 'hsl(0 55% 44%)'; }}
                          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = `hsl(${TEXT_200} / 40%)`; }}
                          title="Delete permanently"
                        >
                          <Trash2 size={12} />
                        </div>
                      </button>
                      {confirmDeleteId === tab.id && (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.375rem 0.625rem',
                          fontSize: '0.563rem',
                          fontFamily: FONT_UI,
                          color: 'hsl(0 55% 44%)',
                        }}>
                          <span>Delete permanently?</span>
                          <div style={{ display: 'flex', gap: '0.25rem' }}>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              style={{
                                padding: '0.125rem 0.5rem',
                                fontSize: '0.563rem',
                                fontFamily: FONT_UI,
                                borderRadius: '0.375rem',
                                border: `0.5px solid hsl(${BORDER_200} / 15%)`,
                                background: 'transparent',
                                color: `hsl(${TEXT_200} / 60%)`,
                                cursor: 'pointer',
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => { onPermanentDelete(tab.id); setConfirmDeleteId(null); }}
                              style={{
                                padding: '0.125rem 0.5rem',
                                fontSize: '0.563rem',
                                fontFamily: FONT_UI,
                                borderRadius: '0.375rem',
                                border: 'none',
                                background: 'hsl(0 55% 44%)',
                                color: '#fff',
                                cursor: 'pointer',
                              }}
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
