import { useEffect, useState, useRef } from 'react';

const STATUS_TEXTS = [
  'Working',
  'Gathering data',
  'Processing',
  'Summarizing',
  'Preparing response',
  'Finalizing',
];

const LoadingAnimation = () => {
  const [seconds, setSeconds] = useState(0);
  const [idx, setIdx] = useState(0);
  const startTimeRef = useRef(Date.now());
  const t1Ref = useRef<NodeJS.Timeout | null>(null);
  const t2Ref = useRef<NodeJS.Timeout | null>(null);
  const pausedTimeRef = useRef(0); // Track accumulated time when paused

  useEffect(() => {
    // Initialize start time on mount
    if (!startTimeRef.current) {
      startTimeRef.current = Date.now() - pausedTimeRef.current;
    }

    // Update timer based on elapsed time since start
    t1Ref.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
      setSeconds(elapsed);
    }, 1000);

    t2Ref.current = setInterval(() => setIdx((i) => (i + 1) % STATUS_TEXTS.length), 1200);

    // Handle tab visibility changes
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab switched away - pause timers
        if (t1Ref.current) clearInterval(t1Ref.current);
        if (t2Ref.current) clearInterval(t2Ref.current);
        pausedTimeRef.current = Date.now() - startTimeRef.current;
      } else {
        // Tab switched back - resume timers
        startTimeRef.current = Date.now() - pausedTimeRef.current;

        t1Ref.current = setInterval(() => {
          const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
          setSeconds(elapsed);
        }, 1000);

        t2Ref.current = setInterval(() => setIdx((i) => (i + 1) % STATUS_TEXTS.length), 1200);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (t1Ref.current) clearInterval(t1Ref.current);
      if (t2Ref.current) clearInterval(t2Ref.current);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <div role="status" aria-live="polite" aria-busy="true" className="py-3">
      {/* Microsoft-style progress bar with shimmer */}
      <div className="mb-2 relative w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        {/* Base progress bar background */}
        <div className="absolute inset-0 bg-blue-100 dark:bg-blue-900/30" />

        {/* Animated shimmer streak */}
        <div
          className="absolute h-full bg-gradient-to-r from-transparent via-blue-500 to-transparent animate-shimmer"
          style={{
            width: '40%',
            boxShadow: '0 0 10px rgba(59, 130, 246, 0.5)',
          }}
        />
      </div>

      {/* Status text and timer */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-700 dark:text-gray-300 font-medium">
          {STATUS_TEXTS[idx]}
        </span>
        <span className="text-gray-600 dark:text-gray-400">
          {seconds}s
        </span>
      </div>

      <style>{`
        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(350%);
          }
        }
        
        .animate-shimmer {
          animation: shimmer 1.5s ease-in-out infinite;
        }
        
        /* Respect reduced motion */
        @media (prefers-reduced-motion: reduce) { 
          .animate-shimmer { 
            animation: none;
            transform: translateX(0);
            width: 100% !important;
            background: linear-gradient(to right, transparent, rgba(59, 130, 246, 0.3), transparent);
          } 
        }
      `}</style>
    </div>
  );
};

export default LoadingAnimation;
