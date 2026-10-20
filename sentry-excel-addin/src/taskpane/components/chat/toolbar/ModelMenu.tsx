import React, { useState, useRef, useEffect } from "react";
import { getModelById, getAvailableModels } from "../../../../shared/models";

interface ModelMenuProps {
  selectedModel: string;
  onModelChange: (modelId: string) => void;
}

export const ModelMenu: React.FC<ModelMenuProps> = ({ selectedModel, onModelChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  const currentModel = getModelById(selectedModel);
  const availableModels = getAvailableModels();

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="btn btn-secondary font-small"
        style={{
          height: "32px", borderRadius: "6px", padding: "0 12px",
          display: "flex", alignItems: "center", gap: "6px",
          minWidth: "4rem", maxWidth: "160px",
        }}
        title={currentModel.name}
      >
        <span className="truncate" style={{ minWidth: 0, fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' }}>{currentModel.name}</span>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 256 256" style={{ flexShrink: 0, color: 'hsl(var(--text-400))', transition: 'transform 200ms ease', transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          <path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z"></path>
        </svg>
      </button>

      {isOpen && (
        <div className="dropdown-menu align-right" style={{ minWidth: "200px" }}>
          {availableModels.map((model) => (
            <button
              key={model.id}
              onClick={() => { onModelChange(model.id); setIsOpen(false); }}
              className="dropdown-item-grid"
            >
              <span className="truncate">{model.name}</span>
              {selectedModel === model.id && (
                <svg width="16" height="16" viewBox="0 0 256 256" fill="currentColor" className="dropdown-checkmark">
                  <path d="M229.66,77.66l-128,128a8,8,0,0,1-11.32,0l-56-56a8,8,0,0,1,11.32-11.32L96,188.69,218.34,66.34a8,8,0,0,1,11.32,11.32Z" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
