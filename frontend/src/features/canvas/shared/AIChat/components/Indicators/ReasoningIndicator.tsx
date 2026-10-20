interface ReasoningIndicatorProps {
  reasoningStreaming: boolean;
  reasoningText: string;
}

export function ReasoningIndicator({ reasoningStreaming, reasoningText }: ReasoningIndicatorProps) {
  return (
    <div className="mb-2 pl-7">
      <div className="flex items-center gap-1.5 mb-1">
        <div className="w-3 h-3 flex items-center justify-center">
          {reasoningStreaming ? (
            <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-pulse" />
          ) : (
            <span className="text-[9px]">💭</span>
          )}
        </div>
        <span className="text-[10px] font-medium text-gray-500">Reasoning</span>
      </div>
      {reasoningText && (
        <div className="text-sm text-gray-800 opacity-60 leading-relaxed pl-5">
          {(() => {
            const lines = reasoningText.split('\n');
            const lastThreeLines = lines.slice(-3);
            return lastThreeLines.join('\n');
          })()}
        </div>
      )}
    </div>
  );
}
