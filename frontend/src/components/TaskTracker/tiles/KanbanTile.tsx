import { useReview } from '../mosaic/ReviewContext';
import { KanbanBoard } from '../KanbanView/KanbanBoard';
import { TaskFilters } from '../Shared/TaskFilters';

export default function KanbanTile() {
  const { filteredTasks, setSearchTerm, setPriorityFilter, setStatusFilter, onTaskClick, onCreateTask } = useReview();
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #f3f4f6', flexShrink: 0 }}>
        <TaskFilters onSearchChange={setSearchTerm} onPriorityFilter={setPriorityFilter} onStatusFilter={setStatusFilter} />
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
        <KanbanBoard tasks={filteredTasks} onTaskClick={onTaskClick} onCreateTask={onCreateTask} />
      </div>
    </div>
  );
}
