import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Play, Square, Database, BarChart3, Upload, Sparkles, Mail, FileText, Presentation, Cloud, MessageSquare, Users, BookOpen, ChevronDown, ChevronRight, Clock, Calendar as CalendarIcon, Globe, X, Tag, Merge, Split } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { customRepeatToCron, cronToCustomRepeat } from '@/utils/cronConverter';

interface NodeType {
  type: string;
  label: string;
  Icon: LucideIcon | null;
  logoPath: string | null;
  bgColor: string;
  iconColor: string;
  comingSoon?: boolean;
}

interface TaskSidebarProps {
  taskName: string;
  onTaskNameChange: (name: string) => void;
  description: string;
  onDescriptionChange: (desc: string) => void;
  frequency: string;
  onFrequencyChange: (freq: string) => void;
  cronExpression: string;  // Used for time strings like "02:30 PM"
  onCronExpressionChange: (cron: string) => void;
  customCronExpression: string;  // Used for actual cron expressions in 'custom' frequency
  onCustomCronExpressionChange: (cron: string) => void;
  email: string;
  onEmailChange: (email: string) => void;
  deliveryPreference: string;
  onDeliveryPreferenceChange: (pref: string) => void;
  onAddNode: (type: string) => void;
  // Additional settings
  selectedDate: Date | null;
  onSelectedDateChange: (date: Date | null) => void;
  timezone: string;
  onTimezoneChange: (tz: string) => void;
  tags: string[];
  onTagsChange: (tags: string[]) => void;
  selectedDays: number[];
  onSelectedDaysChange: (days: number[]) => void;
  dayOfMonth: number | null;  // Day of month for monthly frequency (1-31)
  onDayOfMonthChange: (day: number | null) => void;
}

// Custom Calendar Component
function MiniCalendar({ selectedDate, onDateSelect }: { selectedDate: Date | null; onDateSelect: (date: Date) => void }) {
  const [currentMonth, setCurrentMonth] = useState(new Date());

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const dayNames = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const days = [];
    for (let i = 0; i < firstDay; i++) {
      days.push(null);
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(year, month, i));
    }
    return days;
  };

  const days = getDaysInMonth(currentMonth);

  const isToday = (date: Date | null) => {
    if (!date) return false;
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  const isSelected = (date: Date | null) => {
    if (!date || !selectedDate) return false;
    return date.toDateString() === selectedDate.toDateString();
  };

  return (
    <div style={{
      background: '#FFFFFF',
      border: '1px solid #DADCE0',
      borderRadius: '8px',
      padding: '12px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
      width: '240px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <button
          onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '2px 6px',
            fontSize: '16px',
            color: '#5F6368',
          }}
        >
          ‹
        </button>
        <span style={{ fontSize: '13px', fontWeight: '500', color: '#202124' }}>
          {monthNames[currentMonth.getMonth()]} {currentMonth.getFullYear()}
        </span>
        <button
          onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '2px 6px',
            fontSize: '16px',
            color: '#5F6368',
          }}
        >
          ›
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '3px', marginBottom: '3px' }}>
        {dayNames.map((day, i) => (
          <div key={i} style={{
            textAlign: 'center',
            fontSize: '10px',
            fontWeight: '500',
            color: '#70757A',
            padding: '3px 0',
          }}>
            {day}
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '3px' }}>
        {days.map((day, i) => (
          <button
            key={i}
            disabled={!day}
            onClick={() => day && onDateSelect(day)}
            style={{
              background: isSelected(day) ? '#1A73E8' : isToday(day) ? '#E8F0FE' : 'transparent',
              color: isSelected(day) ? '#FFFFFF' : isToday(day) ? '#1A73E8' : day ? '#202124' : 'transparent',
              border: 'none',
              borderRadius: '50%',
              width: '28px',
              height: '28px',
              fontSize: '12px',
              cursor: day ? 'pointer' : 'default',
              fontWeight: isSelected(day) || isToday(day) ? '500' : '400',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => {
              if (day && !isSelected(day)) {
                e.currentTarget.style.background = '#F1F3F4';
              }
            }}
            onMouseLeave={(e) => {
              if (day && !isSelected(day)) {
                e.currentTarget.style.background = isToday(day) ? '#E8F0FE' : 'transparent';
              }
            }}
          >
            {day ? day.getDate() : ''}
          </button>
        ))}
      </div>
    </div>
  );
}

