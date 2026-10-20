// Shared constants for streaming functionality

// Maximum age for streaming rehydration (5 minutes)
export const REHYDRATE_MAX_AGE_MS = 5 * 60 * 1000;

// Timeout for stale streaming messages (30 minutes)
export const STREAMING_TIMEOUT_MS = 30 * 60 * 1000;

// Idle timeout before finalizing (1.5 seconds)
export const IDLE_FINALIZE_DELAY_MS = 1500;

// Stream retry timeout (20 seconds)
export const STREAM_MAX_RETRY_MS = 20000;

// Polling interval for stream status checks (3 seconds)
export const STREAM_POLL_INTERVAL_MS = 3000;

// Maximum polling attempts (~5 minutes at 3s interval)
export const MAX_POLL_ATTEMPTS = 100;
