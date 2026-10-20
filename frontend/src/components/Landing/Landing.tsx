import React, { useRef, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, useScroll, useTransform, useSpring, useInView, AnimatePresence, useMotionValue } from 'framer-motion';
import { ArrowUpRight, ChevronRight, BarChart3, Shield, Zap, Globe, Lock, Cpu, Terminal, Activity, Layers, Play, CheckCircle2, MessageCircle, Briefcase, TrendingUp, Calendar, Network, Settings, Home, Pause, Edit, Trash2, Calculator, FileText, Workflow, PieChart, Database, LayoutGrid, Search, FileCheck, AlertTriangle, TrendingDown, Share2, Download, Eye, LineChart, BriefcaseBusiness, CandlestickChart, DollarSign, Scale, FileStack } from 'lucide-react';
import BinomialLogo from '../../assets/binomial-icon-logo.png';
import './Landing.css';

// --- Components ---

import { useUser } from '@clerk/clerk-react';

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

// 3D Visual Component (Abstract UI Stack)
const HeroVisual = () => {
  return (
    <div className="l2-hero-visual">
      {/* Floating Card 1: Chat Interface (Left, Dominant) */}
      <motion.div
        className="l2-3d-card"
        style={{ width: 320, height: 400, top: '10%', left: '5%', zIndex: 3 }}
        animate={{
          y: [0, -15, 0],
          rotateX: [2, -2, 2],
          rotateY: [5, 8, 5],
        }}
        transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut' }}
      >
        <div className="l2-visual-card-glass">
          <div className="l2-visual-header">
            <div className="l2-visual-dots">
              <div className="l2-dot red" />
              <div className="l2-dot yellow" />
              <div className="l2-dot green" />
            </div>
            <div className="l2-visual-title-group">
              <span className="l2-visual-title">Analyst Chat</span>
              <span className="l2-visual-subtitle">AI Agent</span>
            </div>
          </div>
          <div className="l2-visual-content">
            <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#E5E7EB' }}></div>
              <div style={{ flex: 1 }}>
                <div style={{ width: '70%', height: 8, background: '#F3F4F6', borderRadius: 4, marginBottom: 8 }}></div>
                <div style={{ width: '40%', height: 8, background: '#F3F4F6', borderRadius: 4 }}></div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexDirection: 'row-reverse' }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#111' }}></div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <div style={{ width: '80%', height: 8, background: '#F3F4F6', borderRadius: 4, marginBottom: 8 }}></div>
                <div style={{ width: '90%', height: 8, background: '#F3F4F6', borderRadius: 4, marginBottom: 8 }}></div>
                <div style={{ width: '60%', height: 8, background: '#F3F4F6', borderRadius: 4 }}></div>
              </div>
            </div>
             <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#E5E7EB' }}></div>
              <div style={{ flex: 1 }}>
                <div style={{ width: '50%', height: 8, background: '#F3F4F6', borderRadius: 4, marginBottom: 8 }}></div>
                <div style={{ width: '65%', height: 8, background: '#F3F4F6', borderRadius: 4 }}></div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Floating Card 2: Chart (Right, Secondary) */}
      <motion.div
        className="l2-3d-card"
        style={{ width: 340, height: 240, top: '5%', right: '5%', zIndex: 2 }}
        animate={{
          y: [0, 20, 0],
          rotateX: [5, 8, 5],
          rotateY: [-5, 0, -5],
        }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
      >
        <div className="l2-visual-card-glass">
          <div className="l2-visual-header">
            <div className="l2-visual-dots">
              <div className="l2-dot red" />
              <div className="l2-dot yellow" />
              <div className="l2-dot green" />
            </div>
            <div className="l2-visual-title-group">
              <span className="l2-visual-title">Portfolio Alpha</span>
              <span className="l2-visual-subtitle">Live Metrics</span>
            </div>
          </div>
          <div className="l2-visual-content" style={{ display: 'flex', alignItems: 'flex-end', gap: 8, paddingBottom: 8 }}>
             {[40, 65, 45, 85, 55, 75, 90, 60].map((h, i) => (
              <motion.div
                key={i}
                initial={{ height: 0 }}
                animate={{ height: [`${h}%`, `${h + (Math.random() * 20 - 10)}%`, `${h}%`] }}
                transition={{ duration: 3, repeat: Infinity, delay: i * 0.1, ease: 'easeInOut' }}
                style={{ flex: 1, background: i === 6 ? '#111' : '#F3F4F6', borderRadius: 4 }}
              />
            ))}
          </div>
        </div>
      </motion.div>

      {/* Floating Card 3: Risk Metric (Bottom Right, Supporting) */}
      <motion.div
        className="l2-3d-card"
        style={{ width: 260, height: 160, bottom: '15%', right: '15%', zIndex: 4 }}
        animate={{
          y: [0, -10, 0],
          rotateZ: [-1, 1, -1],
        }}
        transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
      >
        <div className="l2-visual-card-glass" style={{ justifyContent: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', boxShadow: '0 0 0 2px rgba(16, 185, 129, 0.2)' }}></div>
            <div style={{ fontSize: 11, color: '#999', fontWeight: 600, letterSpacing: '0.05em' }}>DATA ACCURACY</div>
          </div>
          <div style={{ fontSize: 42, fontWeight: 600, color: '#111', letterSpacing: '-0.03em', lineHeight: 1 }}>99.2%</div>
          <div style={{ fontSize: 13, color: '#666', marginTop: 8 }}>vs 68.4% in frontier LLMs</div>
        </div>
      </motion.div>
    </div>
  );
};

const Hero = () => {
  return (
    <section className="l2-hero">
      <div className="l2-hero-grid">
        <div className="l2-hero-content">

          <h1 className="l2-hero-title">
            Sentry Investment<br />
            <span>Intelligence</span>
          </h1>

          <p className="l2-hero-subtitle">
            Next generation investment intelligence developed by Binomial Technologies.
            We are your trusted analytical partner, delivering data-driven insights to optimize investment outcomes.
          </p>

          <div className="l2-hero-actions">
            <Link to="/contact" className="l2-btn-primary">
              Request Access <ArrowUpRight size={18} />
            </Link>
            <Link to="/about" className="l2-btn-secondary">
              Learn More
            </Link>
          </div>
        </div>
        <HeroVisual />
      </div>
    </section>
  );
};

const AboutSection = () => (
  <section id="about" className="l2-section" style={{ padding: '120px 40px' }}>
    <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '80px', alignItems: 'center' }}>
      <div>
        <span className="l2-section-eyebrow">About</span>
        <h2 className="l2-section-title" style={{ marginBottom: '32px' }}>Your Trusted<br/>Analytical Partner</h2>
        <div className="l2-text-block" style={{ fontSize: '1.125rem', lineHeight: '1.7', color: 'var(--l2-text-secondary)', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <p>
            Sentry Intelligence has been developed by Binomial Capital Management, providing institutional-grade investment intelligence across comprehensive market analytics. We are more than just a platform; we are your trusted analytical partner, delivering data-driven insights to optimize investment outcomes.
          </p>
          <p>
            We combine advanced AI capabilities with deep quantitative analysis and real-time market intelligence. Our platform leverages sophisticated algorithms and proven analytical frameworks used by institutional investors.
          </p>
        </div>
        <div style={{ marginTop: '40px' }}>
          <Link to="/contact" className="l2-btn-primary">
            Start Analyzing <ArrowUpRight size={18} />
          </Link>
        </div>
      </div>
      <div style={{ position: 'relative', height: '500px', background: '#EAE8E2', borderRadius: '24px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

        {/* Background Pattern */}
        <div style={{ position: 'absolute', inset: 0, opacity: 0.03 }} >
           <svg width="100%" height="100%">
             <defs>
               <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                 <path d="M 40 0 L 0 0 0 40" fill="none" stroke="black" strokeWidth="1"/>
               </pattern>
             </defs>
             <rect width="100%" height="100%" fill="url(#grid)" />
           </svg>
        </div>

        {/* Trading Terminal Candlestick Chart */}
        <div style={{ position: 'relative', width: 350, height: 300 }}>

          {/* Chart Container */}
          <div style={{
            background: 'linear-gradient(135deg, #111 0%, #1a1a1a 100%)',
            borderRadius: '16px',
            padding: '24px',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>

            {/* Chart Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <LineChart size={18} color="#10b981" strokeWidth={2} />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#e5e5e5' }}>PORTFOLIO</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600 }}>+12.4%</span>
              </div>
            </div>

            {/* Candlestick Chart */}
            <div style={{ position: 'relative', height: 180, display: 'flex', alignItems: 'flex-end', gap: 8, justifyContent: 'center' }}>

              {/* Grid lines */}
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={`grid-${i}`}
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    bottom: `${i * 25}%`,
                    height: 1,
                    background: 'rgba(255,255,255,0.03)',
                  }}
                />
              ))}

              {/* Candlesticks */}
              {[
                { h: 120, o: 40, c: 80, color: '#10b981' },
                { h: 140, o: 80, c: 100, color: '#10b981' },
                { h: 110, o: 100, c: 60, color: '#ef4444' },
                { h: 150, o: 60, c: 130, color: '#10b981' },
                { h: 160, o: 130, c: 90, color: '#ef4444' },
                { h: 130, o: 90, c: 110, color: '#10b981' },
                { h: 170, o: 110, c: 150, color: '#10b981' },
                { h: 165, o: 150, c: 145, color: '#ef4444' },
                { h: 155, o: 145, c: 140, color: '#ef4444' },
                { h: 180, o: 140, c: 170, color: '#10b981' },
              ].map((candle, i) => (
                <motion.div
                  key={i}
                  style={{ position: 'relative', flex: 1, maxWidth: 20 }}
                  initial={{ scaleY: 0, opacity: 0 }}
                  animate={{ scaleY: 1, opacity: 1 }}
                  transition={{ delay: i * 0.1, duration: 0.4 }}
                >
                  {/* Wick */}
                  <div style={{
                    position: 'absolute',
                    left: '50%',
                    bottom: 0,
                    width: 2,
                    height: candle.h,
                    background: `${candle.color}80`,
                    transform: 'translateX(-50%)',
                  }} />
                  {/* Body */}
                  <motion.div
                    style={{
                      position: 'absolute',
                      left: '50%',
                      bottom: Math.min(candle.o, candle.c),
                      width: '100%',
                      height: Math.abs(candle.c - candle.o),
                      background: candle.color,
                      transform: 'translateX(-50%)',
                      borderRadius: 2,
                      boxShadow: `0 0 12px ${candle.color}40`,
                    }}
                    whileHover={{ scale: 1.1 }}
                  />
                </motion.div>
              ))}
            </div>

            {/* Bottom Ticker Info */}
            <div style={{
              marginTop: 16,
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 10,
              color: '#888',
            }}>
              <span>VOL 2.4M</span>
              <span>52W: $142-$198</span>
              <span>MKT CAP $2.1T</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
);

