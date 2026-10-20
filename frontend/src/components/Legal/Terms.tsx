import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import './Legal.css';

const Terms: React.FC = () => {
  return (
    <div className="legal-page">
      <div className="legal-container">
        <Link to="/" className="legal-back">
          <ArrowLeft size={16} />
          Back to Home
        </Link>

        <h1>Terms of Service</h1>
        <p className="legal-updated">Last updated: January 12, 2026</p>

        <section>
          <h2>1. Acceptance of Terms</h2>
          <p>
            By accessing or using Sentry Intelligence ("Service"), you agree to be bound by these 
            Terms of Service. If you do not agree to these terms, please do not use the Service.
          </p>
        </section>

        <section>
          <h2>2. Description of Service</h2>
          <p>
            Sentry Intelligence provides AI-powered investment research and analytics tools. 
            The Service is designed to assist with financial analysis and should not be considered 
            as financial advice.
          </p>
        </section>

        <section>
          <h2>3. User Accounts</h2>
          <p>
            You are responsible for maintaining the confidentiality of your account credentials 
            and for all activities that occur under your account. You must notify us immediately 
            of any unauthorized use of your account.
          </p>
        </section>

        <section>
          <h2>4. Acceptable Use</h2>
          <p>You agree not to:</p>
          <ul>
            <li>Use the Service for any unlawful purpose</li>
            <li>Attempt to gain unauthorized access to any portion of the Service</li>
            <li>Interfere with or disrupt the integrity of the Service</li>
            <li>Transmit any malicious code or harmful content</li>
            <li>Resell or redistribute the Service without authorization</li>
          </ul>
        </section>

        <section>
          <h2>5. Intellectual Property</h2>
          <p>
            All content, features, and functionality of the Service are owned by Binomial Capital 
            Management and are protected by international copyright, trademark, and other 
            intellectual property laws.
          </p>
        </section>

        <section>
          <h2>6. Disclaimer of Warranties</h2>
          <p>
            THE SERVICE IS PROVIDED "AS IS" WITHOUT WARRANTIES OF ANY KIND. WE DO NOT GUARANTEE 
            THE ACCURACY, COMPLETENESS, OR USEFULNESS OF ANY INFORMATION PROVIDED. INVESTMENT 
            DECISIONS SHOULD NOT BE MADE SOLELY BASED ON INFORMATION FROM THIS SERVICE.
          </p>
        </section>

        <section>
          <h2>7. Limitation of Liability</h2>
          <p>
            IN NO EVENT SHALL SENTRY INTELLIGENCE OR BINOMIAL CAPITAL MANAGEMENT BE LIABLE FOR 
            ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING FROM 
            YOUR USE OF THE SERVICE.
          </p>
        </section>

        <section>
          <h2>8. Changes to Terms</h2>
          <p>
            We reserve the right to modify these terms at any time. We will notify users of 
            significant changes by posting a notice on our website or sending an email.
          </p>
        </section>

        <section>
          <h2>9. Contact</h2>
          <p>
            For questions about these Terms, please contact us at{' '}
            <a href="mailto:legal@binomialsentry.ai">legal@binomialsentry.ai</a>.
          </p>
        </section>
      </div>
    </div>
  );
};

export default Terms;

