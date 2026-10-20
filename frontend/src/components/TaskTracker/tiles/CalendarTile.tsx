import { useReview } from '../mosaic/ReviewContext';
import { TaskCalendar } from '../CalendarView/TaskCalendar';
import { TaskFilters } from '../Shared/TaskFilters';

export default function CalendarTile() {
  const { filteredTasks, setSearchTerm, setPriorityFilter, setStatusFilter, onTaskClick } = useReview();
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #f3f4f6', flexShrink: 0 }}>
        <TaskFilters onSearchChange={setSearchTerm} onPriorityFilter={setPriorityFilter} onStatusFilter={setStatusFilter} />
      </div>
      <div style={{ flex: 1, overflow: 'hidden', padding: '12px 16px' }}>
        <TaskCalendar tasks={filteredTasks} onTaskClick={onTaskClick} />
      </div>
    </div>
  );
}
