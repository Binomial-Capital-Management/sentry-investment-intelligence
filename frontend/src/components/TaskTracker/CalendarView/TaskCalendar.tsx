import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import { format, parse, startOfWeek, getDay } from 'date-fns';
import { enUS } from 'date-fns/locale';
import { CalendarEvent } from './CalendarEvent';
import { CustomToolbar } from './CustomToolbar';
import type { Task } from '@/types/task.types';
import '@/styles/calendar.css';

const locales = { 'en-US': enUS };
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

interface TaskCalendarProps {
  tasks: Task[];
  onTaskClick: (task: Task) => void;
}

export function TaskCalendar({ tasks, onTaskClick }: TaskCalendarProps) {
  const events = tasks
    .filter((task) => task.dueDate)
    .map((task) => ({
      id: task.id,
      title: task.title,
      start: new Date(task.dueDate!),
      end: new Date(task.dueDate!),
      allDay: true, // Force all-day visual style like Google Calendar top bars
      resource: task,
    }));

  return (
    <div className="h-full bg-white rounded-2xl shadow-sm border border-gray-200/60 overflow-hidden flex flex-col">
      <div className="flex-1 p-6">
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          views={['month', 'week', 'day', 'agenda']}
          defaultView="month"
          components={{
            event: CalendarEvent,
            toolbar: CustomToolbar,
          }}
          onSelectEvent={(event) => {
            const task = event.resource as Task;
            onTaskClick(task);
          }}
          style={{ height: '100%' }}
          eventPropGetter={(event) => {
            const task = event.resource as Task;

            // Google Calendar style pastel colors based on type
            let backgroundColor = '#3b82f6'; // default blue
            let borderColor = '#2563eb';
            let textColor = '#1e3a8a';

            switch (task.type) {
                case 'research':
                    backgroundColor = '#dbeafe'; // blue-100
                    borderColor = '#bfdbfe'; // blue-200
                    textColor = '#1e40af'; // blue-800
                    break;
                case 'meeting':
                    backgroundColor = '#f3e8ff'; // purple-100
                    borderColor = '#e9d5ff'; // purple-200
                    textColor = '#6b21a8'; // purple-800
                    break;
                case 'committee':
                    backgroundColor = '#ffedd5'; // orange-100
                    borderColor = '#fed7aa'; // orange-200
                    textColor = '#9a3412'; // orange-800
                    break;
                case 'filing':
                    backgroundColor = '#fee2e2'; // red-100
                    borderColor = '#fecaca'; // red-200
                    textColor = '#991b1b'; // red-800
                    break;
                default:
                    backgroundColor = '#f1f5f9'; // slate-100
                    borderColor = '#e2e8f0'; // slate-200
                    textColor = '#334155'; // slate-700
                    break;
            }

            return {
              style: {
                backgroundColor,
                color: textColor,
                borderLeft: `3px solid ${borderColor}`, // Left border accent like Google
                borderTop: 'none',
                borderRight: 'none',
                borderBottom: 'none',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: '600',
                padding: '2px 6px',
                margin: '1px 0',
                boxShadow: '0 1px 1px rgba(0,0,0,0.05)',
              },
            };
          }}
        />
      </div>
    </div>
  );
}
