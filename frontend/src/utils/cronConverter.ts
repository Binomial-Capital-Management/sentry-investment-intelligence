/**
 * Utility functions to convert between user-friendly custom repeat settings and cron expressions
 *
 * Note: Standard cron has limitations and cannot express all patterns (e.g., "every 2 weeks", "ends after X occurrences")
 * This implementation uses a hybrid approach: cron expression + JSON metadata
 */

export interface CustomRepeatConfig {
  interval: number;
  unit: 'days' | 'weeks' | 'months';
  daysOfWeek?: number[];  // 0-6 (Sun-Sat), only for weeks
  dayOfMonth?: number;    // 1-31, only for months
  endType: 'never' | 'after' | 'on';
  endCount?: number;      // occurrences, for 'after'
  endDate?: string;       // ISO date string, for 'on'
  time?: string;          // Time string (e.g., "02:30 PM")
}

/**
 * Convert user-friendly custom repeat config to cron expression
 * Returns a best-effort cron expression + full config as JSON comment
 */
export function customRepeatToCron(config: CustomRepeatConfig): string {
  const { interval, unit, daysOfWeek, dayOfMonth, time } = config;

  // Parse time (default to 9:00 AM if not provided)
  let hour = 9;
  let minute = 0;

  if (time) {
    const match = time.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
    if (match) {
      hour = parseInt(match[1]);
      minute = parseInt(match[2]);
      const period = match[3].toUpperCase();

      // Convert to 24-hour format
      if (period === 'PM' && hour !== 12) {
        hour += 12;
      } else if (period === 'AM' && hour === 12) {
        hour = 0;
      }
    }
  }

  // Build cron expression based on unit
  let cronExpr: string;

  if (unit === 'days') {
    if (interval === 1) {
      // Every day
      cronExpr = `${minute} ${hour} * * *`;
    } else {
      // Every N days - cron can't express this directly, use */N approximation
      // NOTE: This is not perfect but best effort
      cronExpr = `${minute} ${hour} */${interval} * *`;
    }
  } else if (unit === 'weeks') {
    const days = daysOfWeek && daysOfWeek.length > 0 ? daysOfWeek.join(',') : '*';

    if (interval === 1) {
      // Every week on specified days
      cronExpr = `${minute} ${hour} * * ${days}`;
    } else {
      // Every N weeks - cron can't express this, store in comment
      // Use weekly pattern as best effort
      cronExpr = `${minute} ${hour} * * ${days}`;
    }
  } else if (unit === 'months') {
    const day = dayOfMonth || 1;

    if (interval === 1) {
      // Every month on specified day
      cronExpr = `${minute} ${hour} ${day} * *`;
    } else {
      // Every N months - cron can't express this directly
      // Use */N approximation
      cronExpr = `${minute} ${hour} ${day} */${interval} *`;
    }
  } else {
    // Fallback
    cronExpr = `${minute} ${hour} * * *`;
  }

  // Append config as JSON comment for full fidelity
  const configJson = JSON.stringify(config);
  return `${cronExpr} # ${configJson}`;
}

/**
 * Decode cron expression back to custom repeat config
 * Handles both pure cron and cron with JSON comment
 */
export function cronToCustomRepeat(cronExpression: string, timezone?: string): CustomRepeatConfig | null {
  if (!cronExpression || !cronExpression.trim()) {
    return null;
  }

  // Check if cron has JSON comment
  const parts = cronExpression.split('#');
  if (parts.length > 1) {
    try {
      const config = JSON.parse(parts[1].trim());
      return config as CustomRepeatConfig;
    } catch (e) {
      console.warn('Failed to parse cron comment JSON, falling back to cron parsing');
    }
  }

  // Parse standard cron expression
  const cronParts = parts[0].trim().split(/\s+/);
  if (cronParts.length < 5) {
    return null;
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = cronParts;

  // Convert hour/minute to time string
  const hourNum = parseInt(hour);
  const minuteNum = parseInt(minute);
  const period = hourNum >= 12 ? 'PM' : 'AM';
  const hour12 = hourNum === 0 ? 12 : hourNum > 12 ? hourNum - 12 : hourNum;
  const time = `${hour12.toString().padStart(2, '0')}:${minuteNum.toString().padStart(2, '0')} ${period}`;

  // Detect pattern
  if (dayOfWeek !== '*') {
    // Weekly pattern
    const days = dayOfWeek.split(',').map(d => parseInt(d)).filter(d => !isNaN(d));

    return {
      interval: 1, // Best guess
      unit: 'weeks',
      daysOfWeek: days,
      endType: 'never',
      time,
    };
  } else if (dayOfMonth !== '*') {
    // Monthly pattern
    const day = parseInt(dayOfMonth.replace(/\/.*/, '')); // Remove */N part

    return {
      interval: 1, // Best guess
      unit: 'months',
      dayOfMonth: day,
      endType: 'never',
      time,
    };
  } else {
    // Daily pattern (default)
    return {
      interval: 1,
      unit: 'days',
      endType: 'never',
      time,
    };
  }
}
