/**
 * ModeSelector - Data type toggle tabs (Stock/ETF, Forex, Crypto, etc.)
 */

interface ModeOption<T extends string> {
  mode: T;
  label: string;
  color?: string;
}

interface ModeSelectorProps<T extends string> {
  modes: ModeOption<T>[];
  selectedMode: T;
  onModeChange: (mode: T) => void;
  label?: string;
}

export default function ModeSelector<T extends string>({
  modes,
  selectedMode,
  onModeChange,
  label = 'Data Type',
}: ModeSelectorProps<T>) {
  return (
    <div className="p-4 pb-2 border-b border-slate-100">
      <label className="block text-xs font-medium text-slate-600 mb-1.5">{label}</label>
      <div className="flex flex-wrap gap-1">
        {modes.map(({ mode, label: modeLabel }) => {
          const isActive = selectedMode === mode;
          return (
            <button
              key={mode}
              onClick={() => onModeChange(mode)}
              className={`px-2 py-1 text-[10px] font-medium rounded transition-colors ${
                isActive ? 'bg-slate-200 text-slate-700' : 'text-slate-400 hover:bg-slate-100'
              }`}
            >
              {modeLabel}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type { ModeOption };
