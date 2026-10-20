import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Check, ArrowUpRight, Shield, Zap, Globe, Briefcase, Lock } from 'lucide-react';
import BinomialLogo from '../../assets/binomial-icon-logo.png';
import './Landing.css'; // Keep base styles
import './Pricing.css';   // Add pricing specific styles

import { useUser } from '@clerk/clerk-react';

// Reusing Navbar from Landing2 for consistency
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
        <Link to="/pricing" className="l2-nav-link" style={{ color: '#111' }}>Pricing</Link>
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

const PricingCard = ({
  plan,
  price,
  period = '/month',
  desc,
  features,
  ctaText = 'Get Started',
  ctaLink = '/register',
  featured = false,
  badge = null,
  priceDetail = null,
}: {
  plan: string;
  price: string;
  period?: string;
  desc: string;
  features: string[];
  ctaText?: string;
  ctaLink?: string;
  featured?: boolean;
  badge?: React.ReactNode;
  priceDetail?: string;
}) => (
  <motion.div
    className={`pricing-card ${featured ? 'featured' : ''}`}
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.4 }}
  >
    {badge && badge}
    <h3 className="pricing-plan-name">{plan}</h3>
    <div className="pricing-price-wrapper">
      <span className="pricing-currency">$</span>
      <span className="pricing-price">{price}</span>
      <span className="pricing-period">{period}</span>
    </div>
    {priceDetail && <div style={{ fontSize: '12px', color: featured ? '#aaa' : '#666', marginTop: '-12px', marginBottom: '16px' }}>{priceDetail}</div>}

    <p className="pricing-desc">{desc}</p>

    <div className="pricing-divider" />

    <div className="pricing-features">
      {features.map((feat, i) => (
        <div key={i} className="pricing-feature">
          <Check size={16} className="check-icon" />
          <span>{feat}</span>
        </div>
      ))}
    </div>

    <Link to={ctaLink} className={`pricing-btn ${featured ? '' : 'primary'}`}>
      {ctaText}
    </Link>
  </motion.div>
);

const CustomPricingCard = ({
  plan,
  badge = null,
  desc,
  features,
}: {
  plan: string;
  badge?: React.ReactNode;
  desc: string;
  features: string[];
}) => (
  <motion.div
    className="pricing-card"
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.4 }}
  >
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
      <h3 className="pricing-plan-name" style={{ margin: 0 }}>{plan}</h3>
      {badge && badge}
    </div>

    <div className="pricing-price-wrapper">
      <span className="pricing-price" style={{ fontSize: '2.5rem' }}>Contact Us</span>
    </div>

    <p className="pricing-desc">{desc}</p>

    <div className="pricing-divider" />

    <div className="pricing-features">
      {features.map((feat, i) => (
        <div key={i} className="pricing-feature">
          <Check size={16} className="check-icon" />
          <span>{feat}</span>
        </div>
      ))}
    </div>

    <Link to="/contact" className="pricing-btn primary">
      Contact Sales
    </Link>
  </motion.div>
);

