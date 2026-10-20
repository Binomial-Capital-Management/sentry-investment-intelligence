import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, Edit, Play, Pause, Plus, Search, List as ListIcon, LayoutGrid, Calendar, Clock, Mail, Activity, HelpCircle } from 'lucide-react';
import { tasksApi } from '@/services/tasksApi';
import toast from 'react-hot-toast';
import type { Task } from '@/types/tasks';
import WorkspaceIndicator from '@/components/Common/WorkspaceIndicator';
import { TaskGuidePanel } from '@/components/Task/TaskGuidePanel';

export default function Tasks() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [guideOpen, setGuideOpen] = useState(false);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const data = await tasksApi.list();
      setTasks(data);
    } catch (err) {
      toast.error('Failed to load tasks');
      console.error('Failed to fetch tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
    try {
      await tasksApi.delete(id);
      fetchTasks();
      toast.success('Task deleted');
    } catch (err) {
      toast.error((err as any)?.message || 'Failed to delete task');
    }
  };

  const handleToggle = async (id: string) => {
    try {
      await tasksApi.toggle(id);
      fetchTasks();
      toast.success('Task status updated');
    } catch (err) {
      toast.error('Failed to update task status');
    }
  };

  const handleTrigger = async (id: string) => {
    try {
      await tasksApi.trigger(id);
      fetchTasks();
      toast.success('Task triggered successfully');
    } catch (err) {
      toast.error('Failed to trigger task');
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
           ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  const getStatusBadge = (status: string) => {
    if (status === 'active') {
      return (
        <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded text-[10px] font-bold uppercase border border-emerald-100">
          Active
        </span>
      );
    }
    if (status === 'paused') {
      return (
        <span className="px-2 py-0.5 bg-amber-50 text-amber-600 rounded text-[10px] font-bold uppercase border border-amber-100">
          Paused
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 bg-gray-50 text-gray-600 rounded text-[10px] font-bold uppercase border border-gray-100">
        {status}
      </span>
    );
  };

  const filteredTasks = tasks.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.description?.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="flex flex-col h-full bg-[#fafafa]">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Task Manager</h1>
            <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
              <span>Automated workflows and scheduled agents</span>
              <span className="text-gray-300">•</span>
              <WorkspaceIndicator size="sm" />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setGuideOpen(true)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
              title="Open Task Guide"
            >
              <HelpCircle className="w-5 h-5" />
            </button>
            <button
              onClick={() => navigate('/tasks/new')}
              style={{ backgroundColor: '#0051cc' }}
              className="px-4 py-2 text-white text-sm font-medium rounded-lg shadow-sm hover:shadow-md flex items-center gap-2 transition-all hover:opacity-90"
            >
              <Plus className="w-4 h-4" />
              Create Task
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          {/* Search */}
          <div className="relative max-w-md w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border-0 rounded-lg text-sm focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>

          {/* View Toggle */}
          <div className="flex items-center bg-gray-100 p-1 rounded-lg border border-gray-200/50">
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'list' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
              title="List View"
            >
              <ListIcon className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'grid' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
              title="Grid View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-8">
        {loading ? (
          <div className="flex items-center justify-center h-64">
             <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-96 bg-white rounded-2xl border border-gray-100 border-dashed">
            <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mb-4">
              <Activity className="w-5 h-5 text-gray-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">No tasks found</h3>
            <p className="text-gray-500 text-sm mt-1">
              {tasks.length === 0 ? 'Create your first automation task to get started.' : 'Try adjusting your search terms.'}
            </p>
          </div>
        ) : (
          <>
            {viewMode === 'grid' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {filteredTasks.map((task) => (
                  <div
                    key={task.id}
                    onClick={() => navigate(`/tasks/${task.id}`)}
                    className="group bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md hover:border-gray-300 transition-all duration-200 cursor-pointer relative overflow-hidden flex flex-col"
                  >
                    <div className="p-5 flex-1">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors truncate pr-2">
                            {task.name}
                          </h3>
                          <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
                            <Clock className="w-3 h-3" />
                            {task.frequency}
                          </div>
                        </div>
                        {getStatusBadge(task.status)}
                      </div>

                      <div className="mt-3 text-sm text-gray-600 line-clamp-2 min-h-[2.5em]">
                        {task.description || <span className="text-gray-400 italic">No description</span>}
                      </div>

                      <div className="mt-4 flex items-center gap-2 text-xs text-gray-500">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>Next: {formatDate(task.next_run_at)}</span>
                      </div>
                    </div>

                    <div className="px-5 py-3 bg-gray-50/50 border-t border-gray-100 flex items-center justify-between text-xs">
                      <span className="font-medium text-gray-500 truncate max-w-[120px]">
                        {task.email || 'No email'}
                      </span>

                      <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                         <button
                            onClick={(e) => { e.stopPropagation(); handleTrigger(task.id); }}
                            className="text-gray-400 hover:text-blue-600 transition-colors"
                            title="Run Now"
                         >
                            <Play className="w-3.5 h-3.5" />
                         </button>
                         <button
                            onClick={(e) => { e.stopPropagation(); handleToggle(task.id); }}
                            className="text-gray-400 hover:text-amber-600 transition-colors"
                            title={task.status === 'active' ? 'Pause' : 'Resume'}
                         >
                            {task.status === 'active' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                         </button>
                         <button
                            onClick={(e) => { e.stopPropagation(); handleDelete(task.id, task.name); }}
                            className="text-gray-400 hover:text-red-500 transition-colors"
                            title="Delete"
                         >
                            <Trash2 className="w-3.5 h-3.5" />
                         </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                <table className="w-full text-sm text-left border-collapse">
                  <thead className="bg-gray-50/80 text-gray-500 font-medium border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs w-1/4">Name</th>
                      <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs">Schedule</th>
                      <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs">Description</th>
                      <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-right">Last Run</th>
                      <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-right">Next Run</th>
                      <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredTasks.map((task) => (
                      <tr
                        key={task.id}
                        onClick={() => navigate(`/tasks/${task.id}`)}
                        className="hover:bg-gray-50/80 transition-colors cursor-pointer group"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div>
                              <div className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                                {task.name}
                              </div>
                              <div className="flex items-center gap-1.5 mt-1">
                                {getStatusBadge(task.status)}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2 text-gray-600 font-medium">
                            <Clock className="w-3.5 h-3.5 text-gray-400" />
                            <span className="capitalize">{task.frequency === 'custom' ? 'Custom' : task.frequency}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-gray-500 max-w-xs truncate">
                          {task.description || <span className="text-gray-400 italic">No description</span>}
                          {task.email && (
                            <div className="flex items-center gap-1.5 mt-1 text-xs text-gray-400">
                              <Mail className="w-3 h-3" />
                              {task.email}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right text-gray-500 font-mono text-xs">
                          {formatDate(task.last_run_at)}
                        </td>
                        <td className="px-6 py-4 text-right text-gray-900 font-mono text-xs font-medium">
                          {formatDate(task.next_run_at)}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleTrigger(task.id); }}
                              className="p-1.5 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded transition-colors"
                              title="Run Now"
                            >
                              <Play className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleToggle(task.id); }}
                              className="p-1.5 hover:bg-amber-50 text-gray-400 hover:text-amber-600 rounded transition-colors"
                              title={task.status === 'active' ? 'Pause' : 'Resume'}
                            >
                              {task.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}`); }}
                              className="p-1.5 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded transition-colors"
                              title="Edit"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(task.id, task.name); }}
                              className="p-1.5 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded transition-colors"
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Task Guide Panel */}
      <TaskGuidePanel
        isOpen={guideOpen}
        onClose={() => setGuideOpen(false)}
        context="list"
      />
    </div>
  );
}
