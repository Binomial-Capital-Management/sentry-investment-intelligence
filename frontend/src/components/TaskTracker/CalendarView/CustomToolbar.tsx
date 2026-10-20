import type { ToolbarProps } from 'react-big-calendar';

export function CustomToolbar(props: ToolbarProps) {
  const { label, onNavigate, onView, view, views } = props;

  const goToBack = () => {
    onNavigate('PREV');
  };

  const goToNext = () => {
    onNavigate('NEXT');
  };

  const goToCurrent = () => {
    onNavigate('TODAY');
  };

  return (
    <div className="flex items-center justify-between mb-6 px-1">
      <div className="flex items-center gap-4">
        <div className="flex items-center bg-gray-100/80 rounded-lg p-1 border border-gray-200/50">
            <button
            onClick={goToCurrent}
            className="px-3 py-1 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-sm rounded-md transition-all"
            >
            Today
            </button>
            <div className="w-px h-4 bg-gray-300 mx-1" />
            <div className="flex items-center gap-0.5">
                <button
                onClick={goToBack}
                className="p-1 hover:bg-white hover:text-gray-900 text-gray-500 rounded-md transition-all hover:shadow-sm"
                title="Previous"
                >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
                </button>
                <button
                onClick={goToNext}
                className="p-1 hover:bg-white hover:text-gray-900 text-gray-500 rounded-md transition-all hover:shadow-sm"
                title="Next"
                >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6"/></svg>
                </button>
            </div>
        </div>

        <h2 className="text-lg font-semibold text-gray-900 tracking-tight">
          {label}
        </h2>
      </div>

      <div className="flex items-center bg-gray-100/80 p-1 rounded-lg border border-gray-200/50">
        {(views as string[]).map((viewName) => (
          <button
            key={viewName}
            onClick={() => onView(viewName as any)}
            className={`
              px-3 py-1 text-sm font-medium rounded-md transition-all
              ${
                view === viewName
                  ? 'bg-white text-gray-900 shadow-sm ring-1 ring-black/5'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'
              }
            `}
          >
            {viewName.charAt(0).toUpperCase() + viewName.slice(1)}
          </button>
        ))}
      </div>
    </div>
  );
}
