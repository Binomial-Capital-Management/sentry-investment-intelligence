import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowUpRight, CheckCircle, AlertCircle } from 'lucide-react';
import BinomialLogo from '../../assets/binomial-icon-logo.png';
import api from '../../services/api';
import '../Landing/Landing.css'; // Use Landing2 styles

// Import logos used in Contact.tsx
import EmailIconPng from '../../assets/connector-logos/email-icon.png';
import LinkedInLogoPng from '../../assets/misc-logos/linkedin-logo.png';
import BinomialLogoPng from '../../assets/misc-logos/binomial-logo.png';

import { useUser } from '@clerk/clerk-react';

// Reusing Navbar from Landing2/Pricing
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
        <Link to="/contact" className="l2-nav-link" style={{ color: '#111' }}>Contact</Link>
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

const ContactForm = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    title: '',
    message: '',
  });

  const [submitState, setSubmitState] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitState('submitting');
    setErrorMessage('');

    try {
      await api.post('/api/contact', formData);
      setSubmitState('success');
      setFormData({
        name: '',
        email: '',
        company: '',
        title: '',
        message: '',
      });
    } catch (error: any) {
      setSubmitState('error');
      setErrorMessage(error.message || 'Failed to send message. Please try again.');
      console.error('Contact form submission error:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#666', marginBottom: 8 }}>Full Name *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleInputChange}
            required
            style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 14, outline: 'none', transition: 'border-color 0.2s' }}
            placeholder="John Doe"
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#666', marginBottom: 8 }}>Email Address *</label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleInputChange}
            required
            style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 14, outline: 'none', transition: 'border-color 0.2s' }}
            placeholder="john@company.com"
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#666', marginBottom: 8 }}>Company *</label>
          <input
            type="text"
            name="company"
            value={formData.company}
            onChange={handleInputChange}
            required
            style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 14, outline: 'none', transition: 'border-color 0.2s' }}
            placeholder="ABC Inc."
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#666', marginBottom: 8 }}>Title / Role</label>
          <input
            type="text"
            name="title"
            value={formData.title}
            onChange={handleInputChange}
            style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 14, outline: 'none', transition: 'border-color 0.2s' }}
            placeholder="Portfolio Manager"
          />
        </div>
      </div>

      <div>
        <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#666', marginBottom: 8 }}>Message / Requirements</label>
        <textarea
          name="message"
          value={formData.message}
          onChange={handleInputChange}
          rows={5}
          style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 14, outline: 'none', transition: 'border-color 0.2s', resize: 'vertical', fontFamily: 'inherit' }}
          placeholder="Tell us about your investment analysis needs..."
        />
      </div>

      {submitState === 'success' && (
        <div style={{ padding: 16, background: '#ECFDF5', color: '#065F46', borderRadius: 8, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
          <CheckCircle size={18} />
          Message sent successfully. We'll be in touch shortly.
        </div>
      )}

      {submitState === 'error' && (
        <div style={{ padding: 16, background: '#FEF2F2', color: '#991B1B', borderRadius: 8, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          {errorMessage}
        </div>
      )}

      <button
        type="submit"
        disabled={submitState === 'submitting'}
        className="l2-btn-primary"
        style={{ justifyContent: 'center', marginTop: 16 }}
      >
        {submitState === 'submitting' ? 'Sending...' : 'Request Demo'}
      </button>
    </form>
  );
};

// X Logo Component (SVG)
const XLogo = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="#000000"/>
  </svg>
);

const Contact2 = () => {
  return (
    <div className="landing2-page">
      <Navbar />

      <div style={{ paddingTop: 160, paddingBottom: 80, maxWidth: 1400, margin: '0 auto', paddingLeft: 40, paddingRight: 40 }}>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 80 }}>

          {/* Left Column: Info */}
          <div>
            <span className="l2-hero-badge" style={{ marginBottom: '24px' }}>
              <span className="l2-hero-badge-dot"></span>
              <span className="l2-hero-badge-text">Get in Touch</span>
            </span>

            <h1 className="l2-hero-title" style={{ fontSize: '4rem', marginBottom: 32 }}>
              Start Your<br />Analysis.
            </h1>

            <p className="l2-hero-subtitle" style={{ marginBottom: 60 }}>
              Ready to elevate your investment process? Schedule a personalized demo of Sentry Intelligence.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
              {/* Email */}
              <a href="mailto:hello@bcmassets.com" style={{ display: 'flex', alignItems: 'center', gap: 16, textDecoration: 'none', color: 'inherit', padding: 20, borderRadius: 12, border: '1px solid #E5E7EB', background: '#fff', transition: 'all 0.2s' }}>
                <div style={{ width: 40, height: 40, background: '#F3F4F6', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                  <img src={EmailIconPng} alt="Email" style={{ width: 24, height: 24, objectFit: 'contain' }} />
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Email Us</div>
                  <div style={{ fontSize: 16, fontWeight: 500 }}>hello@bcmassets.com</div>
                </div>
                <ArrowUpRight size={18} style={{ marginLeft: 'auto', color: '#999' }} />
              </a>

              {/* Corporate Site */}
              <a href="https://www.bcmassets.com" target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: 16, textDecoration: 'none', color: 'inherit', padding: 20, borderRadius: 12, border: '1px solid #E5E7EB', background: '#fff', transition: 'all 0.2s' }}>
                <div style={{ width: 40, height: 40, background: '#F3F4F6', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                  <img src={BinomialLogoPng} alt="Binomial" style={{ width: 24, height: 24, objectFit: 'contain' }} />
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Corporate Site</div>
                  <div style={{ fontSize: 16, fontWeight: 500 }}>www.bcmassets.com</div>
                </div>
                <ArrowUpRight size={18} style={{ marginLeft: 'auto', color: '#999' }} />
              </a>

              {/* LinkedIn */}
              <a href="https://www.linkedin.com/company/binomialtec" target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: 16, textDecoration: 'none', color: 'inherit', padding: 20, borderRadius: 12, border: '1px solid #E5E7EB', background: '#fff', transition: 'all 0.2s' }}>
                <div style={{ width: 40, height: 40, background: '#F3F4F6', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                   <img src={LinkedInLogoPng} alt="LinkedIn" style={{ width: 24, height: 24, objectFit: 'contain' }} />
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Follow Us</div>
                  <div style={{ fontSize: 16, fontWeight: 500 }}>@binomialtec</div>
                </div>
                <ArrowUpRight size={18} style={{ marginLeft: 'auto', color: '#999' }} />
              </a>

              {/* X / Twitter */}
              <a href="https://x.com/BinomialTech" target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: 16, textDecoration: 'none', color: 'inherit', padding: 20, borderRadius: 12, border: '1px solid #E5E7EB', background: '#fff', transition: 'all 0.2s' }}>
                <div style={{ width: 40, height: 40, background: '#F3F4F6', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                   <XLogo />
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>X / Twitter</div>
                  <div style={{ fontSize: 16, fontWeight: 500 }}>@BinomialTech</div>
                </div>
                <ArrowUpRight size={18} style={{ marginLeft: 'auto', color: '#999' }} />
              </a>
            </div>
          </div>

          {/* Right Column: Form */}
          <div style={{
            background: '#fff',
            borderRadius: 24,
            padding: 48,
            border: '1px solid rgba(0,0,0,0.06)',
            boxShadow: '0 20px 40px -10px rgba(0,0,0,0.05)',
          }}>
            <h3 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: '2rem', marginBottom: 8 }}>Request Access</h3>
            <p style={{ color: '#666', marginBottom: 32 }}>Fill out the form below and our team will get back to you within 24 hours.</p>

            <ContactForm />
          </div>

        </div>
      </div>

      <Footer />
    </div>
  );
};

export default Contact2;
