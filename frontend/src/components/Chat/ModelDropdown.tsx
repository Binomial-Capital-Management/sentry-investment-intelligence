import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { useChatStore } from '@stores/chatStore';
import { MODELS, getModelById } from '@/config/models';
import type { ModelId } from '@/types';

const ModelDropdown: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { getCurrentThreadModel, setSelectedModel } = useChatStore();
  const selectedModel = getCurrentThreadModel();

  const currentModel = getModelById(selectedModel);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleModelSelect = (modelId: ModelId) => {
    const model = MODELS[modelId];
    if (model.available) {
      setSelectedModel(modelId);
      setIsOpen(false);
    }
  };

  // Group models by category
  const fastModels = Object.values(MODELS).filter(m => m.category === 'fast');
  const versatileModels = Object.values(MODELS).filter(m => m.category === 'versatile');
  const powerfulModels = Object.values(MODELS).filter(m => m.category === 'powerful');
  const searchModels = Object.values(MODELS).filter(m => m.category === 'search');

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 12px',
          fontSize: '14px',
          background: isOpen ? '#F5F5F5' : 'transparent',
          border: '1px solid #E5E5E5',
          cursor: 'pointer',
          color: '#323130',
          borderRadius: '6px',
          transition: 'all 0.2s',
          fontWeight: '500',
        }}
        onMouseEnter={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = '#FAFAFA';
            e.currentTarget.style.borderColor = '#D1D1D1';
          }
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = '#E5E5E5';
          }
        }}
      >
        <img
          src={currentModel.logo}
          alt={currentModel.name}
          style={{ width: '20px', height: '20px', borderRadius: '4px' }}
        />
        <span>{currentModel.name}</span>
        <ChevronDown 
          size={14} 
          style={{ 
            opacity: 0.5,
            transition: 'transform 0.2s ease',
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          }} 
        />
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            width: '316px',
            background: '#FFFFFF',
            border: '1px solid #D4D4D4',
            borderRadius: '4px',
            boxShadow: '0 10px 26px rgba(0, 0, 0, 0.09)',
            zIndex: 1000,
            maxHeight: '396px',
            overflowY: 'auto',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '7px 11px',
              borderBottom: '1px solid #E2E2E2',
              fontSize: '11px',
              fontWeight: '700',
              color: '#2F2F2F',
              letterSpacing: '-0.01em',
            }}
          >
            Models
          </div>

          {/* Fast and cost-efficient */}
          {fastModels.length > 0 && (
            <>
              <div
                style={{
                  padding: '5px 11px 2px',
                  fontSize: '10px',
                  color: '#8A8A8A',
                  fontWeight: '600',
                  textTransform: 'uppercase',
                  letterSpacing: '0.03em',
                }}
              >
                Fast and cost-efficient
              </div>
              {fastModels.map((model) => (
                <ModelOption
                  key={model.id}
                  model={model}
                  isSelected={selectedModel === model.id}
                  onSelect={handleModelSelect}
                />
              ))}
            </>
          )}

          {/* Versatile and highly intelligent */}
          {versatileModels.length > 0 && (
            <>
              <div
                style={{
                  padding: '5px 11px 2px',
                  fontSize: '10px',
                  color: '#8A8A8A',
                  fontWeight: '600',
                  textTransform: 'uppercase',
                  letterSpacing: '0.03em',
                }}
              >
                Versatile and highly intelligent
              </div>
              {versatileModels.map((model) => (
                <ModelOption
                  key={model.id}
                  model={model}
                  isSelected={selectedModel === model.id}
                  onSelect={handleModelSelect}
                />
              ))}
            </>
          )}

          {/* Most powerful at complex tasks */}
          {powerfulModels.length > 0 && (
            <>
              <div
                style={{
                  padding: '5px 11px 2px',
                  fontSize: '10px',
                  color: '#8A8A8A',
                  fontWeight: '600',
                  textTransform: 'uppercase',
                  letterSpacing: '0.03em',
                }}
              >
                Most powerful at complex tasks
              </div>
              {powerfulModels.map((model) => (
                <ModelOption
                  key={model.id}
                  model={model}
                  isSelected={selectedModel === model.id}
                  onSelect={handleModelSelect}
                />
              ))}
            </>
          )}

          {/* Search models */}
          {searchModels.length > 0 && (
            <>
              <div
                style={{
                  padding: '5px 11px 2px',
                  fontSize: '10px',
                  color: '#8A8A8A',
                  fontWeight: '600',
                  textTransform: 'uppercase',
                  letterSpacing: '0.03em',
                }}
              >
                Search models
              </div>
              {searchModels.map((model) => (
                <ModelOption
                  key={model.id}
                  model={model}
                  isSelected={selectedModel === model.id}
                  onSelect={handleModelSelect}
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};

interface ModelOptionProps {
  model: any;
  isSelected: boolean;
  onSelect: (modelId: ModelId) => void;
}

const ModelOption: React.FC<ModelOptionProps> = ({ model, isSelected, onSelect }) => {
  const [isHovered, setIsHovered] = useState(false);

  // Check if this model has code execution limitations (Claude/Gemini/Grok)
  const isClaudeModel = model.id && (
    model.id.includes('anthropic') ||
    model.id.includes('claude')
  );
  const isGeminiModel = model.id && model.id.includes('gemini');
  const isGrokModel = model.id && (
    model.id.includes('xai') ||
    model.id.includes('grok')
  );
  const isDeepSeekModel = model.id && model.id.includes('deepseek');
  const isBedrockModel = model.id && (
    model.id.includes('bedrock') ||
    model.id.includes('llama4')
  );
  const isMoonshotModel = model.id && (model.id.includes('moonshot') || model.id.includes('kimi'));
  const isQwenModel = model.id && (model.id.includes('dashscope') || model.id.includes('qwen'));
  const isZaiModel = model.id && (model.id.includes('zai') || model.id.includes('glm'));

  return (
    <div
      onClick={() => onSelect(model.id)}
      onMouseEnter={() => model.available && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        padding: '5px 10px',
        cursor: model.available ? 'pointer' : 'default',
        background: isSelected ? '#EEF5FF' : isHovered ? '#FAFAFA' : 'transparent',
        opacity: model.available ? 1 : 0.4,
        transition: 'background 0.15s ease',
        borderRadius: isSelected ? '3px' : '0',
        margin: isSelected ? '2px 5px' : '0',
        border: isSelected ? '1px solid #D7E8FF' : '1px solid transparent',
      }}
    >
      {isSelected && (
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#2B6FD3"
          strokeWidth="2.5"
          style={{ flexShrink: 0, marginRight: '8px' }}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      )}
      {!isSelected && <div style={{ width: '24px' }} />}

      <img
        src={model.logo}
        alt={model.name}
        style={{
          width: '17px',
          height: '17px',
          borderRadius: '3px',
          marginRight: '7px',
        }}
      />

      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span
            style={{
              fontSize: '11px',
              color: model.available ? '#2F2F2F' : '#8B8A89',
              fontWeight: isSelected ? '600' : '500',
              letterSpacing: '-0.01em',
            }}
          >
            {model.name}
          </span>
          {!model.available && (
            <span
              style={{
                fontSize: '9px',
                color: '#8B8A89',
                padding: '1px 4px',
                background: '#F3F3F3',
                borderRadius: '3px',
                fontWeight: '600',
                letterSpacing: '0.02em',
              }}
            >
              Coming soon
            </span>
          )}
          {model.available && (isClaudeModel || isGeminiModel || isGrokModel || isDeepSeekModel || isBedrockModel || isMoonshotModel || isQwenModel || isZaiModel) && (
            <span
              style={{
                fontSize: '9px',
                color: '#7E7E7E',
                padding: '1px 4px',
                background: '#F2F2F2',
                borderRadius: '3px',
                fontWeight: '500',
                letterSpacing: '0.02em',
              }}
            >
              Beta
            </span>
          )}
        </div>
        {model.description && (
          <div
            style={{
              fontSize: '9px',
              color: '#868686',
              marginTop: '1px',
              lineHeight: 1.18,
            }}
          >
            {model.description}
          </div>
        )}
        {model.contextLimit && (
          <div
            style={{
              fontSize: '9px',
              color: '#696969',
              marginTop: '1px',
              fontStyle: 'italic',
            }}
          >
            {model.contextLimit}
          </div>
        )}
      </div>
    </div>
  );
};

export default ModelDropdown;