// Mini Custom Select for Time Picker - Google Calendar Style
function MiniSelect({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) {
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDropdownStyle({
        position: 'fixed',
        top: `${rect.bottom + 4}px`,
        left: `${rect.left}px`,
        minWidth: `${rect.width}px`,
        background: '#FFFFFF',
        border: '1px solid #DADCE0',
        borderRadius: '8px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
        zIndex: 10000,
        maxHeight: '200px',
        overflowY: 'auto',
      });
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      const handleClickOutside = (e: MouseEvent) => {
        const target = e.target as Node;
        if (
          buttonRef.current && !buttonRef.current.contains(target) &&
          dropdownRef.current && !dropdownRef.current.contains(target)
        ) {
          setIsOpen(false);
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        style={{
          padding: '6px 8px',
          fontSize: '13px',
          border: '1px solid #DADCE0',
          borderRadius: '6px',
          background: '#FFFFFF',
          cursor: 'pointer',
          color: '#202124',
          fontWeight: '500',
          minWidth: '42px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '4px',
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#F8F9FA';
          e.currentTarget.style.borderColor = '#1A73E8';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#FFFFFF';
          e.currentTarget.style.borderColor = '#DADCE0';
        }}
      >
        <span>{value}</span>
        <ChevronDown size={10} color="#5F6368" style={{
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease',
        }} />
      </button>

      {isOpen && createPortal(
        <div ref={dropdownRef} style={dropdownStyle}>
          {options.map(option => (
            <button
              key={option}
              onClick={() => {
                onChange(option);
                setIsOpen(false);
              }}
              style={{
                width: '100%',
                padding: '7px 10px',
                fontSize: '13px',
                border: 'none',
                background: value === option ? '#E8F0FE' : 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
                color: value === option ? '#1A73E8' : '#202124',
                fontWeight: value === option ? '600' : '400',
                transition: 'background 0.1s ease',
              }}
              onMouseEnter={(e) => {
                if (value !== option) {
                  e.currentTarget.style.background = '#F1F3F4';
                }
              }}
              onMouseLeave={(e) => {
                if (value !== option) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {option}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </>
  );
}

// Custom Time Picker Component
function TimePicker({ value, onChange }: { value: string; onChange: (time: string) => void }) {
  // Parse initial time from value prop
  const parseTime = (timeString: string) => {
    if (!timeString) return { hour: '12', minute: '00', period: 'PM' };

    // Expected format: "HH:MM AM/PM" (e.g., "02:30 PM")
    const match = timeString.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
    if (match) {
      return {
        hour: match[1].padStart(2, '0'),
        minute: match[2],
        period: match[3].toUpperCase(),
      };
    }
    return { hour: '12', minute: '00', period: 'PM' };
  };

  const initialTime = parseTime(value);
  const [showPicker, setShowPicker] = useState(false);
  const [customEntry, setCustomEntry] = useState(false);
  const [customValue, setCustomValue] = useState('');
  const [hour, setHour] = useState(initialTime.hour);
  const [minute, setMinute] = useState(initialTime.minute);
  const [period, setPeriod] = useState(initialTime.period);

  // Update internal state when value prop changes (only when picker is closed)
  useEffect(() => {
    if (!showPicker) {  // Only sync when picker is closed to avoid race condition
      const newTime = parseTime(value);
      setHour(newTime.hour);
      setMinute(newTime.minute);
      setPeriod(newTime.period);
    }
  }, [value, showPicker]);

  const formatTime = () => {
    if (!value) return 'Select time';
    return value || 'Select time';
  };

  const hours = Array.from({ length: 12 }, (_, i) => (i + 1).toString().padStart(2, '0'));
  const minutes = ['00', '05', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55'];
  const periods = ['AM', 'PM'];

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {customEntry ? (
        <input
          type="text"
          value={customValue}
          onChange={(e) => setCustomValue(e.target.value)}
          onBlur={() => {
            const parsed = parseTime(customValue);
            if (parsed) {
              const timeString = `${parsed.hour}:${parsed.minute} ${parsed.period}`;
              onChange(timeString);
            }
            setCustomEntry(false);
            setCustomValue('');
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const parsed = parseTime(customValue);
              if (parsed) {
                const timeString = `${parsed.hour}:${parsed.minute} ${parsed.period}`;
                onChange(timeString);
              }
              setCustomEntry(false);
              setCustomValue('');
            } else if (e.key === 'Escape') {
              setCustomEntry(false);
              setCustomValue('');
            }
          }}
          placeholder="e.g., 02:30 PM"
          autoFocus
          style={{
            width: '100%',
            padding: '7px 10px',
            fontSize: '13px',
            border: '2px solid #1A73E8',
            borderRadius: '6px',
            background: '#FFFFFF',
            outline: 'none',
            color: '#202124',
            fontWeight: '500',
          }}
        />
      ) : (
        <button
          onClick={() => setShowPicker(!showPicker)}
          onDoubleClick={() => {
            setCustomEntry(true);
            setCustomValue(value || '');
            setShowPicker(false);
          }}
          style={{
            width: '100%',
            padding: '7px 10px',
            fontSize: '13px',
            border: '1px solid #DADCE0',
            borderRadius: '6px',
            background: '#FFFFFF',
            cursor: 'pointer',
            textAlign: 'left',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            color: '#202124',
            fontWeight: '500',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#F8F9FA';
            e.currentTarget.style.borderColor = '#1A73E8';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#FFFFFF';
            e.currentTarget.style.borderColor = '#DADCE0';
          }}
        >
          <span>{formatTime()}</span>
          <Clock size={14} color="#5F6368" />
        </button>
      )}

      {showPicker && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          marginTop: '6px',
          background: '#FFFFFF',
          border: '1px solid #DADCE0',
          borderRadius: '10px',
          padding: '14px',
          boxShadow: '0 6px 20px rgba(0,0,0,0.15)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          width: 'auto',
        }}>
          <div style={{
            display: 'flex',
            gap: '6px',
            alignItems: 'center',
            justifyContent: 'flex-start',
          }}>
            <MiniSelect
              value={hour}
              onChange={setHour}
              options={hours}
            />

            <span style={{ fontSize: '16px', color: '#5F6368', fontWeight: '600' }}>:</span>

            <MiniSelect
              value={minute}
              onChange={setMinute}
              options={minutes}
            />

            <MiniSelect
              value={period}
              onChange={setPeriod}
              options={periods}
            />
          </div>

          <div style={{
            display: 'flex',
            gap: '8px',
            marginTop: '4px',
          }}>
            <button
              onClick={() => setShowPicker(false)}
              style={{
                flex: 1,
                padding: '8px 14px',
                fontSize: '13px',
                background: 'transparent',
                color: '#5F6368',
                border: '1px solid #DADCE0',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: '500',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#F1F3F4';
                e.currentTarget.style.borderColor = '#9AA0A6';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderColor = '#DADCE0';
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => {
                const timeString = `${hour}:${minute} ${period}`;
                onChange(timeString);
                setShowPicker(false);
              }}
              style={{
                flex: 1,
                padding: '8px 14px',
                fontSize: '13px',
                background: '#1A73E8',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: '600',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#1557B0';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#1A73E8';
              }}
            >
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Custom Dropdown Component - Google Calendar Style
function CustomSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[]
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const selectedLabel = options.find(opt => opt.value === value)?.label || options[0].label;

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDropdownStyle({
        position: 'fixed',
        top: `${rect.bottom + 6}px`,
        left: `${rect.left}px`,
        width: `${rect.width}px`,
        background: '#FFFFFF',
        border: '1px solid #DADCE0',
        borderRadius: '8px',
        boxShadow: '0 6px 20px rgba(0,0,0,0.15)',
        zIndex: 9999,
        maxHeight: '360px',
        overflow: 'auto',
      });
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      const handleClickOutside = (e: MouseEvent) => {
        const target = e.target as Node;
        if (
          buttonRef.current && !buttonRef.current.contains(target) &&
          dropdownRef.current && !dropdownRef.current.contains(target)
        ) {
          setIsOpen(false);
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          padding: '7px 10px',
          fontSize: '13px',
          border: '1px solid #DADCE0',
          borderRadius: '6px',
          background: '#FFFFFF',
          cursor: 'pointer',
          textAlign: 'left',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          color: '#202124',
          fontWeight: '500',
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#F8F9FA';
          e.currentTarget.style.borderColor = '#1A73E8';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#FFFFFF';
          e.currentTarget.style.borderColor = '#DADCE0';
        }}
      >
        <span>{selectedLabel}</span>
        <ChevronDown size={14} color="#5F6368" style={{
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease',
        }} />
      </button>

      {isOpen && createPortal(
        <div ref={dropdownRef} style={dropdownStyle}>
          {options.map(option => (
            <button
              key={option.value}
              onClick={() => {
                onChange(option.value);
                setIsOpen(false);
              }}
              style={{
                width: '100%',
                padding: '9px 12px',
                fontSize: '13px',
                border: 'none',
                background: value === option.value ? '#E8F0FE' : 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
                color: value === option.value ? '#1A73E8' : '#202124',
                fontWeight: value === option.value ? '600' : '400',
                transition: 'background 0.1s ease',
              }}
              onMouseEnter={(e) => {
                if (value !== option.value) {
                  e.currentTarget.style.background = '#F1F3F4';
                }
              }}
              onMouseLeave={(e) => {
                if (value !== option.value) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {option.label}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </>
  );
}

export function TaskSidebar({
  taskName,
  onTaskNameChange,
  description,
  onDescriptionChange,
  frequency,
  onFrequencyChange,
  cronExpression,
  onCronExpressionChange,
  customCronExpression,
  onCustomCronExpressionChange,
  email,
  onEmailChange,
  deliveryPreference,
  onDeliveryPreferenceChange,
  onAddNode,
  selectedDate,
  onSelectedDateChange,
  timezone,
  onTimezoneChange,
  tags,
  onTagsChange,
  selectedDays,
  onSelectedDaysChange,
  dayOfMonth,
  onDayOfMonthChange,
}: TaskSidebarProps) {
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);
  const [tagInput, setTagInput] = useState('');

  // Custom repeat state
  const [customRepeatInterval, setCustomRepeatInterval] = useState(1);
  const [customRepeatUnit, setCustomRepeatUnit] = useState<'days' | 'weeks' | 'months'>('days');
  const [customEndType, setCustomEndType] = useState<'never' | 'after' | 'on'>('never');
  const [customEndCount, setCustomEndCount] = useState(10);
  const [customEndDate, setCustomEndDate] = useState<Date | null>(null);

  // Auto-convert custom repeat settings to cron expression when they change
  useEffect(() => {
    if (frequency === 'custom') {
      const config = {
        interval: customRepeatInterval,
        unit: customRepeatUnit,
        daysOfWeek: customRepeatUnit === 'weeks' ? selectedDays : undefined,
        dayOfMonth: customRepeatUnit === 'months' ? (dayOfMonth ?? undefined) : undefined,
        endType: customEndType,
        endCount: customEndType === 'after' ? customEndCount : undefined,
        endDate: customEndType === 'on' && customEndDate ? customEndDate.toISOString() : undefined,
        time: cronExpression, // Use the time from the time picker
      };
      const cron = customRepeatToCron(config);
      onCustomCronExpressionChange(cron);
    }
  }, [
    frequency,
    customRepeatInterval,
    customRepeatUnit,
    customEndType,
    customEndCount,
    customEndDate,
    selectedDays,
    dayOfMonth,
    cronExpression,
  ]);

  // Decode cron expression on load to populate custom repeat UI
  useEffect(() => {
    if (frequency === 'custom' && customCronExpression) {
      const decoded = cronToCustomRepeat(customCronExpression, timezone);
      if (decoded) {
        setCustomRepeatInterval(decoded.interval);
        setCustomRepeatUnit(decoded.unit);
        setCustomEndType(decoded.endType);
        if (decoded.endCount !== undefined) setCustomEndCount(decoded.endCount);
        if (decoded.endDate) setCustomEndDate(new Date(decoded.endDate));
        if (decoded.daysOfWeek) onSelectedDaysChange(decoded.daysOfWeek);
        if (decoded.dayOfMonth !== undefined) onDayOfMonthChange(decoded.dayOfMonth);
        if (decoded.time) onCronExpressionChange(decoded.time);
      }
    }
  }, [customCronExpression, frequency]);

  const toggleDay = (dayIndex: number) => {
    onSelectedDaysChange(
      selectedDays.includes(dayIndex)
        ? selectedDays.filter(d => d !== dayIndex)
        : [...selectedDays, dayIndex],
    );
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      onTagsChange([...tags, tagInput.trim()]);
      setTagInput('');
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    onTagsChange(tags.filter(tag => tag !== tagToRemove));
  };

  const nodeTypes: Record<string, NodeType[]> = {
    entrance: [
      {
        type: 'start',
        label: 'Start',
        Icon: Play,
        logoPath: null,
        bgColor: '#ffffff',
        iconColor: '#10B981',
      },
      {
        type: 'end',
        label: 'End',
        Icon: Square,
        logoPath: null,
        bgColor: '#ffffff',
        iconColor: '#EF4444',
      },
    ],
    dataSource: [
      {
        type: 'portfolio',
        label: 'Portfolio',
        Icon: Database,
        logoPath: null,
        bgColor: '#F3E5F5',
        iconColor: '#9C27B0',
      },
      {
        type: 'graph',
        label: 'Graph',
        Icon: BarChart3,
        logoPath: null,
        bgColor: '#E8F5E9',
        iconColor: '#4CAF50',
        comingSoon: true,
      },
      {
        type: 'fileUpload',
        label: 'File Upload',
        Icon: Upload,
        logoPath: null,
        bgColor: '#FFF3E0',
        iconColor: '#FF9800',
      },
      {
        type: 'oneDrive',
        label: 'OneDrive',
        Icon: null,
        logoPath: '/connector-logos/one-drive.png',
        bgColor: '#E1F5FE',
        iconColor: '#0078D4',
      },
      {
        type: 'sharepoint',
        label: 'SharePoint',
        Icon: null,
        logoPath: '/connector-logos/sharepoint-logo.png',
        bgColor: '#E8F0F7',
        iconColor: '#036C70',
      },
      {
        type: 'googleDrive',
        label: 'Google Drive',
        Icon: null,
        logoPath: '/connector-logos/google-drive.png',
        bgColor: '#E8F5E9',
        iconColor: '#4CAF50',
      },
    ],
    utility: [
      {
        type: 'merge',
        label: 'Merge',
        Icon: Merge,
        logoPath: null,
        bgColor: '#F3E8FF',
        iconColor: '#8B5CF6',
      },
      {
        type: 'distribute',
        label: 'Distribute',
        Icon: Split,
        logoPath: null,
        bgColor: '#F3E8FF',
        iconColor: '#8B5CF6',
      },
    ],
    agent: [
      {
        type: 'agent',
        label: 'Agent',
        Icon: Sparkles,
        logoPath: null,
        bgColor: '#E3F2FD',
        iconColor: '#2196F3',
      },
    ],
    outputStyle: [
      {
        type: 'pdfReport',
        label: 'PDF Report',
        Icon: FileText,
        logoPath: null,
        bgColor: '#FCE4EC',
        iconColor: '#E91E63',
      },
      {
        type: 'pptPresentation',
        label: 'PPT',
        Icon: Presentation,
        logoPath: null,
        bgColor: '#FFF9C4',
        iconColor: '#F57C00',
      },
      {
        type: 'workbook',
        label: 'Workbook',
        Icon: BookOpen,
        logoPath: null,
        bgColor: '#E8F5E9',
        iconColor: '#4CAF50',
      },
    ],
    communicators: [
      {
        type: 'saveToSentry',
        label: 'Save to Sentry',
        Icon: null,
        logoPath: '/binomial-icon-logo.png',
        bgColor: '#FFFFFF',
        iconColor: '#111827',
      },
      {
        type: 'email',
        label: 'Email',
        Icon: null,
        logoPath: '/connector-logos/email-icon.png',
        bgColor: '#FFFFFF',
        iconColor: '#F44336',
      },
      {
        type: 'slack',
        label: 'Slack',
        Icon: null,
        logoPath: '/connector-logos/slack-logo.png',
        bgColor: '#FFFFFF',
        iconColor: '#4A154B',
      },
      {
        type: 'teams',
        label: 'Teams',
        Icon: null,
        logoPath: '/connector-logos/teams-logo.png',
        bgColor: '#FFFFFF',
        iconColor: '#5B5FC7',
      },
    ],
  };

  return (
    <>
      {/* Task Settings Header - Collapsed Tab */}
      <div
        onClick={() => setSettingsExpanded(!settingsExpanded)}
        style={{
          position: 'absolute',
          top: '60px',
          left: '12px',
          width: 'clamp(220px, 16vw, 280px)',
          background: '#FFFFFF',
          borderRadius: '10px',
          padding: '12px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          zIndex: 5,
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '13px', fontWeight: '500', color: '#202124', letterSpacing: '0.1px' }}>
          Task Settings
        </span>
        <ChevronRight
          size={16}
          color="#5F6368"
        />
      </div>

      {/* Task Settings Expanded Panel - Slides to Right */}
      {settingsExpanded && (
        <div style={{
          position: 'absolute',
          top: '60px',
          left: 'clamp(244px, calc(16vw + 32px), 312px)',
          width: 'clamp(260px, 18vw, 320px)',
          maxHeight: 'calc(100vh - 72px)',
          background: '#FFFFFF',
          borderRadius: '10px',
          padding: '12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          zIndex: 5,
          overflowY: 'visible',
          overflowX: 'visible',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'visible', maxHeight: 'calc(100vh - 96px)', overflowY: 'auto', paddingRight: '4px' }}>
            {/* Title */}
            <input
              type="text"
              value={taskName}
              onChange={(e) => onTaskNameChange(e.target.value)}
              placeholder="Add title"
              style={{
                width: '100%',
                maxWidth: '100%',
                padding: '6px 0',
                fontSize: '16px',
                fontWeight: '400',
                border: 'none',
                borderBottom: '1px solid #DADCE0',
                outline: 'none',
                background: 'transparent',
                color: '#202124',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderBottomColor = '#1A73E8';
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderBottomColor = '#DADCE0';
              }}
            />

            {/* Date/Time/Timezone Section */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflow: 'visible' }}>
              {/* Date */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  minWidth: '60px',
                  color: '#5F6368',
                  fontSize: '12px',
                }}>
                  <CalendarIcon size={14} />
                  <span>Date</span>
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'visible' }}>
                  <button
                    onClick={() => setShowCalendar(!showCalendar)}
                    style={{
                      width: '100%',
                      padding: '5px 8px',
                      fontSize: '12px',
                      border: '1px solid #DADCE0',
                      borderRadius: '4px',
                      background: '#FFFFFF',
                      cursor: 'pointer',
                      textAlign: 'left',
                      color: '#202124',
                    }}
                  >
                    {selectedDate ? selectedDate.toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    }) : 'Select date'}
                  </button>
                </div>
              </div>

              {/* Time - Custom Picker with 5-min Increments */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'visible' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  minWidth: '60px',
                  color: '#5F6368',
                  fontSize: '12px',
                }}>
                  <Clock size={14} />
                  <span>Time</span>
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'visible' }}>
                  <TimePicker
                    value={cronExpression}
                    onChange={onCronExpressionChange}
                  />
                </div>
              </div>

              {/* Timezone */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'visible' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  minWidth: '60px',
                  color: '#5F6368',
                  fontSize: '12px',
                }}>
                  <Globe size={14} />
                  <span>Zone</span>
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'visible' }}>
                  <CustomSelect
                    value={timezone}
                    onChange={onTimezoneChange}
                    options={[
                      // North America - United States
                      { value: 'America/New_York', label: 'New York (UTC-5)' },
                      { value: 'America/Chicago', label: 'Chicago (UTC-6)' },
                      { value: 'America/Denver', label: 'Denver (UTC-7)' },
                      { value: 'America/Los_Angeles', label: 'Los Angeles (UTC-8)' },
                      { value: 'America/Phoenix', label: 'Phoenix (UTC-7)' },
                      { value: 'America/Detroit', label: 'Detroit (UTC-5)' },
                      { value: 'America/Boise', label: 'Boise (UTC-7)' },
                      { value: 'America/Anchorage', label: 'Anchorage (UTC-9)' },
                      { value: 'Pacific/Honolulu', label: 'Honolulu (UTC-10)' },
                      // North America - Canada & Mexico
                      { value: 'America/Toronto', label: 'Toronto (UTC-5)' },
                      { value: 'America/Vancouver', label: 'Vancouver (UTC-8)' },
                      { value: 'America/Mexico_City', label: 'Mexico City (UTC-6)' },
                      // South America
                      { value: 'America/Sao_Paulo', label: 'São Paulo (UTC-3)' },
                      { value: 'America/Buenos_Aires', label: 'Buenos Aires (UTC-3)' },
                      { value: 'America/Santiago', label: 'Santiago (UTC-3)' },
                      { value: 'America/Lima', label: 'Lima (UTC-5)' },
                      { value: 'America/Bogota', label: 'Bogotá (UTC-5)' },
                      { value: 'America/Caracas', label: 'Caracas (UTC-4)' },
                      // Europe - Western
                      { value: 'Europe/London', label: 'London (UTC+0)' },
                      { value: 'Europe/Dublin', label: 'Dublin (UTC+0)' },
                      { value: 'Europe/Lisbon', label: 'Lisbon (UTC+0)' },
                      { value: 'Europe/Paris', label: 'Paris (UTC+1)' },
                      { value: 'Europe/Berlin', label: 'Berlin (UTC+1)' },
                      { value: 'Europe/Amsterdam', label: 'Amsterdam (UTC+1)' },
                      { value: 'Europe/Brussels', label: 'Brussels (UTC+1)' },
                      { value: 'Europe/Madrid', label: 'Madrid (UTC+1)' },
                      { value: 'Europe/Rome', label: 'Rome (UTC+1)' },
                      { value: 'Europe/Zurich', label: 'Zurich (UTC+1)' },
                      { value: 'Europe/Vienna', label: 'Vienna (UTC+1)' },
                      // Europe - Northern
                      { value: 'Europe/Stockholm', label: 'Stockholm (UTC+1)' },
                      { value: 'Europe/Copenhagen', label: 'Copenhagen (UTC+1)' },
                      { value: 'Europe/Oslo', label: 'Oslo (UTC+1)' },
                      { value: 'Europe/Helsinki', label: 'Helsinki (UTC+2)' },
                      // Europe - Eastern
                      { value: 'Europe/Athens', label: 'Athens (UTC+2)' },
                      { value: 'Europe/Warsaw', label: 'Warsaw (UTC+1)' },
                      { value: 'Europe/Prague', label: 'Prague (UTC+1)' },
                      { value: 'Europe/Budapest', label: 'Budapest (UTC+1)' },
                      { value: 'Europe/Bucharest', label: 'Bucharest (UTC+2)' },
                      { value: 'Europe/Istanbul', label: 'Istanbul (UTC+3)' },
                      { value: 'Europe/Moscow', label: 'Moscow (UTC+3)' },
                      // Middle East
                      { value: 'Asia/Dubai', label: 'Dubai (UTC+4)' },
                      { value: 'Asia/Riyadh', label: 'Riyadh (UTC+3)' },
                      { value: 'Asia/Tel_Aviv', label: 'Tel Aviv (UTC+2)' },
                      { value: 'Asia/Jerusalem', label: 'Jerusalem (UTC+2)' },
                      { value: 'Asia/Kuwait', label: 'Kuwait (UTC+3)' },
                      // Africa
                      { value: 'Africa/Cairo', label: 'Cairo (UTC+2)' },
                      { value: 'Africa/Johannesburg', label: 'Johannesburg (UTC+2)' },
                      { value: 'Africa/Nairobi', label: 'Nairobi (UTC+3)' },
                      { value: 'Africa/Lagos', label: 'Lagos (UTC+1)' },
                      { value: 'Africa/Casablanca', label: 'Casablanca (UTC+0)' },
                      // Asia - South & Southeast
                      { value: 'Asia/Kolkata', label: 'Mumbai (UTC+5:30)' },
                      { value: 'Asia/Karachi', label: 'Karachi (UTC+5)' },
                      { value: 'Asia/Bangkok', label: 'Bangkok (UTC+7)' },
                      { value: 'Asia/Jakarta', label: 'Jakarta (UTC+7)' },
                      { value: 'Asia/Manila', label: 'Manila (UTC+8)' },
                      { value: 'Asia/Singapore', label: 'Singapore (UTC+8)' },
                      { value: 'Asia/Kuala_Lumpur', label: 'Kuala Lumpur (UTC+8)' },
                      { value: 'Asia/Ho_Chi_Minh', label: 'Ho Chi Minh (UTC+7)' },
                      // Asia - East
                      { value: 'Asia/Shanghai', label: 'Shanghai (UTC+8)' },
                      { value: 'Asia/Hong_Kong', label: 'Hong Kong (UTC+8)' },
                      { value: 'Asia/Taipei', label: 'Taipei (UTC+8)' },
                      { value: 'Asia/Tokyo', label: 'Tokyo (UTC+9)' },
                      { value: 'Asia/Seoul', label: 'Seoul (UTC+9)' },
                      // Australia & Pacific
                      { value: 'Australia/Sydney', label: 'Sydney (UTC+10)' },
                      { value: 'Australia/Melbourne', label: 'Melbourne (UTC+10)' },
                      { value: 'Australia/Brisbane', label: 'Brisbane (UTC+10)' },
                      { value: 'Australia/Perth', label: 'Perth (UTC+8)' },
                      { value: 'Pacific/Auckland', label: 'Auckland (UTC+12)' },
                      { value: 'Pacific/Fiji', label: 'Fiji (UTC+12)' },
                      // UTC
                      { value: 'UTC', label: 'UTC (UTC+0)' },
                    ]}
                  />
                </div>
              </div>
            </div>

            {/* Repeat */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'visible' }}>
              <div style={{
                minWidth: '60px',
                color: '#5F6368',
                fontSize: '12px',
                fontWeight: '500',
              }}>
                Repeat
              </div>
              <div style={{ flex: 1, overflow: 'visible' }}>
                <CustomSelect
                  value={frequency}
                  onChange={onFrequencyChange}
                  options={[
                    { value: 'once', label: 'Does not repeat' },
                    { value: 'daily', label: 'Daily' },
                    { value: 'weekdays', label: 'Weekdays (Mon-Fri)' },
                    { value: 'weekly', label: 'Weekly' },
                    { value: 'biweekly', label: 'Biweekly' },
                    { value: 'monthly', label: 'Monthly' },
                    { value: 'custom', label: 'Custom' },
                  ]}
                />
              </div>
            </div>

            {/* Weekly/Biweekly Day Selector */}
            {(frequency === 'weekly' || frequency === 'biweekly') && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <div style={{
                  minWidth: '60px',
                  paddingTop: '4px',
                  color: '#5F6368',
                  fontSize: '12px',
                  fontWeight: '500',
                }}>
                  On
                </div>
                <div style={{ flex: 1, display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                  {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, idx) => (
                    <button
                      key={idx}
                      onClick={() => toggleDay(idx)}
                      style={{
                        width: '32px',
                        height: '32px',
                        fontSize: '12px',
                        border: `1px solid ${selectedDays.includes(idx) ? '#1A73E8' : '#DADCE0'}`,
                        borderRadius: '50%',
                        background: selectedDays.includes(idx) ? '#1A73E8' : '#FFFFFF',
                        color: selectedDays.includes(idx) ? '#FFFFFF' : '#5F6368',
                        cursor: 'pointer',
                        fontWeight: '500',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.12s',
                      }}
                    >
                      {day}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Monthly Day of Month Selector */}
            {frequency === 'monthly' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  minWidth: '60px',
                  color: '#5F6368',
                  fontSize: '12px',
                  fontWeight: '500',
                }}>
                  Day
                </div>
                <input
                  type="number"
                  min="1"
                  max="31"
                  value={dayOfMonth || ''}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    onDayOfMonthChange(isNaN(val) ? null : val);
                  }}
                  placeholder="1-31"
                  style={{
                    flex: 1,
                    padding: '5px 8px',
                    fontSize: '12px',
                    border: '1px solid #DADCE0',
                    borderRadius: '4px',
                    outline: 'none',
                    background: '#FFFFFF',
                    color: '#202124',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = '#1A73E8';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = '#DADCE0';
                  }}
                />
              </div>
            )}

            {/* Custom Repeat Configuration */}
            {frequency === 'custom' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingLeft: '8px', paddingTop: '4px' }}>
                {/* Repeat Every */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '12px', color: '#5F6368', fontWeight: '500', minWidth: '50px' }}>Every</span>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={customRepeatInterval}
                    onChange={(e) => setCustomRepeatInterval(parseInt(e.target.value) || 1)}
                    style={{
                      width: '60px',
                      padding: '5px 8px',
                      fontSize: '12px',
                      border: '1px solid #DADCE0',
                      borderRadius: '4px',
                      outline: 'none',
                      background: '#FFFFFF',
                      color: '#202124',
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = '#1A73E8';
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = '#DADCE0';
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <CustomSelect
                      value={customRepeatUnit}
                      onChange={(val) => setCustomRepeatUnit(val as 'days' | 'weeks' | 'months')}
                      options={[
                        { value: 'days', label: 'Day(s)' },
                        { value: 'weeks', label: 'Week(s)' },
                        { value: 'months', label: 'Month(s)' },
                      ]}
                    />
                  </div>
                </div>

                {/* Week Days Selector - Only for weeks */}
                {customRepeatUnit === 'weeks' && (
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <span style={{ fontSize: '12px', color: '#5F6368', fontWeight: '500', minWidth: '50px', paddingTop: '4px' }}>On</span>
                    <div style={{ flex: 1, display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, idx) => (
                        <button
                          key={idx}
                          onClick={() => toggleDay(idx)}
                          style={{
                            width: '32px',
                            height: '32px',
                            fontSize: '12px',
                            border: `1px solid ${selectedDays.includes(idx) ? '#1A73E8' : '#DADCE0'}`,
                            borderRadius: '50%',
                            background: selectedDays.includes(idx) ? '#1A73E8' : '#FFFFFF',
                            color: selectedDays.includes(idx) ? '#FFFFFF' : '#5F6368',
                            cursor: 'pointer',
                            fontWeight: '500',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'all 0.12s',
                          }}
                        >
                          {day}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Month Day Selector - Only for months */}
                {customRepeatUnit === 'months' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '12px', color: '#5F6368', fontWeight: '500', minWidth: '50px' }}>On day</span>
                    <input
                      type="number"
                      min="1"
                      max="31"
                      value={dayOfMonth || ''}
                      onChange={(e) => {
                        const val = parseInt(e.target.value);
                        onDayOfMonthChange(isNaN(val) ? null : val);
                      }}
                      placeholder="1-31"
                      style={{
                        width: '70px',
                        padding: '5px 8px',
                        fontSize: '12px',
                        border: '1px solid #DADCE0',
                        borderRadius: '4px',
                        outline: 'none',
                        background: '#FFFFFF',
                        color: '#202124',
                      }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = '#1A73E8';
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = '#DADCE0';
                      }}
                    />
                  </div>
                )}

                {/* Ends */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '12px', color: '#5F6368', fontWeight: '500', minWidth: '50px' }}>Ends</span>
                  <div style={{ flex: 1 }}>
                    <CustomSelect
                      value={customEndType}
                      onChange={(val) => setCustomEndType(val as 'never' | 'after' | 'on')}
                      options={[
                        { value: 'never', label: 'Never' },
                        { value: 'after', label: 'After...' },
                        { value: 'on', label: 'On date...' },
                      ]}
                    />
                  </div>
                </div>

                {/* After X occurrences */}
                {customEndType === 'after' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingLeft: '58px' }}>
                    <input
                      type="number"
                      min="1"
                      max="999"
                      value={customEndCount}
                      onChange={(e) => setCustomEndCount(parseInt(e.target.value) || 1)}
                      style={{
                        width: '70px',
                        padding: '5px 8px',
                        fontSize: '12px',
                        border: '1px solid #DADCE0',
                        borderRadius: '4px',
                        outline: 'none',
                        background: '#FFFFFF',
                        color: '#202124',
                      }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = '#1A73E8';
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = '#DADCE0';
                      }}
                    />
                    <span style={{ fontSize: '12px', color: '#5F6368' }}>occurrences</span>
                  </div>
                )}

                {/* On specific date */}
                {customEndType === 'on' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingLeft: '58px' }}>
                    <button
                      onClick={() => setShowCalendar(!showCalendar)}
                      style={{
                        padding: '5px 8px',
                        fontSize: '12px',
                        border: '1px solid #DADCE0',
                        borderRadius: '4px',
                        background: '#FFFFFF',
                        cursor: 'pointer',
                        color: '#202124',
                      }}
                    >
                      {customEndDate ? customEndDate.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      }) : 'Select date'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Description */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ color: '#5F6368', fontSize: '12px', fontWeight: '500' }}>
                Description
              </div>
              <textarea
                value={description}
                onChange={(e) => onDescriptionChange(e.target.value)}
                placeholder="Add description"
                rows={2}
                style={{
                  width: '100%',
                  maxWidth: '100%',
                  padding: '6px 8px',
                  fontSize: '12px',
                  border: '1px solid #DADCE0',
                  borderRadius: '4px',
                  outline: 'none',
                  resize: 'vertical',
                  fontFamily: 'inherit',
                  background: '#FFFFFF',
                  color: '#202124',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = '#1A73E8';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = '#DADCE0';
                }}
              />
            </div>

            {/* Tags/Categories */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ color: '#5F6368', fontSize: '12px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Tag size={12} />
                <span>Tags</span>
              </div>
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '4px',
                padding: '6px 8px',
                border: '1px solid #DADCE0',
                borderRadius: '4px',
                minHeight: '34px',
                alignItems: 'center',
                width: '100%',
                boxSizing: 'border-box',
              }}>
                {tags.map(tag => (
                  <div
                    key={tag}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '3px 8px',
                      background: '#E8F0FE',
                      color: '#1A73E8',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: '500',
                    }}
                  >
                    <span>{tag}</span>
                    <button
                      onClick={() => handleRemoveTag(tag)}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: '0',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <X size={12} color="#1A73E8" />
                    </button>
                  </div>
                ))}
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ',') {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                  placeholder={tags.length === 0 ? 'Add tags...' : ''}
                  style={{
                    flex: 1,
                    border: 'none',
                    outline: 'none',
                    fontSize: '12px',
                    minWidth: '60px',
                    background: 'transparent',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Calendar - Third Layer Outside Panel */}
      {settingsExpanded && showCalendar && (
        <div style={{
          position: 'absolute',
          top: 'calc(60px + 68px)',
          left: 'clamp(512px, calc(34vw + 40px), 640px)',
          zIndex: 11,
        }}>
          <MiniCalendar
            selectedDate={selectedDate}
            onDateSelect={(date) => {
              onSelectedDateChange(date);
              setShowCalendar(false);
            }}
          />
        </div>
      )}

      {/* Node Palette - Separate Rounded Card */}
      <div style={{
        position: 'absolute',
        top: 'calc(60px + 60px)',
        left: '12px',
        width: 'clamp(220px, 16vw, 280px)',
        maxHeight: 'calc(100vh - 132px)',
        background: '#FFFFFF',
        borderRadius: '10px',
        padding: '10px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        overflow: 'auto',
        zIndex: 4,
      }}>
        {/* Entrance */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#5F6368',
            padding: '0 4px',
            marginBottom: '6px',
            letterSpacing: '0.4px',
          }}>
            ENTRANCE
          </div>
          {nodeTypes.entrance.map((node) => {
            const { Icon, logoPath } = node;
            return (
              <button
                key={node.type}
                onClick={() => onAddNode(node.type)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: '400',
                  color: '#202124',
                  transition: 'background 0.12s',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#F1F3F4';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '3px',
                  background: node.bgColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {Icon && <Icon size={12} style={{ color: node.iconColor }} />}
                  {logoPath && <img src={logoPath} alt={node.label} style={{ width: '14px', height: '14px', objectFit: 'contain' }} />}
                </div>
                <span>{node.label}</span>
              </button>
            );
          })}
        </div>

        {/* Data Source */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#5F6368',
            padding: '0 4px',
            marginBottom: '6px',
            letterSpacing: '0.4px',
          }}>
            DATA SOURCE
          </div>
          {nodeTypes.dataSource.map((node) => {
            const { Icon, logoPath, comingSoon } = node;
            return (
              <button
                key={node.type}
                onClick={() => !comingSoon && onAddNode(node.type)}
                disabled={comingSoon}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: comingSoon ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  fontWeight: '400',
                  color: comingSoon ? '#8A8886' : '#202124',
                  transition: 'background 0.12s',
                  textAlign: 'left',
                  opacity: comingSoon ? 0.5 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!comingSoon) e.currentTarget.style.background = '#F1F3F4';
                }}
                onMouseLeave={(e) => {
                  if (!comingSoon) e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '3px',
                  background: node.bgColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {Icon && <Icon size={12} style={{ color: node.iconColor }} />}
                  {logoPath && <img src={logoPath} alt={node.label} style={{ width: '14px', height: '14px', objectFit: 'contain' }} />}
                </div>
                <span style={{ flex: 1 }}>{node.label}</span>
                {comingSoon && (
                  <span style={{ fontSize: '10px', color: '#8A8886', fontStyle: 'italic' }}>Coming Soon</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Utility */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#5F6368',
            padding: '0 4px',
            marginBottom: '6px',
            letterSpacing: '0.4px',
          }}>
            UTILITY
          </div>
          {nodeTypes.utility.map((node) => {
            const { Icon, logoPath } = node;
            return (
              <button
                key={node.type}
                onClick={() => onAddNode(node.type)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: '400',
                  color: '#202124',
                  transition: 'background 0.12s',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#F1F3F4';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '3px',
                  background: node.bgColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {Icon && <Icon size={12} style={{ color: node.iconColor, transform: node.type === 'merge' ? 'rotate(90deg)' : node.type === 'distribute' ? 'rotate(90deg)' : undefined }} />}
                  {logoPath && <img src={logoPath} alt={node.label} style={{ width: '14px', height: '14px', objectFit: 'contain' }} />}
                </div>
                <span>{node.label}</span>
              </button>
            );
          })}
        </div>

        {/* Agent */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#5F6368',
            padding: '0 4px',
            marginBottom: '6px',
            letterSpacing: '0.4px',
          }}>
            AGENT
          </div>
          {nodeTypes.agent.map((node) => {
            const { Icon, logoPath } = node;
            return (
              <button
                key={node.type}
                onClick={() => onAddNode(node.type)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: '400',
                  color: '#202124',
                  transition: 'background 0.12s',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#F1F3F4';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '3px',
                  background: node.bgColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {Icon && <Icon size={12} style={{ color: node.iconColor }} />}
                  {logoPath && <img src={logoPath} alt={node.label} style={{ width: '14px', height: '14px', objectFit: 'contain' }} />}
                </div>
                <span>{node.label}</span>
              </button>
            );
          })}
        </div>

        {/* Output Style */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#5F6368',
            padding: '0 4px',
            marginBottom: '6px',
            letterSpacing: '0.4px',
          }}>
            OUTPUT STYLE
          </div>
          {nodeTypes.outputStyle.map((node) => {
            const { Icon, logoPath, comingSoon } = node;
            return (
              <button
                key={node.type}
                onClick={() => !comingSoon && onAddNode(node.type)}
                disabled={comingSoon}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: comingSoon ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  fontWeight: '400',
                  color: comingSoon ? '#8A8886' : '#202124',
                  transition: 'background 0.12s',
                  textAlign: 'left',
                  opacity: comingSoon ? 0.5 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!comingSoon) e.currentTarget.style.background = '#F1F3F4';
                }}
                onMouseLeave={(e) => {
                  if (!comingSoon) e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '3px',
                  background: node.bgColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {Icon && <Icon size={12} style={{ color: node.iconColor }} />}
                  {logoPath && <img src={logoPath} alt={node.label} style={{ width: '14px', height: '14px', objectFit: 'contain' }} />}
                </div>
                <span style={{ flex: 1 }}>{node.label}</span>
                {comingSoon && (
                  <span style={{ fontSize: '10px', color: '#8A8886', fontStyle: 'italic' }}>Coming Soon</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Delivery Methods */}
        <div style={{ marginBottom: '0' }}>
          <div style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#5F6368',
            padding: '0 4px',
            marginBottom: '6px',
            letterSpacing: '0.4px',
          }}>
            DELIVERY METHODS
          </div>
          {nodeTypes.communicators.map((node) => {
            const { Icon, logoPath } = node;
            return (
              <button
                key={node.type}
                onClick={() => onAddNode(node.type)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: '400',
                  color: '#202124',
                  transition: 'background 0.12s',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#F1F3F4';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '3px',
                  background: node.bgColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {Icon && <Icon size={12} style={{ color: node.iconColor }} />}
                  {logoPath && <img src={logoPath} alt={node.label} style={{ width: '14px', height: '14px', objectFit: 'contain' }} />}
                </div>
                <span>{node.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
