import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import './Legal.css';

const Privacy: React.FC = () => {
  return (
    <div className="legal-page">
      <div className="legal-container">
        <Link to="/" className="legal-back">
          <ArrowLeft size={16} />
          Back to Home
        </Link>

        <h1>Privacy Policy</h1>
        <p className="legal-updated">Last updated: January 12, 2026</p>

        <section>
          <h2>1. Information We Collect</h2>
          <p>
            Sentry Intelligence ("we", "our", or "us") collects information you provide directly, 
            including your name, email address, and account credentials when you register for our service. 
            We also collect usage data such as interaction logs and preferences to improve your experience.
          </p>
        </section>

        <section>
          <h2>2. How We Use Your Information</h2>
          <p>We use the information we collect to:</p>
          <ul>
            <li>Provide, maintain, and improve our services</li>
            <li>Process transactions and send related information</li>
            <li>Send technical notices, updates, and support messages</li>
            <li>Respond to your comments, questions, and customer service requests</li>
            <li>Monitor and analyze trends, usage, and activities</li>
          </ul>
        </section>

        <section>
          <h2>3. Data Security</h2>
          <p>
            We implement appropriate technical and organizational measures to protect your personal 
            information against unauthorized access, alteration, disclosure, or destruction. However, 
            no method of transmission over the Internet is 100% secure.
          </p>
        </section>

        <section>
          <h2>4. Third-Party Services</h2>
          <p>
            Our service integrates with third-party services such as Google Drive for file access. 
            When you connect these services, their respective privacy policies apply to data 
            they collect. We only access the specific files you explicitly select.
          </p>
        </section>

        <section>
          <h2>5. Data Retention</h2>
          <p>
            We retain your information for as long as your account is active or as needed to 
            provide services. You may request deletion of your data at any time by contacting us.
          </p>
        </section>

        <section>
          <h2>6. Your Rights</h2>
          <p>You have the right to:</p>
          <ul>
            <li>Access and receive a copy of your personal data</li>
            <li>Rectify inaccurate personal data</li>
            <li>Request deletion of your personal data</li>
            <li>Object to or restrict processing of your personal data</li>
          </ul>
        </section>

        <section>
          <h2>7. Contact Us</h2>
          <p>
            If you have questions about this Privacy Policy, please contact us at{' '}
            <a href="mailto:privacy@binomialsentry.ai">privacy@binomialsentry.ai</a>.
          </p>
        </section>
      </div>
    </div>
  );
};

export default Privacy;

