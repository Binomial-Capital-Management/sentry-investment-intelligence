import { useState, useRef, useEffect, useCallback } from 'react';

const C = {
  text:       'hsl(60 2.5% 23.3%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  borderSel:  '0.5px solid hsl(30 3.3% 11.8% / 15%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
  bgHover:    'hsl(30 3.3% 11.8% / 5%)',
} as const;

export interface SelectOption {
  value: string;
  label: string;
  group?: string;
}

interface Props {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
}

export function CustomSelect({ value, options, onChange, placeholder }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const selected = options.find(o => o.value === value);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  useEffect(() => {
    if (open) requestAnimationFrame(updateFades);
  }, [open, updateFades]);

  const groups = new Map<string, SelectOption[]>();
  for (const opt of options) {
    const g = opt.group || '';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(opt);
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          height: 26,
          padding: '0.2rem 0.5rem',
          fontSize: '0.563rem',
          fontWeight: 500,
          textAlign: 'left' as const,
          border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
          borderRadius: '0.375rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.25rem',
          color: selected ? C.text : C.textFaint,
          backgroundColor: 'white',
          cursor: 'pointer',
        }}
      >
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selected?.label || placeholder || 'Select...'}
        </span>
        <svg
          style={{ width: 8, height: 8, color: C.textFaint, flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div style={{
          marginTop: 2,
          backgroundColor: 'white',
          borderRadius: '0.5rem',
          border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
          position: 'relative',
          overflow: 'hidden',
          zIndex: 10,
        }}>
          {showTopFade && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 16, background: 'linear-gradient(to bottom, white, transparent)', zIndex: 1, pointerEvents: 'none', borderRadius: '0.5rem 0.5rem 0 0' }} />}
          <div
            ref={scrollRef}
            onScroll={updateFades}
            style={{ maxHeight: 160, overflowY: 'auto', padding: '0.25rem' }}
          >
            {[...groups.entries()].map(([groupName, groupOpts]) => (
              <div key={groupName}>
                {groupName && (
                  <div style={{ fontSize: '0.5rem', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.04em', color: C.textGhost, padding: '0.25rem 0.375rem 0.125rem', marginTop: groupName !== [...groups.keys()][0] ? '0.25rem' : 0 }}>
                    {groupName}
                  </div>
                )}
                {groupOpts.map(opt => {
                  const isSelected = value === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => { onChange(opt.value); setOpen(false); }}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.375rem',
                        padding: '0.25rem 0.375rem',
                        fontSize: '0.563rem',
                        border: 'none',
                        borderRadius: '0.25rem',
                        backgroundColor: isSelected ? C.bgActive : 'transparent',
                        color: isSelected ? C.text : C.textMuted,
                        cursor: 'pointer',
                        textAlign: 'left' as const,
                        transition: 'all 0.1s ease',
                      }}
                      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.backgroundColor = C.bgHover; }}
                      onMouseLeave={e => { e.currentTarget.style.backgroundColor = isSelected ? C.bgActive : 'transparent'; }}
                    >
                      <span style={{ fontWeight: isSelected ? 600 : 400 }}>{opt.label}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          {showBottomFade && <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 16, background: 'linear-gradient(to top, white, transparent)', zIndex: 1, pointerEvents: 'none', borderRadius: '0 0 0.5rem 0.5rem' }} />}
        </div>
      )}
    </div>
  );
}
