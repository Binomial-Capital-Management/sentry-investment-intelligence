import { ChevronDown, Check } from 'lucide-react';
import { MODELS } from '@/config/models';
import type { ModelId } from '@/types';

interface ModelSelectorProps {
  selectedModel: ModelId;
  isModelMenuOpen: boolean;
  setIsModelMenuOpen: (open: boolean) => void;
  setSelectedModel: (model: ModelId) => void;
}

export function ModelSelector({
  selectedModel,
  isModelMenuOpen,
  setIsModelMenuOpen,
  setSelectedModel,
}: ModelSelectorProps) {
  const currentModel = MODELS[selectedModel];

  return (
    <div style={{ position: 'relative', display: 'flex' }}>
      <button
        onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          height: 32,
          padding: '0 12px',
          fontFamily: 'var(--cc-font-ui)',
          fontSize: '0.688rem',
          fontWeight: 500,
          color: 'hsl(var(--cc-text-000))',
          background: 'transparent',
          border: 'none',
          borderRadius: 6,
          cursor: 'pointer',
          transition: 'background-color 0.15s ease',
          minWidth: '4rem',
          maxWidth: 160,
        }}
        onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)')}
        onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        {currentModel?.logo && (
          <img src={currentModel.logo} alt="" style={{ width: 12, height: 12, objectFit: 'contain' }} />
        )}
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 100 }}>
          {currentModel?.name || 'Select Model'}
        </span>
        <ChevronDown style={{ width: 12, height: 12, flexShrink: 0, color: 'hsl(var(--cc-text-400))', transition: 'transform 200ms ease', transform: isModelMenuOpen ? 'rotate(180deg)' : 'rotate(0deg)' }} />
      </button>

      {isModelMenuOpen && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setIsModelMenuOpen(false)} />
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            marginBottom: 4,
            width: 200,
            backgroundColor: 'hsl(var(--cc-bg-000))',
            border: '0.5px solid hsl(var(--cc-border-200) / 30%)',
            borderRadius: 'var(--cc-radius-2xl)',
            boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
            zIndex: 50,
            padding: '0.375rem',
            maxHeight: 240,
            overflowY: 'auto',
          }}>
            {Object.values(MODELS).filter(m => m.available).map((model) => (
              <button
                key={model.id}
                onClick={() => {
                  setSelectedModel(model.id);
                  setIsModelMenuOpen(false);
                }}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '0.375rem 0.5rem',
                  fontFamily: 'var(--cc-font-ui)',
                  fontSize: '0.688rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  background: selectedModel === model.id ? 'hsl(var(--cc-bg-200))' : 'transparent',
                  color: selectedModel === model.id ? 'hsl(var(--cc-text-000))' : 'hsl(var(--cc-text-200))',
                  fontWeight: selectedModel === model.id ? 500 : 400,
                  border: 'none',
                  borderRadius: 'var(--cc-radius-lg)',
                  cursor: 'pointer',
                  transition: 'background-color 0.1s ease',
                }}
                className="cc-btn-ghost"
              >
                {model.logo && (
                  <img src={model.logo} alt="" style={{ width: 14, height: 14, objectFit: 'contain', flexShrink: 0 }} />
                )}
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                  {model.name}
                </span>
                {selectedModel === model.id && (
                  <Check style={{ width: 12, height: 12, color: 'hsl(var(--cc-accent-main-000))', flexShrink: 0 }} />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
