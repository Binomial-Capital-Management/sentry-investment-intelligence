import React, { useState, useRef, useEffect, useCallback } from "react";
import { PlusIcon } from "@phosphor-icons/react";
import { Tooltip } from "../../Tooltip";
import { Upload, Globe, Database, BookIcon, BriefcaseIcon, CheckmarkIcon } from "../shared";

interface PortfolioInfo {
  id: string;
  name: string;
  tickers: string[];
}

interface PlusMenuProps {
  onFileUploadClick: () => void;
  webSearchEnabled: boolean;
  onWebSearchToggle: () => void;
  bloombergEnabled?: boolean;
  onBloombergToggle?: (enabled: boolean) => void;
  portfolios?: PortfolioInfo[];
  selectedPortfolioId?: string | null;
  onPortfolioChange?: (id: string | null) => void;
  showMemory: boolean;
  onToggleMemory: () => void;
}

export const PlusMenu: React.FC<PlusMenuProps> = ({
  onFileUploadClick,
  webSearchEnabled,
  onWebSearchToggle,
  bloombergEnabled,
  onBloombergToggle,
  portfolios,
  selectedPortfolioId,
  onPortfolioChange,
  showMemory,
  onToggleMemory,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isSubMenuOpen, setIsSubMenuOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
        setIsSubMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  const close = useCallback(() => { setIsOpen(false); setIsSubMenuOpen(false); }, []);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <Tooltip label="More options" side="top">
        <button
          onClick={() => { if (isOpen) { close(); } else { setIsOpen(true); } }}
          className="btn btn-ghost"
          style={{
            width: "32px", height: "32px", borderRadius: "6px",
            background: isOpen ? "hsl(var(--bg-300))" : undefined,
          }}
          aria-label="More options"
        >
          <PlusIcon size={16} weight="regular" />
        </button>
      </Tooltip>

      {isOpen && (
        <div style={{
          position: "absolute", zIndex: 50, bottom: "100%", left: 0, marginBottom: "8px",
          background: "hsl(var(--bg-000))", border: "0.5px solid hsl(var(--border-300) / 15%)",
          borderRadius: "12px", boxShadow: "0 4px 12px 0 rgba(0,0,0,0.08)", padding: "6px",
          width: "220px", color: "hsl(var(--text-300))",
        }}>
          {!isSubMenuOpen ? (
            <>
              {/* Upload file */}
              <button
                onClick={() => { close(); onFileUploadClick(); }}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                    <Upload />
                  </div>
                  <div className="font-base" style={{ color: "hsl(var(--text-200))" }}>Upload File</div>
                </div>
              </button>

              {/* Web search toggle */}
              <button
                onClick={onWebSearchToggle}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                    <Globe />
                  </div>
                  <div className="font-base" style={{ flex: 1, color: "hsl(var(--text-200))" }}>Search the web</div>
                  {webSearchEnabled && <CheckmarkIcon />}
                </div>
              </button>

              {/* Sources sub-menu entry */}
              <button
                onClick={() => setIsSubMenuOpen(true)}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                    <Database />
                  </div>
                  <div className="font-base" style={{ flex: 1, color: "hsl(var(--text-200))" }}>Sources</div>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" style={{ color: "hsl(var(--text-400))", flexShrink: 0 }}>
                    <path d="M181.66,133.66l-80,80a8,8,0,0,1-11.32-11.32L164.69,128,90.34,53.66a8,8,0,0,1,11.32-11.32l80,80A8,8,0,0,1,181.66,133.66Z"></path>
                  </svg>
                </div>
              </button>
            </>
          ) : (
            <>
              {/* Back button */}
              <button
                onClick={() => setIsSubMenuOpen(false)}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256">
                      <path d="M165.66,202.34a8,8,0,0,1-11.32,11.32l-80-80a8,8,0,0,1,0-11.32l80-80a8,8,0,0,1,11.32,11.32L91.31,128Z"></path>
                    </svg>
                  </div>
                  <div className="font-base" style={{ color: "hsl(var(--text-200))" }}>Back</div>
                </div>
              </button>

              <div style={{ height: "1px", background: "hsl(var(--border-300) / 15%)", margin: "4px 0" }} />

              {/* Data source selector */}
              <div className="font-caption" style={{ padding: "4px 10px", color: "hsl(var(--text-400))" }}>Data Source</div>
              <button
                onClick={() => { onBloombergToggle?.(false); }}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ width: "16px", height: "16px", borderRadius: "2px", background: "hsl(var(--bg-300))", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "8px", fontWeight: 700, flexShrink: 0 }}>S</span>
                  <div className="font-base" style={{ flex: 1, color: "hsl(var(--text-200))" }}>Sentry</div>
                  {!bloombergEnabled && <CheckmarkIcon />}
                </div>
              </button>
              <button
                onClick={() => { onBloombergToggle?.(true); }}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <img src={require("../../../../assets/bbg_logo.png")} alt="" style={{ width: "16px", height: "16px", objectFit: "contain", borderRadius: "2px", flexShrink: 0 }} />
                  <div className="font-base" style={{ flex: 1, color: "hsl(var(--text-200))" }}>Bloomberg</div>
                  {bloombergEnabled && <CheckmarkIcon />}
                </div>
              </button>

              {/* Portfolio selector */}
              {portfolios && portfolios.length > 0 && (
                <>
                  <div style={{ height: "1px", background: "hsl(var(--border-300) / 15%)", margin: "4px 0" }} />
                  <div className="font-caption" style={{ padding: "4px 10px", color: "hsl(var(--text-400))" }}>Portfolio</div>
                  <button
                    onClick={() => { onPortfolioChange?.(null); }}
                    style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer", fontStyle: "italic" }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                        <BriefcaseIcon />
                      </div>
                      <div className="font-base" style={{ flex: 1, color: "hsl(var(--text-200))" }}>No portfolio</div>
                      {!selectedPortfolioId && <CheckmarkIcon />}
                    </div>
                  </button>
                  {portfolios.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => { onPortfolioChange?.(p.id); }}
                      style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                      onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                      onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                          <BriefcaseIcon />
                        </div>
                        <div className="font-base truncate" style={{ flex: 1, color: "hsl(var(--text-200))" }}>{p.name}</div>
                        {selectedPortfolioId === p.id ? (
                          <CheckmarkIcon />
                        ) : (
                          <span style={{ fontSize: "9px", color: "hsl(var(--text-400))" }}>{p.tickers.length}</span>
                        )}
                      </div>
                    </button>
                  ))}
                </>
              )}

              {/* Memory notebook */}
              <div style={{ height: "1px", background: "hsl(var(--border-300) / 15%)", margin: "4px 0" }} />
              <button
                onClick={() => { onToggleMemory(); close(); }}
                style={{ width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px", transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--text-300))", flexShrink: 0, width: "16px", height: "16px" }}>
                    <BookIcon />
                  </div>
                  <div className="font-base" style={{ flex: 1, color: "hsl(var(--text-200))" }}>Memory Notebook</div>
                  {showMemory && <CheckmarkIcon />}
                </div>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};
