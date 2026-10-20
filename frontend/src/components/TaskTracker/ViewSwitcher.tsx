import type { ViewMode } from '@/types/task.types';

interface ViewSwitcherProps {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export function ViewSwitcher({ mode, onChange }: ViewSwitcherProps) {
  return (
    <div className="flex items-center bg-gray-100/80 p-1 rounded-full border border-gray-200/50">
      <button
        onClick={() => onChange('post_mortems')}
        className={`
          px-4 py-1.5 text-sm font-medium rounded-full transition-all duration-200
          ${
            mode === 'post_mortems'
              ? 'bg-white text-gray-900 shadow-sm ring-1 ring-black/5'
              : 'text-gray-500 hover:text-gray-700'
          }
        `}
      >
        Post Mortems
      </button>
      <button
        disabled
        className="px-4 py-1.5 text-sm font-medium rounded-full transition-all duration-200 text-gray-300 cursor-not-allowed"
      >
        Calendar
      </button>
      <button
        disabled
        className="px-4 py-1.5 text-sm font-medium rounded-full transition-all duration-200 text-gray-300 cursor-not-allowed"
      >
        Board
      </button>
    </div>
  );
}
