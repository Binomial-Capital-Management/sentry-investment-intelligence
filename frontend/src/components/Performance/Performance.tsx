import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowUpRight, TrendingUp, Activity, BarChart3, PieChart, Calendar } from 'lucide-react';
import BinomialLogo from '../../assets/binomial-icon-logo.png';
import '../Landing/Landing.css'; // Use Landing2 styles
import { useUser } from '@clerk/clerk-react';

// Reusing Navbar
const Navbar = () => {
  const { isSignedIn } = useUser();

  return (
    <motion.nav
      className="l2-nav"
      initial={{ y: -100, x: '-50%' }}
      animate={{ y: 0, x: '-50%' }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
    >
      <Link to="/" className="l2-nav-logo">
        <img src={BinomialLogo} alt="Sentry" style={{ height: 32, width: 'auto' }} />
      </Link>
      <div className="l2-nav-links">
        <Link to="/about" className="l2-nav-link">About</Link>
        <Link to="/capabilities" className="l2-nav-link">Capabilities</Link>
        <Link to="/performance" className="l2-nav-link" style={{ color: '#111' }}>Performance</Link>
        <Link to="/pricing" className="l2-nav-link">Pricing</Link>
        <Link to="/contact" className="l2-nav-link">Contact</Link>
      </div>
      {isSignedIn ? (
        <Link to="/chat" className="l2-nav-cta">Launch Platform</Link>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link to="/login" className="l2-nav-link" style={{ background: 'transparent', border: 'none', padding: '8px 16px' }}>Login</Link>
          <Link to="/register" className="l2-nav-cta" style={{ marginLeft: 0 }}>Get Started</Link>
        </div>
      )}
    </motion.nav>
  );
};

const Footer = () => (
  <footer className="l2-footer">
    <div className="l2-footer-grid">
      <div className="l2-footer-brand">
        <div className="l2-brand-header">
          <img src={BinomialLogo} alt="Sentry" className="l2-footer-logo" />
          <h2>Sentry Intelligence</h2>
        </div>
        <p className="l2-footer-desc">
          Developed by Binomial Capital Management.
          <br />
          Your trusted analytical partner.
          <br /><br />
          © 2025 Sentry Intelligence. All rights reserved.
        </p>
      </div>
      <div className="l2-footer-col">
        <h4>Platform</h4>
        <Link to="/capabilities" className="l2-footer-link">Capabilities</Link>
        <Link to="/performance" className="l2-footer-link">Performance</Link>
        <Link to="/about" className="l2-footer-link">About</Link>
        <Link to="/login" className="l2-footer-link">Login</Link>
      </div>
      <div className="l2-footer-col">
        <h4>Company</h4>
        <a href="https://www.bcmassets.com" target="_blank" rel="noreferrer" className="l2-footer-link">Binomial Capital</a>
        <a href="https://www.linkedin.com/company/binomialtec" target="_blank" rel="noreferrer" className="l2-footer-link">LinkedIn</a>
        <Link to="/contact" className="l2-footer-link">Contact</Link>
      </div>
      <div className="l2-footer-col">
        <h4>Legal</h4>
        <Link to="/privacy" className="l2-footer-link">Privacy Policy</Link>
        <Link to="/terms" className="l2-footer-link">Terms of Service</Link>
      </div>
    </div>
  </footer>
);

const PerformanceChart = () => {
  // Simulated cumulative return data
  const dataPoints = [
    0, 2, 4, 3, 5, 8, 12, 11, 15, 18, 22, 25, 24, 28, 32, 35, 38, 42, 45, 48, 52, 55, 58.9,
  ];

  // Generate SVG path
  const width = 800;
  const height = 300;
  const padding = 40;
  const points = dataPoints.map((val, i) => {
    const x = (i / (dataPoints.length - 1)) * (width - padding * 2) + padding;
    const y = height - ((val / 60) * (height - padding * 2) + padding);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div style={{ width: '100%', overflow: 'hidden', borderRadius: 24, border: '1px solid rgba(0,0,0,0.06)', background: '#fff', padding: 32, boxShadow: '0 10px 30px -10px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 4 }}>Cumulative Return</h3>
          <p style={{ color: '#666', fontSize: '0.9rem' }}>Inception to Date (Gross)</p>
        </div>
        <div style={{ textAlign: 'right' }}>
           <div style={{ fontSize: '2rem', fontWeight: 500, fontFamily: 'var(--l2-font-serif)', color: '#10B981' }}>+58.9%</div>
           <div style={{ fontSize: '0.9rem', color: '#10B981', background: '#ECFDF5', display: 'inline-block', padding: '2px 8px', borderRadius: 100, fontWeight: 600 }}>Outperforming</div>
        </div>
      </div>

      <div style={{ position: 'relative', height: 300 }}>
        <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
          {/* Grid Lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
             <line
               key={i}
               x1={padding}
               y1={padding + t * (height - 2 * padding)}
               x2={width - padding}
               y2={padding + t * (height - 2 * padding)}
               stroke="#E5E7EB"
               strokeWidth="1"
               strokeDasharray="4 4"
             />
          ))}

          {/* Area Gradient */}
          <defs>
            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10B981" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
            </linearGradient>
          </defs>

          <path
            d={`M ${padding},${height - padding} L ${points.split(' ')[0]} ${points.replace(/,/g, ' L ')} L ${width - padding},${height - padding} Z`}
            fill="url(#chartGradient)"
          />

          {/* Line */}
          <motion.path
            d={`M ${points.replace(/ /g, ' L ')}`}
            fill="none"
            stroke="#10B981"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            whileInView={{ pathLength: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 2, ease: 'easeInOut' }}
          />
        </svg>
      </div>
    </div>
  );
};

const Performance = () => {
  return (
    <div className="landing2-page">
      <Navbar />

      <section className="l2-hero" style={{ minHeight: '60vh', paddingBottom: 0 }}>
        <div className="l2-hero-grid" style={{ gridTemplateColumns: '1fr' }}>
          <div className="l2-hero-content" style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center' }}>
            <span className="l2-hero-badge" style={{ marginBottom: '24px' }}>
              <span className="l2-hero-badge-dot"></span>
              <span className="l2-hero-badge-text">Track Record</span>
            </span>

            <h1 className="l2-hero-title">
              Proven Results.<br />
              <span>Transparent Metrics.</span>
            </h1>

            <p className="l2-hero-subtitle" style={{ margin: '0 auto 40px' }}>
              Sentry Intelligence combines state-of-the-art AI precision with institutional-grade strategy performance.
              Below are the core performance metrics of the AI models themselves, alongside results of strategies utilizing our platform.
            </p>
          </div>
        </div>
      </section>

      <section style={{ padding: '0 40px 120px', position: 'relative', zIndex: 2 }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>

          {/* AI System Metrics - Top Priority */}
          <div style={{ marginBottom: 80 }}>
            <h3 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2rem', marginBottom: 24, textAlign: 'center' }}>AI System Metrics</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
               <div className="l2-feature-card" style={{ padding: 32, background: '#111', color: '#fff', border: 'none' }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', opacity: 0.6, marginBottom: 12 }}>Data Accuracy</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, marginBottom: 8 }}>99.2%</div>
                 <div style={{ fontSize: 14, color: '#10B981' }}>vs 68.4% in frontier LLMs</div>
               </div>
               <div className="l2-feature-card" style={{ padding: 32 }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#666', marginBottom: 12 }}>Time Savings</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, marginBottom: 8, color: '#111' }}>~75%</div>
                 <div style={{ fontSize: 14, color: '#666' }}>in financial workflows</div>
               </div>
               <div className="l2-feature-card" style={{ padding: 32 }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#666', marginBottom: 12 }}>Daily Coverage</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, marginBottom: 8, color: '#111' }}>600+</div>
                 <div style={{ fontSize: 14, color: '#666' }}>companies analyzed</div>
               </div>
               <div className="l2-feature-card" style={{ padding: 32 }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#666', marginBottom: 12 }}>Models Ensembled</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, marginBottom: 8, color: '#111' }}>15</div>
                 <div style={{ fontSize: 14, color: '#666' }}>fine-tuned agents</div>
               </div>
            </div>
          </div>

          {/* Strategy Performance Section */}
          <div style={{ marginBottom: 80, borderTop: '1px solid #E5E7EB', paddingTop: 80 }}>
             <div style={{ textAlign: 'center', marginBottom: 40 }}>
               <h3 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2rem', marginBottom: 16 }}>Strategy Validation</h3>
               <p style={{ color: '#666' }}>Results from strategies utilizing Sentry Intelligence</p>
             </div>

             {/* Fund Metrics */}
             <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 40 }}>
               <div className="l2-feature-card" style={{ padding: 32 }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#666', marginBottom: 12 }}>Since Inception</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '4rem', lineHeight: 1, marginBottom: 8, color: '#111' }}>58.9%</div>
                 <div style={{ fontSize: 14, color: '#10B981' }}>Strategies utilizing Sentry</div>
               </div>
               <div className="l2-feature-card" style={{ padding: 32 }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#666', marginBottom: 12 }}>Sharpe Ratio</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '4rem', lineHeight: 1, marginBottom: 8, color: '#111' }}>3.21</div>
                 <div style={{ fontSize: 14, color: '#666' }}>Risk-adjusted optimization</div>
               </div>
               <div className="l2-feature-card" style={{ padding: 32 }}>
                 <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#666', marginBottom: 12 }}>Jensen's Alpha</div>
                 <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '4rem', lineHeight: 1, marginBottom: 8, color: '#111' }}>46.8%</div>
                 <div style={{ fontSize: 14, color: '#666' }}>Excess return vs Benchmark</div>
               </div>
             </div>

             {/* Chart */}
             <div style={{ marginBottom: 40 }}>
               <PerformanceChart />
             </div>

             {/* Risk Profile Strip */}
             <div style={{ background: '#F9FAFB', borderRadius: 24, padding: 40 }}>
                <h4 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '1.5rem', marginBottom: 24, textAlign: 'center' }}>Risk Profile</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
                  {[
                    { label: 'Max Drawdown', val: '-16.1%' },
                    { label: 'Volatility (Ann.)', val: '12.2%' },
                    { label: 'Sortino Ratio', val: '6.4' },
                    { label: 'Beta', val: '0.37' },
                  ].map((stat, i) => (
                    <div key={i} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>{stat.label}</div>
                      <div style={{ fontSize: '2rem', fontWeight: 600, color: '#111' }}>{stat.val}</div>
                    </div>
                  ))}
                </div>
             </div>
          </div>

          <div style={{ padding: 40, background: '#F5F4EF', borderRadius: 24, display: 'flex', flexDirection: 'column', justifyContent: 'center', textAlign: 'center' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 16 }}>Disclaimer</h3>
              <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: '#666', marginBottom: 12, maxWidth: 800, margin: '0 auto 12px' }}>
                Past performance is not indicative of future results. The metrics presented above represent the performance of strategies managed by human investment teams using the Sentry Intelligence platform. Sentry Intelligence is an analytical tool and does not autonomously execute trades.
              </p>
              <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: '#666', maxWidth: 800, margin: '0 auto' }}>
                These figures are provided for demonstration purposes to illustrate the capabilities of the analytical engine. Investment involves risk, including possible loss of principal. System metrics based on internal benchmarking vs frontier LLMs.
              </p>
          </div>

        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Performance;
