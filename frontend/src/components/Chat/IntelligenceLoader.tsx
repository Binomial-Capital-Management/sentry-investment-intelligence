import { memo, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface IntelligenceLoaderProps {
  agent?: string;
  text?: string; // Explicit text override
  isComplete?: boolean;
  compact?: boolean;
  currentTool?: {
    name: string;
    status: string;
    type?: string;
  };
}

const AGENT_STATUSES: Record<string, string[]> = {
  generalist: [
    'Reviewing conversation context...',
    'Identifying data requirements...',
    'Formulating analysis plan...',
    'Consulting knowledge base...',
    'Synthesizing findings...',
    'Structuring response...',
  ],
  risk_specialist: [
    'Calibrating risk models...',
    'Computing Value at Risk (VaR)...',
    'Running Monte Carlo simulations...',
    'Analyzing portfolio volatility...',
    'Stress testing positions...',
    'Evaluating correlation matrices...',
    'Calculating Sharpe ratios...',
    'Assessing tail risk...',
  ],
  document_analyst: [
    'Indexing SEC filings...',
    'Extracting financial tables...',
    'Cross-referencing footnotes...',
    'Summarizing key risk factors...',
    'Parsing 10-K/10-Q structure...',
    'Locating management discussion...',
    'Analyzing item 1A (Risk Factors)...',
  ],
  comparable_companies: [
    'Screening peer universe...',
    'Normalizing valuation multiples...',
    'Fetching EV/EBITDA ratios...',
    'Analyzing industry averages...',
    'Calculating peer group median...',
    'Adjusting for capital structure...',
  ],
  chart_analyst: [
    'Fetching historical price data...',
    'Calculating technical indicators...',
    'Identifying chart patterns...',
    'Rendering visualization...',
    'Applying moving averages...',
    'Analyzing volume profile...',
  ],
  orchestrator: [
    'Decomposing user request...',
    'Selecting specialized agents...',
    'Optimizing execution path...',
    'Aggregating multi-agent results...',
    'Planning workflow...',
  ],
  institutional_activity: [
    'Tracking insider trades...',
    'Analyzing 13F filings...',
    'Monitoring congressional trading...',
    'Detecting accumulation patterns...',
    'Aggregating flow data...',
  ],
  quant_coding: [
    'Generating Python script...',
    'Executing quantitative model...',
    'Processing large datasets...',
    'Validating calculation results...',
    'Debugging execution...',
    'Formatting output...',
  ],
  alternatives_coding: [
    'Fetching cryptocurrency data...',
    'Analyzing alternative assets...',
    'Correlating cross-asset flows...',
    'Checking macro signals...',
  ],
  dcf_valuation: [
    'Projecting free cash flows...',
    'Estimating WACC parameters...',
    'Calculating terminal value...',
    'Running sensitivity analysis...',
    'Discounting future flows...',
  ],
  screener: [
    'Filtering market universe...',
    'Applying technical criteria...',
    'Screening fundamental metrics...',
    'Ranking candidates...',
    'Analyzing sector performance...',
  ],
  options_analyst: [
    'Calculating option Greeks...',
    'Analyzing implied volatility...',
    'Modelling option pricing...',
    'Evaluating put-call ratios...',
    'Assessing skew structure...',
  ],
  funds_analyst: [
    'Analyzing fund composition...',
    'Evaluating expense ratios...',
    'Tracking tracking error...',
    'Comparing benchmark performance...',
    'Assessing sector exposure...',
  ],
  prediction_markets: [
    'Aggregating market probabilities...',
    'Analyzing event contracts...',
    'Correlating outcome signals...',
    'Tracking volume trends...',
  ],
  private_markets: [
    ' analyzing venture capital trends...',
    'Evaluating private equity deals...',
    'Tracking funding rounds...',
    'Assessing pre-IPO valuations...',
  ],
  default: [
    'Thinking...',
    'Processing request...',
    'Analyzing data...',
    'Formulating response...',
  ],
};

const getStatusFromTool = (tool: { name: string; status: string; type?: string }) => {
  const name = (tool.name || '').toLowerCase();
  const status = tool.status;

  // Status-specific overrides
  if (status === 'completed') return `Finished ${tool.name}`;
  if (status === 'failed') return `Retrying ${tool.name}...`;
  if (status === 'arguments_delta') return `Configuring ${tool.name}...`;

  // Tool-specific mappings
  if (name.includes('fmp') || name.includes('stock') || name.includes('price') || name.includes('quote')) {
    return 'Fetching market data...';
  }
  if (name.includes('sec') || name.includes('filing') || name.includes('10-k') || name.includes('10-q')) {
    return 'Reading SEC documents...';
  }
  if (name.includes('search') || name.includes('google') || name.includes('bing')) {
    return 'Searching the web...';
  }
  if (name.includes('code') || name.includes('python') || name.includes('exec')) {
    return status === 'interpreting' || status === 'code_delta' ? 'Running Python code...' : 'Writing code...';
  }
  if (name.includes('calculate') || name.includes('compute')) {
    return 'Calculating metrics...';
  }
  if (name.includes('risk') || name.includes('var') || name.includes('monte')) {
    return 'Running risk models...';
  }
  if (name.includes('optimize') || name.includes('efficient')) {
    return 'Optimizing portfolio...';
  }
  if (name.includes('chart') || name.includes('plot') || name.includes('visual')) {
    return 'Generating charts...';
  }
  if (name.includes('news') || name.includes('article')) {
    return 'Scanning news feeds...';
  }
  if (name.includes('financial') || name.includes('statement') || name.includes('balance')) {
    return 'Analyzing financial statements...';
  }
  if (name.includes('earnings') || name.includes('transcript')) {
    return 'Reading earnings transcripts...';
  }

  // Fallback using capitalized name
  return `Running ${tool.name}...`;
};

const IntelligenceLoader = memo(({ text, isComplete, compact, agent = 'generalist', currentTool }: IntelligenceLoaderProps) => {
  const [statusIdx, setStatusIdx] = useState(0);
  const [shouldHide, setShouldHide] = useState(false);

  useEffect(() => {
    if (isComplete) {
      const timeout = setTimeout(() => setShouldHide(true), 800);
      return () => clearTimeout(timeout);
    }

    // Rotate generic status every 1.2s if no specific tool is active
    // This makes it feel more "alive"
    const interval = setInterval(() => {
      setStatusIdx((prev) => prev + 1);
    }, 2500);

    return () => clearInterval(interval);
  }, [isComplete]);

  if (shouldHide) return null;

  // Determine text to display
  let displayText = text;

  if (!displayText) {
    if (isComplete) {
      displayText = 'Finished';
    } else if (currentTool && currentTool.status !== 'completed' && currentTool.status !== 'failed') {
      // If a tool is active, use its status (highest priority)
      displayText = getStatusFromTool(currentTool);
    } else {
      // Fallback to rotating agent statuses
      // Normalize agent name to match keys
      const normalizedAgent = agent.toLowerCase().replace('agent', '').replace(/s$/, '');
      const key = Object.keys(AGENT_STATUSES).find(k => normalizedAgent.includes(k)) || 'default';
      const statuses = AGENT_STATUSES[key] || AGENT_STATUSES.default;
      displayText = statuses[statusIdx % statuses.length];
    }
  }

  // Compact mode (for inline/streaming)
  if (compact) {
    return (
      <div className="inline-flex items-center gap-2 opacity-90 select-none">
        <motion.div
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.6, 1, 0.6],
          }}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          <img
            src="/binomial-icon-logo.png"
            alt="Loading"
            className="w-3.5 h-3.5 grayscale-0"
          />
        </motion.div>
        {text && (
          <span className="text-xs text-gray-500 font-medium tracking-wide font-mono">
            {text}
          </span>
        )}
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-3 py-3 px-1 my-1 select-none"
    >
      <motion.div
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.6, 1, 0.6],
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="relative w-5 h-5 flex-shrink-0"
      >
        <img
          src="/binomial-icon-logo.png"
          alt="Sentry"
          className="w-full h-full object-contain grayscale-0"
        />
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.span
          key={displayText}
          initial={{ opacity: 0, y: 2, filter: 'blur(2px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -2, filter: 'blur(2px)' }}
          transition={{ duration: 0.3 }}
          className="text-[13px] text-gray-600 font-medium tracking-wide"
        >
          {displayText}
        </motion.span>
      </AnimatePresence>
    </motion.div>
  );
});

IntelligenceLoader.displayName = 'IntelligenceLoader';

export default IntelligenceLoader;
