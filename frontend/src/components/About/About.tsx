import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import BinomialLogo from '../../assets/binomial-icon-logo.png';
import GreenParkImage from '../../assets/green-park.jpg';
import '../Landing/Landing.css'; // Use Landing2 styles

import { useUser } from '@clerk/clerk-react';

// Reuse Navbar from Landing2/Pricing
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
        <Link to="/about" className="l2-nav-link" style={{ color: '#111' }}>About</Link>
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

// Refined "Glass Monolith" Visual
const AboutVisual = () => (
  <div className="l2-hero-visual" style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 0.2 }}
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: 550,
        height: 'auto',
        zIndex: 1,
      }}
    >
       {/* Background Ambient Glow */}
       <div style={{
         position: 'absolute',
         top: '50%',
         left: '50%',
         transform: 'translate(-50%, -50%)',
         width: '120%',
         height: '120%',
         background: 'radial-gradient(circle at 50% 50%, rgba(235, 94, 40, 0.08), transparent 60%)',
         filter: 'blur(60px)',
         zIndex: -1,
       }} />

       {/* Main Glass Card */}
       <div style={{
         background: 'rgba(255, 255, 255, 0.7)',
         backdropFilter: 'blur(24px)',
         border: '1px solid rgba(255, 255, 255, 0.8)',
         borderRadius: 32,
         boxShadow: '0 20px 60px -10px rgba(0,0,0,0.08), 0 0 0 1px rgba(255,255,255,0.5) inset',
         padding: '48px',
       }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 48 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#888', marginBottom: 8 }}>Platform Version 6.2</div>
              <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 28, color: '#111' }}>Sentry Intelligence</div>
            </div>
            <img src={BinomialLogo} alt="Logo" style={{ height: 40, opacity: 1 }} />
          </div>

          {/* Grid of Stats - Clean Typography */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px 24px' }}>
            <div style={{ position: 'relative' }}>
               <div style={{ fontSize: '1.125rem', color: '#666', marginBottom: 4 }}>Model Accuracy</div>
               <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, color: '#111' }}>99.2%</div>
            </div>
            <div style={{ position: 'relative' }}>
               <div style={{ fontSize: '1.125rem', color: '#666', marginBottom: 4 }}>Strategy Return*</div>
               <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, color: '#EB5E28' }}>58.9%</div>
            </div>
            <div style={{ position: 'relative' }}>
               <div style={{ fontSize: '1.125rem', color: '#666', marginBottom: 4 }}>Strategy Sharpe*</div>
               <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, color: '#111' }}>3.21</div>
            </div>
             <div style={{ position: 'relative' }}>
               <div style={{ fontSize: '1.125rem', color: '#666', marginBottom: 4 }}>Daily Coverage</div>
               <div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3.5rem', lineHeight: 1, color: '#111' }}>600+</div>
            </div>
          </div>

          {/* Footer Note */}
          <div style={{ marginTop: 48, paddingTop: 24, borderTop: '1px solid rgba(0,0,0,0.06)', fontSize: 13, color: '#888', lineHeight: 1.5 }}>
            * Financial metrics represent internal strategies managed by BCM Assets utilizing the Sentry platform. Sentry is an analytical tool and does not autonomously execute trades.
          </div>
       </div>
    </motion.div>
  </div>
);