const Pricing = () => {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');

  return (
    <div className="pricing-page">
      <Navbar />

      <div className="pricing-header">
        <span className="l2-hero-badge" style={{ marginBottom: '24px' }}>
          <span className="l2-hero-badge-dot"></span>
          <span className="l2-hero-badge-text">Plans & Pricing</span>
        </span>
        <h1 className="pricing-title">
          Investment Intelligence<br />
          <span style={{ color: 'var(--l2-text-secondary)', fontStyle: 'italic' }}>for every scale.</span>
        </h1>
        <p className="pricing-subtitle" style={{ marginBottom: '40px' }}>
          Choose the plan that fits your investment strategy. From individual analysts to institutional teams, Sentry scales with your needs.
        </p>

        {/* Billing Cycle Toggle */}
        <div className="billing-toggle-container">
          <button
            className={`billing-toggle-option ${billingCycle === 'monthly' ? 'active' : ''}`}
            onClick={() => setBillingCycle('monthly')}
          >
            Monthly
          </button>
          <div
            className="billing-toggle-switch"
            onClick={() => setBillingCycle(prev => prev === 'monthly' ? 'annual' : 'monthly')}
          >
            <motion.div
              className="billing-toggle-handle"
              layout
              transition={{ type: 'spring', stiffness: 700, damping: 30 }}
              style={{
                left: billingCycle === 'monthly' ? '4px' : 'calc(100% - 28px)',
              }}
            />
          </div>
          <button
            className={`billing-toggle-option ${billingCycle === 'annual' ? 'active' : ''}`}
            onClick={() => setBillingCycle('annual')}
          >
            Annual <span className="save-badge">Save 20%</span>
          </button>
        </div>
      </div>

      {/* Main 3 Plans */}
      <div className="pricing-grid">
        {/* Basic Plan */}
        <PricingCard
          plan="Basic"
          price={billingCycle === 'monthly' ? '99' : '79'}
          period="/month"
          desc="Essential tools for independent analysts and active traders starting their journey."
          priceDetail={billingCycle === 'annual' ? 'Billed $948 annually' : undefined}
          features={[
            'Access to Sentry Analyst (Basic)',
            'Standard Market Data (15 min delay)',
            '50 Queries / month',
            'Basic Portfolio Tracking (1 Portfolio)',
            'Daily Market Summary',
            'Standard Support',
            'Mobile Access',
          ]}
        />

        {/* Pro Plan - Middle */}
        <PricingCard
          plan="Pro"
          price={billingCycle === 'monthly' ? '279' : '229'}
          period="/month"
          desc="Advanced analytics, real-time data, and comprehensive tools for professional investors."
          priceDetail={billingCycle === 'annual' ? 'Billed $2,748 annually' : undefined}
          features={[
            'Everything in Basic',
            'Real-time Market Data Streaming',
            'Unlimited AI Analyst Queries',
            'Advanced Risk Metrics (VaR, CVaR)',
            'Monte Carlo Simulations',
            'Unlimited Portfolios & Watchlists',
            'Export Reports to PDF/CSV',
            'Priority Support (24h response)',
            'Advanced Charting Suite',
            'Scenario Analysis Tools',
          ]}
          featured={true}
        />

        {/* Organization Plan */}
        <PricingCard
          plan="Organization"
          price={billingCycle === 'monthly' ? '179' : '149'}
          period="/seat/mo"
          priceDetail={`Min 3 seats ($${billingCycle === 'monthly' ? '537' : '447'}/mo total)`}
          desc="Collaborative intelligence platform designed for investment teams and small firms."
          features={[
            'All Pro Benefits included',
            'Shared Team Portfolios & Views',
            'Team Chat & Collaboration Spaces',
            'Role-based Access Control (RBAC)',
            'Centralized Billing & Admin',
            'Dedicated Success Manager',
            'Team Usage Analytics',
            'Custom Portfolio Templates',
            'API Access (Read-only)',
          ]}
        />
      </div>

      {/* Specialized Plans */}
      <div className="pricing-grid-bottom">
        {/* Investor Plan */}
        <CustomPricingCard
          plan="Investor"
          badge={<div className="accredited-badge">Accredited Only</div>}
          desc="Invest with Binomial Capital Management and receive complimentary software licenses for life."
          features={[
            'Free Software License (All Features)',
            "Investment in Binomial's Strategies",
            'Co-investment Opportunities',
            'Direct Portfolio Exposure',
            'Quarterly Performance Reports',
            'Priority Access to New Funds',
            'Dedicated Account Management',
            'Requires Accreditation Verification',
          ]}
        />

        {/* Enterprise Plan */}
        <CustomPricingCard
          plan="Enterprise"
          desc="Custom single-tenant deployment with full control over data sources and framework customization for your specific needs."
          features={[
            'Single-Tenant Dedicated Instance',
            'Connect Your Own Data Sources',
            'Fully Customizable Framework',
            'On-premise / Private Cloud Deployment',
            'Custom AI Agent Configuration',
            'White-label Platform & Branding',
            'SLA & 24/7 Dedicated Support',
            'Custom Integrations & Workflows',
          ]}
        />
      </div>

      <Footer />
    </div>
  );
};

export default Pricing;
