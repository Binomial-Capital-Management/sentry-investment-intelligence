/**
 * ToolWorkflowContent - Embeddable tool workflow that renders inside a workspace tab.
 *
 * Renders: progress bar, steps 1-4 content, footer (Back/Continue/Run/Save).
 * Does NOT render: header, AI chat panel — the workspace shell handles those.
 *
 * State is backed by the Zustand store via useToolTab(tabId).
 */

import { useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ToolCatalog as ToolMarketplace, ToolParamsForm as SchemaForm } from './components';
import { TickerPicker } from '@/features/canvas/shared/symbol-search';
import { STEPS } from '@/features/canvas/types';
import type { Step } from '@/features/canvas/types';
import { useToolTab } from './hooks/useToolTab';
import ToolResultsContent from './components/ToolResultsContent';

interface ToolWorkflowContentProps {
  tabId: string;
  /** Optional process ID to load on mount */
  loadProcessId?: string | null;
}

export default function ToolWorkflowContent({ tabId, loadProcessId }: ToolWorkflowContentProps) {
  const { isLoaded } = useAuth();
  const hook = useToolTab(tabId);

  const {
    toolState,
    update,
    tools,
    loadingTools,
    portfolios,
    loadingPortfolios,
    selectedTool,
    inputType,
    canProceed,
    runningTime,
    loadingProcess,
    setStep,
    runTool,
    fetchProcess,
  } = hook;

  const {
    toolStep: step,
    toolId: selectedToolId,
    manualTickers,
    selectedPortfolioId,
    toolParams,
    activeResultId,
    error,
    isRunning,
  } = toolState;

  const result = (toolState.toolResults ?? []).find(r => r.localId === activeResultId)?.result ?? null;

  // Load process on mount if loadProcessId provided
  useEffect(() => {
    if (loadProcessId && isLoaded && !loadingTools) {
      fetchProcess(loadProcessId);
    }
  }, [loadProcessId, isLoaded, loadingTools, fetchProcess]);

  // Note: AI-initiated tool analyses (tool-analysis-complete events) are handled
  // by the workspace-level listener in DataWorkspace.tsx, which creates a NEW tab.
  // ToolWorkflowContent does not listen for these events to avoid overwriting
  // the current tab's results.

  const handleBack = () => {
    if (step > 1) {
      setStep((step - 1) as Step);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Progress Bar */}
      <div className="bg-white border-b border-slate-200 px-4 sm:px-6 py-3 flex-shrink-0">
        <div className="flex items-center justify-between max-w-2xl mx-auto">
          {STEPS.map((s, i) => (
            <div key={s.num} className="flex items-center min-w-0">
              <div
                className={`w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-medium flex-shrink-0
                ${step >= s.num ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-500'}`}
              >
                {step > s.num ? (
                  <svg className="w-3 h-3 sm:w-3.5 sm:h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  s.num
                )}
              </div>
              <span className={`ml-1.5 sm:ml-2 text-[10px] sm:text-xs font-medium truncate ${step >= s.num ? 'text-slate-900' : 'text-slate-400'}`}>
                {s.label}
              </span>
              {i < 3 && <div className={`flex-1 min-w-4 max-w-12 h-px mx-2 sm:mx-3 ${step > s.num ? 'bg-slate-900' : 'bg-slate-200'}`} />}
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6 min-w-0">
        <div className={step === 4 ? '' : 'max-w-4xl mx-auto'}>
          {/* Loading */}
          {loadingProcess && (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="w-6 h-6 border-2 border-slate-200 border-t-slate-600 rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-slate-500">Loading process...</p>
              </div>
            </div>
          )}

          {/* Step 1: Tool Selection */}
          {step === 1 && !loadingProcess && (
            <ToolMarketplace
              tools={tools}
              selectedToolId={selectedToolId}
              onSelect={(id: string) => update({ toolId: id })}
              loading={loadingTools}
            />
          )}

          {/* Step 2: Data */}
          {step === 2 && !loadingProcess && (
            <div className="max-w-lg mx-auto space-y-4">
              {inputType === 'none' ? (
                <div className="text-center py-10 bg-white rounded border border-slate-200">
                  <div className="w-10 h-10 rounded bg-slate-100 flex items-center justify-center mx-auto mb-3">
                    <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                    </svg>
                  </div>
                  <p className="text-sm text-slate-600">This tool analyzes market-wide data automatically.</p>
                </div>
              ) : inputType === 'single_ticker' ? (
                <div className="bg-white rounded border border-slate-200 p-5">
                  <TickerPicker
                    mode="single"
                    selectedSymbols={manualTickers ? [manualTickers] : []}
                    onSelect={(t) => update({ manualTickers: t.symbol, selectedPortfolioId: '' })}
                    placeholder="Select ticker..."
                  />
                </div>
              ) : inputType === 'tickers' ? (
                <div className="bg-white rounded border border-slate-200 p-5">
                  {(() => {
                    const tickers = manualTickers.split(/[,\s]+/).filter(Boolean);
                    return (
                      <TickerPicker
                        mode="multi"
                        selectedSymbols={tickers}
                        onSelect={(t) => update({ manualTickers: [...tickers, t.symbol].join(', ') })}
                        onRemove={(sym) => update({ manualTickers: tickers.filter(x => x !== sym).join(', ') })}
                        placeholder="Select tickers..."
                        maxTickers={10}
                      />
                    );
                  })()}
                </div>
              ) : (
                <>
                  <div className="bg-white rounded border border-slate-200 p-5">
                    <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">Your Portfolios</div>
                    {loadingPortfolios ? (
                      <p className="text-slate-400 text-center py-6 text-xs">Loading...</p>
                    ) : portfolios.length === 0 ? (
                      <p className="text-slate-400 text-center py-6 text-xs">No portfolios</p>
                    ) : (
                      <div className="space-y-2 max-h-48 overflow-auto">
                        {portfolios.map(p => (
                          <button
                            key={p.id}
                            onClick={() => update({ selectedPortfolioId: p.id, manualTickers: '' })}
                            className={`w-full p-3 border rounded text-left flex justify-between items-center transition-colors
                              ${selectedPortfolioId === p.id ? 'bg-slate-900 border-slate-900 text-white' : 'border-slate-200 hover:border-slate-400'}`}
                          >
                            <div>
                              <div className="font-medium text-sm">{p.name}</div>
                              <div className={`text-xs ${selectedPortfolioId === p.id ? 'text-slate-400' : 'text-slate-500'}`}>
                                {p.tickers.slice(0, 4).join(', ')}{p.tickers.length > 4 && ` +${p.tickers.length - 4}`}
                              </div>
                            </div>
                            {selectedPortfolioId === p.id && (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-px bg-slate-200" />
                    <span className="text-xs text-slate-400">or</span>
                    <div className="flex-1 h-px bg-slate-200" />
                  </div>
                  <div className="bg-white rounded border border-slate-200 p-5">
                    {(() => {
                      const tickers = manualTickers.split(/[,\s]+/).filter(Boolean).map(t => t.toUpperCase());
                      return (
                        <TickerPicker
                          mode="multi"
                          selectedSymbols={tickers}
                          onSelect={(t) => update({ manualTickers: [...tickers, t.symbol].join(', '), selectedPortfolioId: '' })}
                          onRemove={(sym) => update({ manualTickers: tickers.filter(x => x !== sym).join(', '), selectedPortfolioId: '' })}
                          placeholder="Select tickers..."
                          maxTickers={20}
                        />
                      );
                    })()}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 3: Config */}
          {step === 3 && selectedTool && !loadingProcess && (
            <div className="max-w-lg mx-auto">
              <div className="bg-white rounded border border-slate-200 p-5">
                <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-4">
                  {selectedTool.name} Parameters
                </div>
                <SchemaForm
                  schema={selectedTool.params_schema || {}}
                  values={toolParams}
                  onChange={(v: Record<string, any>) => update({ toolParams: v })}
                  excludeFields={['portfolio_id', 'tickers', 'weights', 'ticker', 'underlying']}
                  portfolios={portfolios}
                />
              </div>
              {error && (
                <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded text-red-600 text-xs">{error}</div>
              )}
            </div>
          )}

          {/* Step 4: Results */}
          {step === 4 && activeResultId && result && !loadingProcess && (
            <ToolResultsContent tabId={tabId} resultLocalId={activeResultId} />
          )}
        </div>
      </div>

      {/* Footer — hidden at step 4 since results are already part of workspace */}
      {step < 4 && (
        <footer className="bg-white border-t border-slate-200 px-6 py-3 flex justify-between flex-shrink-0">
          <button
            onClick={handleBack}
            disabled={step === 1}
            className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Back
          </button>
          <button
            onClick={() => (step === 3 ? runTool() : setStep((step + 1) as Step))}
            disabled={!canProceed || isRunning}
            className="px-4 py-2 text-xs font-medium bg-slate-900 text-white rounded disabled:opacity-40 hover:bg-slate-800 transition-colors"
          >
            {isRunning ? `Running... ${runningTime}s` : step === 3 ? 'Run Analysis' : 'Continue'}
          </button>
        </footer>
      )}
    </div>
  );
}
