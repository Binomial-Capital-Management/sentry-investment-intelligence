import { useChatStore } from '@/stores/chatStore';
import { Loader2 } from 'lucide-react';

export const CompactionIndicator = () => {
  const compactionInfo = useChatStore(state => state.compactionInfo);

  if (!compactionInfo.isCompacting) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-2 py-1 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
      <Loader2 className="h-3 w-3 animate-spin text-blue-600" />
      <span>
        Compacting {compactionInfo.from?.toUpperCase()} → {compactionInfo.to?.toUpperCase()}
      </span>
    </div>
  );
};

export default CompactionIndicator;
