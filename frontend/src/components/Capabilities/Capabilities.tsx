import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  BarChart3, TrendingUp, PieChart, Download, ArrowUpRight,
  Layers, Brain, Search, Shield, Network, FileText, Code2,
  Activity, Workflow, Database, Cpu, Globe, Lock, Zap,
} from 'lucide-react';
import BinomialLogo from '../../assets/binomial-icon-logo.png';
import '../Landing/Landing.css';

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
        <Link to="/capabilities" className="l2-nav-link" style={{ color: '#111' }}>Capabilities</Link>
        <Link to="/performance" className="l2-nav-link">Performance</Link>
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

// Mini-Visual Components for "Deep Dives"
const QuantVisual = () => (
  <div style={{ position: 'relative', height: '100%', width: '100%', background: '#e9f2ff', borderRadius: 16, overflow: 'hidden', padding: 24, border: '1px solid #d0e1fd' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
      <div style={{ fontSize: 12, color: '#555', fontWeight: 600 }}>MODEL EXECUTION</div>
      <div style={{ fontSize: 12, color: '#059669' }}>Active</div>
    </div>
    {/* Code / Matrix Visual */}
    <div style={{ fontFamily: '"Source Code Pro", "Monaco", monospace', fontSize: 13, color: '#1f2937', lineHeight: 1.6 }}>
      <div>def optimize_portfolio(returns, cov_matrix):</div>
      <div style={{ marginLeft: 12, color: '#4b5563' }}>weights = cp.Variable(n)</div>
      <div style={{ marginLeft: 12 }}>risk = cp.quad_form(weights, cov)</div>
      <div style={{ marginLeft: 12 }}>prob = cp.Problem(cp.Minimize(risk))</div>
      <div style={{ marginTop: 12, color: '#2563eb' }}># Solving for Efficient Frontier...</div>
      <div style={{ marginTop: 4, color: '#059669' }}>&gt; Optimal Sharpe: 2.45</div>
      <div style={{ marginTop: 4, color: '#059669' }}>&gt; Exp. Return: 18.2%</div>
    </div>
    {/* Overlay Chart */}
    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 80, background: 'linear-gradient(to top, rgba(255,255,255,0.8), transparent)' }} />
  </div>
);

const RiskVisual = () => (
  <div style={{ position: 'relative', height: '100%', width: '100%', background: '#fff', borderRadius: 16, border: '1px solid #eee', padding: 24 }}>
     <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
       <div style={{ flex: 1, padding: 12, background: '#FEF2F2', borderRadius: 8 }}>
         <div style={{ fontSize: 10, color: '#991B1B', fontWeight: 600 }}>VaR (95%)</div>
         <div style={{ fontSize: 18, fontWeight: 600, color: '#DC2626' }}>-2.4%</div>
       </div>
       <div style={{ flex: 1, padding: 12, background: '#F3F4F6', borderRadius: 8 }}>
         <div style={{ fontSize: 10, color: '#4B5563', fontWeight: 600 }}>BETA</div>
         <div style={{ fontSize: 18, fontWeight: 600, color: '#111' }}>0.85</div>
       </div>
     </div>
     {/* Heatmap Grid */}
     <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 4 }}>
       {Array.from({ length: 24 }).map((_, i) => (
         <div key={i} style={{
           height: 20,
           background: i % 5 === 0 ? '#FCA5A5' : i % 3 === 0 ? '#F3F4F6' : '#10B981',
           opacity: 0.6,
           borderRadius: 2,
         }} />
       ))}
     </div>
  </div>
);

const CapabilityGrid = () => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32, marginTop: 80 }}>
      {[
        { title: 'Quantitative Modeling', desc: 'Advanced algorithmic strategies, options pricing models, ETF arbitrage, and order flow analytics with backtesting.' },
        { title: 'Technical Analysis', desc: 'Professional charting tools with 100+ indicators, pattern recognition, custom studies, and multi-timeframe analysis.' },
        { title: 'Valuation Models', desc: 'Institutional-grade DCF, comparable company analysis, sum-of-parts modeling, and sensitivity scenarios.' },
        { title: 'Risk Analytics', desc: 'VaR calculations, stress testing, correlation analysis, portfolio optimization, and hedge construction tools.' },
        { title: 'Alternative Data', desc: 'Integration of non-traditional datasets including ESG metrics, satellite imagery, and patent analytics.' },
        { title: 'Agentic Coding', desc: 'AI-powered code generation for custom financial models, automated analysis scripts, and programmable strategies.' },
        { title: 'Portfolio Tracking', desc: 'Real-time portfolio monitoring, performance attribution, risk metrics, and automated rebalancing alerts.' },
        { title: 'SEC Filing Search', desc: 'AI-powered document analysis of 10-K, 10-Q, 8-K filings with natural language query extraction.' },
        { title: 'Financial Search', desc: 'Intelligent research assistant autonomously gathering market data, earnings reports, and statements.' },
        { title: 'Workflow Builder', desc: 'Drag-and-drop interface to construct custom analysis pipelines and automated report generation.' },
        { title: 'Crypto & Options', desc: 'Cryptocurrency analytics, listed options chains with Greeks, and options flow analysis.' },
        { title: 'Fixed Income', desc: 'Bond analytics, yield curve analysis, and credit spread monitoring.' },
      ].map((item, i) => (
        <div key={i} className="l2-feature-card" style={{ padding: 32, minHeight: 200, border: '1px solid rgba(0,0,0,0.06)' }}>
           <h3 className="l2-feature-title" style={{ fontSize: '1.15rem', marginBottom: 12 }}>{item.title}</h3>
           <p className="l2-feature-desc" style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{item.desc}</p>
        </div>
      ))}
    </div>
);