const About2 = () => {
  return (
    <div className="landing2-page">
      <Navbar />

      {/* Hero */}
      <section className="l2-hero" style={{ minHeight: '90vh', paddingBottom: 0 }}>
        <div className="l2-hero-grid" style={{ gridTemplateColumns: '1fr 1.1fr' }}>
          <div className="l2-hero-content">
            <span className="l2-hero-badge" style={{ marginBottom: '24px' }}>
              <span className="l2-hero-badge-dot"></span>
              <span className="l2-hero-badge-text">Our Story</span>
            </span>

            <h1 className="l2-hero-title">
              Autonomous Intelligence<br />
              <span>For Capital Markets.</span>
            </h1>

            <p className="l2-hero-subtitle">
              Sentry Intelligence is the world's first agentic research platform built for institutional depth.
              We combine rigorous financial modeling with autonomous AI agents to accelerate high-conviction decision making.
            </p>
          </div>
          <AboutVisual />
        </div>
      </section>

      {/* Mission Section - Clean & Editorial */}
      <section style={{ position: 'relative', padding: '140px 0', background: '#111', color: '#fff' }}>
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to bottom right, #1a1a1a, #050505)' }} />

        <div style={{ position: 'relative', maxWidth: '1200px', margin: '0 auto', padding: '0 40px', zIndex: 2 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80 }}>
            <div>
              <span className="l2-section-eyebrow" style={{ color: '#fff', opacity: 0.6, borderColor: 'rgba(255,255,255,0.2)' }}>Our Mission</span>
              <h2 className="l2-section-title" style={{ color: '#fff', fontSize: '3rem' }}>
                Institutional Intelligence<br />For The Modern Investor
              </h2>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingTop: 20 }}>
               <p style={{ fontSize: '1.25rem', lineHeight: 1.6, color: 'rgba(255,255,255,0.9)' }}>
                Sentry Intelligence transforms how investment teams interact with data. We believe the future of finance belongs to those who can synthesize vast information streams into actionable signals instantly.
              </p>
              <p style={{ fontSize: '1.1rem', lineHeight: 1.6, color: 'rgba(255,255,255,0.5)' }}>
                From factor analysis to option pricing, we provide the tools that top-tier hedge funds use—now automated and available to all professional investors seeking to generate alpha.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* DNA Section - Text Only, No Icons */}
      <section className="l2-section" style={{ padding: '140px 40px' }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          <div style={{ marginBottom: 100, borderBottom: '1px solid rgba(0,0,0,0.06)', paddingBottom: 40 }}>
             <h2 className="l2-section-title" style={{ fontSize: '4rem', margin: 0 }}>Our DNA</h2>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 60 }}>
            {[
              {
                label: '01',
                title: 'Agentic Architecture',
                desc: 'Sentry is built on a multi-agent framework where specialized AI workers handle distinct tasks—from SEC filing analysis to quantitative modeling—collaborating to solve complex problems.',
              },
              {
                label: '02',
                title: 'Quantitative Rigor',
                desc: "We don't just summarize text. Sentry executes Python-based financial models in real-time, delivering hard numbers, valuation matrices, and risk metrics you can trust.",
              },
              {
                label: '03',
                title: 'Institutional Logic',
                desc: 'Developed originally to manage millions in AUM, our tools are battle-tested. Sentry achieves 99.2% data accuracy vs 68.4% in frontier models.',
              },
            ].map((item, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#EB5E28', marginBottom: 24, fontFamily: 'var(--l2-font-mono)' }}>{item.label}</div>
                <h3 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2rem', marginBottom: 16, color: '#111' }}>{item.title}</h3>
                <p style={{ fontSize: '1.05rem', lineHeight: 1.7, color: '#666' }}>{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Image Break */}
      <section style={{ height: '600px', overflow: 'hidden' }}>
         <img src={GreenParkImage} alt="Office" style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center' }} />
      </section>

      {/* Origin Story */}
      <section className="l2-section" style={{ padding: '120px 40px', background: '#F5F4EF' }}>
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>
          <span className="l2-section-eyebrow" style={{ marginBottom: 24 }}>The Origin Story</span>
          <h3 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '3rem', lineHeight: 1.1, marginBottom: 40, color: '#111' }}>
            "We built Sentry because needed it. Institutional workflows were stuck in legacy terminals; we liberated them with AI."
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40 }}>
             <div style={{ fontSize: '1.1rem', lineHeight: 1.7, color: '#444' }}>
               <p style={{ marginBottom: 24 }}>
                The platform began as a solution to a critical inefficiency: analyst fatigue. Processing thousands of filings and market signals daily is impossible for humans alone.
               </p>
               <p>
                 By deploying autonomous agents to handle the cognitive load, we unlocked a new tier of alpha generation. The result is a system that doesn't just aggregate data, but reasons about it.
               </p>
             </div>
             <div style={{ fontSize: '1.1rem', lineHeight: 1.7, color: '#444' }}>
               <p style={{ marginBottom: 24 }}>
                 We realized that the future of investment technology wasn't just better charts—it was active intelligence. Sentry is the realization of that vision.
               </p>
                <div style={{ marginTop: 24, padding: '20px', borderLeft: '2px solid #EB5E28', background: 'rgba(235, 94, 40, 0.05)' }}>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: '#666', fontStyle: 'italic' }}>
                    * Currently under peer review benchmarking against frontier LLMs. Expected results Oct 2025.
                  </p>
                </div>
             </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About2;
