import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useChatStore } from '@stores/chatStore';
import memoryApiService from '@/services/memoryApi';

interface TokenUsageRingProps {
  size?: number;
}

const TokenUsageRing: React.FC<TokenUsageRingProps> = ({ size = 28 }) => {
  const [usagePercent, setUsagePercent] = useState(0);
  const [pressureLevel, setPressureLevel] = useState<'low' | 'medium' | 'high' | 'critical'>('low');
  const [totalUsed, setTotalUsed] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  
  const { currentThreadId, threads, getCurrentThreadModel, compactionInfo } = useChatStore();
  const currentModel = getCurrentThreadModel?.() || 'gpt-6.1-sol';
  const previousModel = useRef(currentModel);
  
  // Get current thread's message count to trigger refresh
  const currentThread = threads.find(t => t.id === currentThreadId);
  const messageCount = currentThread?.messages?.length || 0;
  
  // Track compaction state
  const wasCompacting = useRef(compactionInfo?.isCompacting);

  const fetchStats = useCallback(async () => {
    if (!currentThreadId) return;
    
    setIsLoading(true);
    try {
      const stats = await memoryApiService.getTokenStats(currentThreadId, currentModel);
      setUsagePercent(stats.usage_percent);
      setPressureLevel(stats.pressure_level);
      setTotalUsed(stats.total_used);
      setRemaining(stats.remaining);
    } catch (err) {
      // Silently fail - indicator will show 0%
      console.debug('[TokenUsageRing] Failed to fetch stats:', err);
    } finally {
      setIsLoading(false);
    }
  }, [currentThreadId, currentModel]);

  // Fetch on mount and when thread/model/messages change
  useEffect(() => {
    fetchStats();
  }, [fetchStats, messageCount]);

  // Refresh after compaction completes
  useEffect(() => {
    if (wasCompacting.current && !compactionInfo?.isCompacting) {
      // Compaction just finished - refresh stats
      setTimeout(fetchStats, 300);
    }
    wasCompacting.current = compactionInfo?.isCompacting;
  }, [compactionInfo?.isCompacting, fetchStats]);
  
  // Refresh on model/provider switch
  useEffect(() => {
    if (previousModel.current !== currentModel) {
      previousModel.current = currentModel;
      setTimeout(fetchStats, 200);
    }
  }, [currentModel, fetchStats]);

  // Calculate ring properties
  const strokeWidth = size <= 18 ? 2 : size <= 22 ? 2.5 : 3;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (usagePercent / 100) * circumference;

  // Get color based on pressure level
  const getColor = () => {
    switch (pressureLevel) {
      case 'critical': return '#D13438';
      case 'high': return '#CA5010';
      case 'medium': return '#FFB900';
      default: return '#107C10';
    }
  };

  const color = getColor();

  // Format numbers for tooltip
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
    return num.toString();
  };

  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        cursor: 'default',
      }}
      title={`Context: ${formatNumber(totalUsed)} / ${formatNumber(totalUsed + remaining)} tokens (${usagePercent.toFixed(0)}%)`}
    >
      <svg
        width={size}
        height={size}
        style={{
          transform: 'rotate(-90deg)',
          opacity: isLoading ? 0.5 : 1,
          transition: 'opacity 0.2s',
        }}
      >
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#E1DFDD"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{
            transition: 'stroke-dashoffset 0.3s ease, stroke 0.3s ease',
          }}
        />
      </svg>
    </div>
  );
};

export default TokenUsageRing;