const Capabilities = () => {
  return (
    <div className="landing2-page">
      <Navbar />

      {/* Hero */}
      <section className="l2-hero" style={{ minHeight: '80vh', paddingBottom: 0 }}>
        <div className="l2-hero-grid" style={{ gridTemplateColumns: '1fr' }}>
          <div className="l2-hero-content" style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center' }}>
            <span className="l2-hero-badge" style={{ marginBottom: '24px' }}>
              <span className="l2-hero-badge-dot"></span>
              <span className="l2-hero-badge-text">System Capabilities</span>
            </span>

            <h1 className="l2-hero-title">
              Institutional Grade.<br />
              <span>Agentic Power.</span>
            </h1>

            <p className="l2-hero-subtitle" style={{ margin: '0 auto 40px' }}>
              A complete investment intelligence suite combining quantitative rigor with autonomous AI agents.
              From idea generation to risk management.
            </p>
          </div>
        </div>
      </section>

      {/* Deep Dive 1: Quantitative Core */}
      <section style={{ padding: '120px 40px', background: '#fff', borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80, alignItems: 'center' }}>
          <div>
             <div style={{ fontSize: 12, fontWeight: 600, color: '#EB5E28', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 16 }}>Core Analytics</div>
             <h2 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2.5rem', marginBottom: 24, color: '#111' }}>Quantitative Modeling Engine</h2>
             <p style={{ fontSize: '1.1rem', lineHeight: 1.7, color: '#666', marginBottom: 32 }}>
               Our proprietary Python-based engine executes complex financial models in real-time. Unlike standard LLMs that hallucinate math, Sentry delegates calculations to a rigorous code execution environment.
             </p>
             <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
               {[
                 'Automated DCF & Comparable Company Analysis',
                 'Black-Scholes Option Pricing & Greeks',
                 'Monte Carlo Simulations (10,000+ paths)',
                 'Efficient Frontier Portfolio Optimization',
               ].map((item, i) => (
                 <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.95rem', color: '#444' }}>
                   <div style={{ width: 6, height: 6, background: '#111', borderRadius: '50%' }} />
                   {item}
                 </li>
               ))}
             </ul>
          </div>
          <div style={{ height: 400 }}>
            <QuantVisual />
          </div>
        </div>
      </section>

      {/* Deep Dive 2: Risk & Portfolio */}
      <section style={{ padding: '120px 40px', background: '#F5F4EF' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80, alignItems: 'center' }}>
          <div style={{ height: 400, order: 0 }}> {/* Visual Left */}
            <RiskVisual />
          </div>
          <div style={{ order: 1 }}>
             <div style={{ fontSize: 12, fontWeight: 600, color: '#EB5E28', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 16 }}>Risk Management</div>
             <h2 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2.5rem', marginBottom: 24, color: '#111' }}>Advanced Risk Analytics</h2>
             <p style={{ fontSize: '1.1rem', lineHeight: 1.7, color: '#666', marginBottom: 32 }}>
               Monitor portfolio health with institutional risk metrics. Sentry continuously scans your positions against market volatility, correlation shifts, and tail risks.
             </p>
             <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
               {[
                 'Value at Risk (VaR) & CVaR / Expected Shortfall',
                 'Factor Exposure Analysis (Fama-French)',
                 'Correlation Matrices & Diversification Scores',
                 'Automated Hedge Construction Suggestions',
               ].map((item, i) => (
                 <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.95rem', color: '#444' }}>
                   <div style={{ width: 6, height: 6, background: '#111', borderRadius: '50%' }} />
                   {item}
                 </li>
               ))}
             </ul>
          </div>
        </div>
      </section>

      {/* Comprehensive Feature List */}
      <section style={{ padding: '120px 40px' }}>
         <div style={{ maxWidth: 1400, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', maxWidth: 800, margin: '0 auto 60px' }}>
               <h2 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2.5rem', marginBottom: 16, color: '#111' }}>Complete Capability Index</h2>
               <p style={{ fontSize: '1.1rem', color: '#666' }}>Every tool required for modern investment analysis, integrated into one platform.</p>
            </div>
            <CapabilityGrid />
         </div>
      </section>

       {/* Technical Specs Grid */}
      <section style={{ padding: '120px 40px', background: '#111', color: '#fff' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          <div style={{ marginBottom: 80, textAlign: 'center' }}>
            <h2 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3rem', marginBottom: 16 }}>Platform Reliability</h2>
            <p style={{ color: '#888', maxWidth: 600, margin: '0 auto' }}>Institutional-grade performance metrics.</p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.1)' }}>
            {[
              { title: 'Time Savings', val: '70-75%', sub: 'reduction in financial workflows' },
              { title: 'Data Accuracy', val: '99.2%', sub: 'vs 68.4% in frontier LLMs' },
              { title: 'Response Time', val: '<90s', sub: 'for complex valuation & modeling' },
              { title: 'Coverage', val: '600+', sub: 'companies analyzed daily' },
              { title: 'Models', val: '15', sub: 'fine-tuned frontier LLMs' },
              { title: 'Security', val: 'RLS', sub: 'Row-Level Security isolation' },
            ].map((spec, i) => (
              <div key={i} style={{ background: '#111', padding: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                <div style={{ color: '#666', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>{spec.title}</div>
                <div style={{ fontSize: 32, fontWeight: 500, color: '#fff', marginBottom: 8, fontFamily: 'var(--l2-font-serif)' }}>{spec.val}</div>
                <div style={{ color: '#444', fontSize: 13 }}>{spec.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

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
    </div>
  );
};

export default Capabilities;
