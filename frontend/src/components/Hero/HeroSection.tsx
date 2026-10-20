import { useChat } from '@/hooks/useChat';

const HeroSection = () => {
  const { sendMessage } = useChat();

  const suggestedQueries = [
    'Calculate VaR and CVaR for my portfolio using Monte Carlo simulation with 10,000 paths',
    'Perform Barra factor decomposition and identify systematic risk exposures in my holdings',
    'Build an optimal hedge portfolio to achieve market neutrality while preserving alpha',
    'Run comparative valuation analysis against sector peers using EV/EBITDA and P/E multiples',
  ];

  const handleSuggestedQuery = (query: string) => {
    sendMessage(query);
  };

  return (
    <div className="flex items-center justify-center min-h-full" style={{ background: '#FFFFFF', padding: '31px' }}>
      <div className="w-full" style={{ maxWidth: 720 }}>
        <div className="text-center mb-11">
          <div className="flex justify-center mb-6">
            <img
              src="/binomial-icon-logo.png"
              className="h-20 w-20"
              alt="Binomial Risk Analyst"
            />
          </div>
          <h1 className="mb-2" style={{
            fontSize: '32px',
            fontWeight: '600',
            color: '#323130',
            letterSpacing: '-0.5px',
            fontFamily: '"Segoe UI Variable", "Segoe UI", sans-serif',
          }}>
            Sentry Investment Intelligence
          </h1>
          <p style={{
            fontSize: '14px',
            color: '#605E5C',
            fontWeight: '500',
          }}>
            Developed by Binomial Technologies
          </p>
        </div>

        <div className="grid grid-cols-1 gap-2" style={{ maxWidth: 720, margin: '0 auto' }}>
          {suggestedQueries.map((query, index) => (
            <button
              key={index}
              onClick={() => handleSuggestedQuery(query)}
              className="text-left transition-all duration-150 group"
              style={{
                padding: '16px',
                border: '1px solid #E1DFDD',
                borderRadius: '6px',
                background: '#FFFFFF',
                cursor: 'pointer',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#0078D4';
                e.currentTarget.style.background = '#FAF9F8';
                e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#E1DFDD';
                e.currentTarget.style.background = '#FFFFFF';
                e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';
              }}
            >
              <span style={{
                fontSize: '14px',
                color: '#323130',
                fontFamily: '"Segoe UI Variable", "Segoe UI", sans-serif',
                lineHeight: '1.6',
              }}>
                {query}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default HeroSection;
