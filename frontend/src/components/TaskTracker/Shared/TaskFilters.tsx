import type { Task } from '@/types/task.types';

interface TaskFiltersProps {
  onSearchChange?: (search: string) => void;
  onPriorityFilter?: (priority: string | null) => void;
  onStatusFilter?: (status: string | null) => void;
}

export function TaskFilters({
  onSearchChange,
  onPriorityFilter,
  onStatusFilter,
}: TaskFiltersProps) {

  return (
    <div className="flex flex-wrap items-center gap-3 p-4">
      {/* Pill Search Input */}
      <div className="relative">
        <input
          type="text"
          onChange={(e) => onSearchChange?.(e.target.value)}
          placeholder="Search ticker, title..."
          className="w-64 pl-4 pr-9 py-2 text-sm text-gray-700 bg-white border-0 rounded-full shadow-sm ring-1 ring-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:shadow-md transition-all placeholder-gray-400"
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-300">
           <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        </div>
      </div>

      {/* Pill Selects */}
      <div className="relative">
        <select
            onChange={(e) => onPriorityFilter?.(e.target.value || null)}
            className="appearance-none py-2 pl-4 pr-8 text-sm font-medium text-gray-600 bg-white border-0 rounded-full shadow-sm ring-1 ring-gray-200 hover:ring-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-all"
        >
            <option value="">Priority</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
        </select>
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
        </div>
      </div>

      <div className="relative">
        <select
            onChange={(e) => onStatusFilter?.(e.target.value || null)}
            className="appearance-none py-2 pl-4 pr-8 text-sm font-medium text-gray-600 bg-white border-0 rounded-full shadow-sm ring-1 ring-gray-200 hover:ring-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-all"
        >
            <option value="">Stage</option>
            <option value="idea-generation">Idea Generation</option>
            <option value="due-diligence">Due Diligence</option>
            <option value="ic-review">IC Review</option>
            <option value="portfolio">Portfolio</option>
        </select>
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
        </div>
      </div>
    </div>
  );
}