const PerformanceSection = () => (
  <section id="performance" className="l2-section" style={{ padding: '120px 40px', background: '#fff', borderTop: '1px solid var(--l2-border)', borderBottom: '1px solid var(--l2-border)' }}>
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      <div className="l2-section-header" style={{ marginBottom: '80px' }}>
        <span className="l2-section-eyebrow">Performance</span>
        <h2 className="l2-section-title">Platform Metrics</h2>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px' }}>
        {[
          { label: 'Beta Users', value: '36', sub: 'Active institutional partners' },
          { label: 'Data Accuracy', value: '99.2%', sub: 'vs 68.4% in frontier LLMs' },
          { label: 'Time Savings', value: '~75%', sub: 'in financial workflows' },
          { label: 'Coverage', value: '600+', sub: 'companies analyzed daily' },
        ].map((kpi, i) => (
          <div key={i} style={{ padding: '32px', border: '1px solid var(--l2-border)', borderRadius: '16px', background: 'var(--l2-bg-primary)' }}>
            <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--l2-text-secondary)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{kpi.label}</div>
            <div style={{ fontSize: '3rem', fontWeight: 400, fontFamily: 'var(--l2-font-serif)', color: 'var(--l2-text-primary)', marginBottom: '8px', lineHeight: 1 }}>{kpi.value}</div>
            <div style={{ fontSize: '14px', color: 'var(--l2-text-secondary)', lineHeight: 1.5 }}>{kpi.sub}</div>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// --- Interactive Product Demo ---
const InteractiveProductDemo = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'tasks'>('chat');

  const TasksDemo = () => (
    <motion.iframe
      key="tasks"
      src="/tasks-demo"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      style={{ width: '100%', height: '100%', border: 'none' }}
      title="Tasks Demo"
    />
  );

  return (
    <section id="demo" className="l2-demo-section">
      <div className="l2-demo-bg"></div>
      <div className="l2-demo-container">
        <div style={{ marginBottom: 40, textAlign: 'center' }}>
          <span className="l2-section-eyebrow" style={{ margin: '0 auto 16px' }}>Platform Demo</span>
          <h2 className="l2-section-title" style={{ color: '#fff', fontSize: '3rem', marginBottom: 24 }}>
            Experience the Power<br />of Sentry.
          </h2>

          <p className="l2-section-subtitle" style={{ color: 'rgba(255,255,255,0.7)', maxWidth: '600px', margin: '0 auto 40px' }}>
             Explore two of our core systems below. The full platform provides comprehensive institutional-grade tools.
          </p>

          {/* Tab Switcher */}
          <div style={{
            display: 'inline-flex',
            background: 'rgba(255,255,255,0.1)',
            padding: 4,
            borderRadius: 100,
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
          }}>
            <button
              onClick={() => setActiveTab('chat')}
              style={{
                padding: '10px 24px',
                borderRadius: 100,
                background: activeTab === 'chat' ? '#fff' : 'transparent',
                color: activeTab === 'chat' ? '#111' : '#fff',
                border: 'none',
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              AI Analyst
            </button>
            <button
              onClick={() => setActiveTab('tasks')}
              style={{
                padding: '10px 24px',
                borderRadius: 100,
                background: activeTab === 'tasks' ? '#fff' : 'transparent',
                color: activeTab === 'tasks' ? '#111' : '#fff',
                border: 'none',
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              Task Automation
            </button>
          </div>
        </div>

        <div className="l2-demo-window" style={{ height: 800, border: '1px solid rgba(255,255,255,0.15)' }}>
          {/* Window Header */}
          <div className="l2-demo-header" style={{ background: '#1a1a1a', borderBottom: '1px solid #333', padding: '0 16px', height: '48px' }}>
            <div className="l2-demo-controls">
              <div className="l2-demo-dot" style={{ background: '#EF4444' }}></div>
              <div className="l2-demo-dot" style={{ background: '#F59E0B' }}></div>
              <div className="l2-demo-dot" style={{ background: '#10B981' }}></div>
            </div>

            <div className="l2-demo-title" style={{ color: '#888', position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>
              {activeTab === 'chat' ? 'Sentry Analyst - Investment Chat' : 'Sentry Tasks - Workflow Automation'}
            </div>

            {/* Module Indicators - Hinting at full capabilities */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, opacity: 0.4, fontSize: 12, color: '#fff' }} title="Full capabilities available in Enterprise">
                <Briefcase size={14} />
                <Network size={14} />
                <Activity size={14} />
                <Lock size={12} style={{ marginLeft: 2 }} />
              </div>
            </div>
          </div>

          {/* Content Container */}
          <div style={{ flex: 1, background: '#fff', position: 'relative', overflow: 'hidden' }}>
            <AnimatePresence mode="wait">
              {activeTab === 'chat' ? (
                <motion.iframe
                  key="chat"
                  src="/chat-demo"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  style={{ width: '100%', height: '100%', border: 'none' }}
                  title="Chat Demo"
                />
              ) : (
                <motion.div
                  key="tasks"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  style={{ width: '100%', height: '100%' }}
                >
                  <TasksDemo />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
};

// --- 3D & Interactive Capabilities ---

const VisualWrapper = ({ children }: { children: React.ReactNode }) => (
  <div style={{ width: '100%', height: '100%', padding: '24px', position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
    {children}
  </div>
);

// Enhanced Visuals

const PortfolioVisual = () => (
  <VisualWrapper>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="l2-stat-label">Current Sharpe</div>
          <div className="l2-stat-value">1.84</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="l2-stat-label">Optimized Sharpe</div>
          <div className="l2-stat-value text-green">2.45</div>
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative', border: '1px solid rgba(0,0,0,0.05)', borderRadius: 8, overflow: 'hidden', background: '#fcfcfc' }}>
        {/* Grid Lines */}
        <div className="l2-chart-grid" />

        {/* Efficient Frontier Curve */}
        <svg width="100%" height="100%" style={{ overflow: 'visible' }}>
          <motion.path
            d="M 20 180 Q 60 100 150 60 T 320 40"
            fill="none"
            stroke="#E5E7EB"
            strokeWidth="2"
            strokeDasharray="4 4"
          />
           <motion.path
            d="M 20 180 Q 60 100 150 60 T 320 40"
            fill="none"
            stroke="#10B981"
            strokeWidth="2"
            initial={{ pathLength: 0 }}
            whileInView={{ pathLength: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 2, ease: 'easeInOut' }}
          />

          {/* Current Portfolio Point */}
          <motion.circle cx="120" cy="90" r="6" fill="#94A3B8" initial={{ scale: 0 }} whileInView={{ scale: 1 }} transition={{ delay: 1 }} viewport={{ once: true }} />

          {/* Optimized Portfolio Point */}
          <motion.circle cx="220" cy="50" r="6" fill="#10B981" initial={{ scale: 0 }} whileInView={{ scale: [1, 1.5, 1] }} transition={{ delay: 1.5, repeat: Infinity, repeatDelay: 2 }} viewport={{ once: true }} />
        </svg>

        {/* Floating Asset Bubbles */}
        <motion.div
          className="l2-asset-bubble"
          style={{ top: '30%', left: '60%', background: '#EEF2FF', color: '#4F46E5' }}
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        >
          AAPL 24%
        </motion.div>
         <motion.div
          className="l2-asset-bubble"
          style={{ top: '60%', left: '20%', background: '#ECFDF5', color: '#059669' }}
          animate={{ y: [0, -15, 0] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
        >
          MSFT 18%
        </motion.div>
      </div>
    </div>
  </VisualWrapper>
);

const RiskVisual = () => (
  <VisualWrapper>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="l2-metric-box">
          <div className="l2-metric-label">VaR (95%)</div>
          <div className="l2-metric-value">-2.4%</div>
        </div>
        <div className="l2-metric-box">
          <div className="l2-metric-label">CVaR</div>
          <div className="l2-metric-value">-3.8%</div>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 4, paddingBottom: 10 }}>
        {[10, 15, 25, 40, 60, 85, 95, 70, 45, 30, 20, 15, 10, 5].map((h, i) => (
           <motion.div
            key={i}
            style={{
              flex: 1,
              background: i < 3 ? '#FECACA' : '#E5E7EB',
              borderRadius: '4px 4px 0 0',
              opacity: 0.8,
            }}
            initial={{ height: 0 }}
            whileInView={{ height: `${h}%` }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.05 }}
           />
        ))}
      </div>

      <div className="l2-alert-banner">
        <AlertTriangle size={14} />
        <span>Tail risk detected in Tech Sector</span>
      </div>
    </div>
  </VisualWrapper>
);

const MarketVisual = () => (
  <VisualWrapper>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {[
        { ticker: 'NVDA', signal: 'Bullish', score: 92, time: '2m ago' },
        { ticker: 'TSLA', signal: 'Neutral', score: 45, time: '5m ago' },
        { ticker: 'AMD', signal: 'Bearish', score: 28, time: '12m ago' },
      ].map((item, i) => (
        <motion.div
          key={i}
          className="l2-market-row"
          initial={{ x: 20, opacity: 0 }}
          whileInView={{ x: 0, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.2 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="l2-ticker-badge">{item.ticker}</div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span className="l2-signal-text">{item.signal}</span>
              <span className="l2-signal-time">{item.time}</span>
            </div>
          </div>
          <div className="l2-score-badge" style={{
            background: item.score > 80 ? '#ECFDF5' : item.score < 40 ? '#FEF2F2' : '#F3F4F6',
            color: item.score > 80 ? '#059669' : item.score < 40 ? '#DC2626' : '#4B5563',
          }}>
            {item.score}
          </div>
        </motion.div>
      ))}

      <div className="l2-processing-indicator">
        <div className="l2-spinner" />
        <span>Processing 14,000+ sources...</span>
      </div>
    </div>
  </VisualWrapper>
);

const ValuationVisual = () => (
  <VisualWrapper>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'center', gap: 20 }}>
      {/* Valuation Football Field */}
      <div className="l2-valuation-bar-group">
        <div className="l2-val-label">DCF (Growth)</div>
        <div className="l2-val-track">
          <motion.div
            className="l2-val-range"
            style={{ left: '40%', width: '30%', background: '#10B981' }}
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          />
          <div className="l2-val-marker" style={{ left: '55%' }} />
        </div>
        <div className="l2-val-price">$145.20</div>
      </div>

      <div className="l2-valuation-bar-group">
        <div className="l2-val-label">Comparables</div>
        <div className="l2-val-track">
           <motion.div
            className="l2-val-range"
            style={{ left: '35%', width: '25%', background: '#3B82F6' }}
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4 }}
          />
          <div className="l2-val-marker" style={{ left: '48%' }} />
        </div>
        <div className="l2-val-price">$138.50</div>
      </div>

      <div className="l2-valuation-bar-group">
        <div className="l2-val-label">Precedent Tx</div>
        <div className="l2-val-track">
           <motion.div
            className="l2-val-range"
            style={{ left: '45%', width: '40%', background: '#6366F1' }}
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.6 }}
          />
          <div className="l2-val-marker" style={{ left: '65%' }} />
        </div>
        <div className="l2-val-price">$152.00</div>
      </div>
    </div>
  </VisualWrapper>
);

const DocVisual = () => (
  <VisualWrapper>
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', gap: 12 }}>
      {[50, 80, 45, 70, 90, 60, 30, 75].map((h, i) => (
        <motion.div
          key={i}
          style={{
            width: 12,
            background: i % 2 === 0 ? '#10B981' : '#E5E7EB',
            borderRadius: 4,
          }}
          initial={{ height: 20 }}
          whileInView={{ height: h }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay: i * 0.1, ease: 'backOut' }}
        />
      ))}
    </div>
  </VisualWrapper>
);

const WorkflowVisual = () => (
  <VisualWrapper>
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%', gap: 16 }}>
      {['Call Option @ 150', 'Put Option @ 140'].map((label, i) => (
        <div key={i} style={{ background: '#F9FAFB', padding: '12px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>{label}</span>
          <span style={{ fontSize: '12px', color: '#10B981', fontWeight: 600 }}>+{i === 0 ? '12.4%' : '8.2%'}</span>
        </div>
      ))}
      <div style={{ height: 1, background: '#E5E7EB', width: '100%' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 4px' }}>
        <span style={{ fontSize: '12px', color: '#6B7280' }}>Delta Hedged</span>
        <span style={{ fontSize: '12px', color: '#10B981', fontWeight: 600 }}>98.5%</span>
      </div>
    </div>
  </VisualWrapper>
);

const capabilitiesData = [
  {
    title: 'Portfolio Optimization',
    desc: 'Constraint-aware optimization using proprietary factor models and advanced risk parity frameworks.',
    visual: <PortfolioVisual />,
  },
  {
    title: 'Risk Analytics',
    desc: 'Deep quantitative analysis including VaR, CVaR, and stress testing across multiple time horizons.',
    visual: <RiskVisual />,
  },
  {
    title: 'Valuations',
    desc: 'Institutional-grade DCF, Comparables, and Precedent Transactions with dynamic assumptions.',
    visual: <ValuationVisual />,
  },
  {
    title: 'Market Intelligence',
    desc: 'Real-time synthesis of global news, filings, and economic indicators extracted by AI agents.',
    visual: <MarketVisual />,
  },
  {
    title: 'Quantitative Modeling',
    desc: 'Advanced statistical models for correlation analysis, factor exposure, and regime detection.',
    visual: <DocVisual />,
  },
  {
    title: 'Options & Hedging',
    desc: 'Black-Scholes pricing, Greeks calculation, and automated hedge construction strategies.',
    visual: <WorkflowVisual />,
  },
];

const CapabilitiesGrid = () => {
  return (
    <section id="capabilities" className="l2-bento-section">
      <div className="l2-section-header center-text">
        <span className="l2-section-eyebrow">Capabilities</span>
        <h2 className="l2-section-title">Comprehensive<br />Market Analytics</h2>
      </div>

      <div className="l2-feature-grid">
        {capabilitiesData.map((cap, index) => (
          <motion.div
            key={index}
            className="l2-feature-card"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-5%' }}
            transition={{ duration: 0.4, delay: index * 0.1 }}
          >
             <div className="l2-feature-visual-container">
               {cap.visual}
             </div>
             <div className="l2-feature-content">
               <h3 className="l2-feature-title">{cap.title}</h3>
               <p className="l2-feature-desc">{cap.desc}</p>
              <Link to="/capabilities" className="l2-feature-link">
                Learn more <ArrowUpRight size={14} />
              </Link>
             </div>
          </motion.div>
        ))}
      </div>

      <div className="l2-section-footer">
        <Link to="/capabilities" className="l2-btn-secondary">
          Explore All Features
        </Link>
      </div>
    </section>
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

const Landing2 = () => {
  return (
    <div className="landing2-page">
      <Navbar />
      <Hero />
      <AboutSection />
      <PerformanceSection />
      <InteractiveProductDemo />
      <CapabilitiesGrid />
      <Footer />
    </div>
  );
};

export default Landing2;
