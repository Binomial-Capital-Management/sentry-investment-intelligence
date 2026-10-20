import { useState, FormEvent, useEffect } from 'react';
import axios from 'axios';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { API_BASE } from '@/services/api';

// Dropdown constants
const INDUSTRIES = [
  'Finance', 'Technology', 'Healthcare', 'Legal', 'Consulting',
  'Manufacturing', 'Real Estate', 'Energy', 'Retail', 'Education', 'Other',
];

const COMPANY_SIZES = [
  '1-10 employees',
  '11-50 employees',
  '51-200 employees',
  '201-1000 employees',
  '1000+ employees',
];

const REGIONS = [
  'North America',
  'Europe',
  'Asia Pacific',
  'Latin America',
  'Middle East',
  'Africa',
];

interface OrganizationMetadata {
  organizationName: string;
  slug: string;
  industry?: string;
  companySize?: string;
  region?: string;
  website?: string;
  description?: string;
  billingContactName?: string;
  billingContactEmail?: string;
  phone?: string;
  taxId?: string;
  address?: {
    street?: string;
    city?: string;
    state?: string;
    zip?: string;
    country?: string;
  };
  timezone?: string;
  logo?: string;
}

interface OrganizationDetailsFormProps {
  onComplete: (orgData: OrganizationMetadata) => void;
  onBack: () => void;
}

const OrganizationDetailsForm = ({ onComplete, onBack }: OrganizationDetailsFormProps) => {
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 4;

  // Step 1: Basic Info
  const [organizationName, setOrganizationName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugAvailable, setSlugAvailable] = useState<boolean | null>(null);
  const [checkingSlug, setCheckingSlug] = useState(false);

  // Step 2: Company Details
  const [industry, setIndustry] = useState('');
  const [companySize, setCompanySize] = useState('');
  const [region, setRegion] = useState('');
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');

  // Step 3: Contact & Legal
  const [billingContactName, setBillingContactName] = useState('');
  const [billingContactEmail, setBillingContactEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [taxId, setTaxId] = useState('');
  const [showAddress, setShowAddress] = useState(false);
  const [address, setAddress] = useState({
    street: '',
    city: '',
    state: '',
    zip: '',
    country: '',
  });
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);

  // Step 4: Branding
  const [logo, setLogo] = useState('');

  const [touched, setTouched] = useState({
    organizationName: false,
    slug: false,
    region: false,
    companySize: false,
    addressStreet: false,
    addressCity: false,
    addressCountry: false,
  });
  const [errors, setErrors] = useState({
    organizationName: '',
    slug: '',
    region: '',
    companySize: '',
    addressStreet: '',
    addressCity: '',
    addressCountry: '',
    general: '',
  });
  const [loading, setLoading] = useState(false);

  // Auto-generate slug from organization name
  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  };

  // Handle organization name change
  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setOrganizationName(value);

    if (!touched.slug) {
      const newSlug = generateSlug(value);
      setSlug(newSlug);
      setSlugAvailable(null);
    }

    if (touched.organizationName) {
      setErrors(prev => ({ ...prev, organizationName: value ? '' : 'Organization name is required' }));
    }
  };

  // Handle slug change
  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(value);
    setSlugAvailable(null);
    setTouched(prev => ({ ...prev, slug: true }));

    if (touched.slug) {
      setErrors(prev => ({
        ...prev,
        slug: value.length < 3 ? 'Slug must be at least 3 characters' : '',
      }));
    }
  };

  // Check slug availability with debounce
  useEffect(() => {
    if (slug.length < 3) {
      setSlugAvailable(null);
      return;
    }

    setCheckingSlug(true);
    const timer = setTimeout(async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/organizations/check-slug/${slug}`);
        setSlugAvailable(res.data.available);
        if (!res.data.available) {
          setErrors(prev => ({ ...prev, slug: res.data.message || 'This slug is already taken' }));
        } else {
          setErrors(prev => ({ ...prev, slug: '' }));
        }
      } catch (error) {
        console.error('Error checking slug:', error);
        setSlugAvailable(null);
      } finally {
        setCheckingSlug(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [slug]);

  // Validate current step
  const validateCurrentStep = (): boolean => {
    if (currentStep === 1) {
      const nameError = organizationName ? '' : 'Organization name is required';
      const slugError = slug.length < 3 ? 'Slug must be at least 3 characters' : '';
      setErrors(prev => ({ ...prev, organizationName: nameError, slug: slugError }));
      setTouched(prev => ({ ...prev, organizationName: true, slug: true }));
      return !nameError && !slugError && slugAvailable === true;
    }

    if (currentStep === 2) {
      const regionError = region ? '' : 'Region is required';
      const companySizeError = companySize ? '' : 'Company size is required';
      setErrors(prev => ({ ...prev, region: regionError, companySize: companySizeError }));
      setTouched(prev => ({ ...prev, region: true, companySize: true }));
      return !regionError && !companySizeError;
    }

    if (currentStep === 3) {
      const streetError = address.street ? '' : 'Street address is required';
      const cityError = address.city ? '' : 'City is required';
      const countryError = address.country ? '' : 'Country is required';
      setErrors(prev => ({
        ...prev,
        addressStreet: streetError,
        addressCity: cityError,
        addressCountry: countryError,
      }));
      setTouched(prev => ({
        ...prev,
        addressStreet: true,
        addressCity: true,
        addressCountry: true,
      }));
      return !streetError && !cityError && !countryError;
    }

    return true; // Step 4 is optional
  };

  // Handle next step
  const handleNext = () => {
    if (!validateCurrentStep()) {
      return;
    }
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    } else {
      handleSubmit();
    }
  };

  // Handle previous step
  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Handle form submission
  const handleSubmit = () => {
    setLoading(true);

    try {
      const orgData: OrganizationMetadata = {
        organizationName,
        slug,
        ...(industry && { industry }),
        ...(companySize && { companySize }),
        ...(region && { region }),
        ...(website && { website }),
        ...(description && { description }),
        ...(billingContactName && { billingContactName }),
        ...(billingContactEmail && { billingContactEmail }),
        ...(phone && { phone }),
        ...(taxId && { taxId }),
        ...(showAddress && Object.values(address).some(v => v) && { address }),
        ...(timezone && { timezone }),
        ...(logo && { logo }),
      };

      onComplete(orgData);
    } catch (error) {
      console.error('Error:', error);
      setErrors(prev => ({ ...prev, general: 'An error occurred. Please try again.' }));
      setLoading(false);
    }
  };

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Basic Information</h2>

            {/* Organization Name */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Organization name *
              </label>
              <input
                type="text"
                value={organizationName}
                onChange={handleNameChange}
                onBlur={() => setTouched(prev => ({ ...prev, organizationName: true }))}
                className="input"
                placeholder="Acme Corp"
                style={{
                  borderRadius: 10,
                  width: '100%',
                  borderColor: errors.organizationName && touched.organizationName ? '#EF4444' : undefined,
                }}
                disabled={loading}
              />
              {errors.organizationName && touched.organizationName && (
                <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                  {errors.organizationName}
                </p>
              )}
            </div>

            {/* Slug */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Organization URL *
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>binomialsentry.ai/</span>
                <input
                  type="text"
                  value={slug}
                  onChange={handleSlugChange}
                  className="input"
                  placeholder="acme-corp"
                  style={{
                    borderRadius: 10,
                    flex: 1,
                    borderColor: (errors.slug && touched.slug) || slugAvailable === false ? '#EF4444' :
                                 slugAvailable === true ? '#10B981' : undefined,
                  }}
                  disabled={loading}
                />
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                {checkingSlug && <span>Checking availability...</span>}
                {!checkingSlug && slugAvailable === true && (
                  <span style={{ color: '#10B981' }}>✓ Available</span>
                )}
                {!checkingSlug && slugAvailable === false && errors.slug && (
                  <span style={{ color: '#EF4444' }}>{errors.slug}</span>
                )}
              </div>
            </div>
          </>
        );

      case 2:
        return (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Company Details</h2>

            {/* Industry */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Industry <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="input"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              >
                <option value="">Select industry...</option>
                {INDUSTRIES.map(ind => (
                  <option key={ind} value={ind}>{ind}</option>
                ))}
              </select>
            </div>

            {/* Company Size */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Company size *
              </label>
              <select
                value={companySize}
                onChange={(e) => setCompanySize(e.target.value)}
                className="input"
                style={{
                  borderRadius: 10,
                  width: '100%',
                  borderColor: errors.companySize && touched.companySize ? '#EF4444' : undefined,
                }}
                disabled={loading}
              >
                <option value="">Select size...</option>
                {COMPANY_SIZES.map(size => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
              {errors.companySize && touched.companySize && (
                <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                  {errors.companySize}
                </p>
              )}
            </div>

            {/* Region */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Region *
              </label>
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="input"
                style={{
                  borderRadius: 10,
                  width: '100%',
                  borderColor: errors.region && touched.region ? '#EF4444' : undefined,
                }}
                disabled={loading}
              >
                <option value="">Select region...</option>
                {REGIONS.map(reg => (
                  <option key={reg} value={reg}>{reg}</option>
                ))}
              </select>
              {errors.region && touched.region && (
                <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                  {errors.region}
                </p>
              )}
            </div>

            {/* Website */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Website <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                className="input"
                placeholder="https://example.com"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              />
            </div>

            {/* Description */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Description <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="input"
                placeholder="Tell us about your organization..."
                rows={3}
                style={{ borderRadius: 10, width: '100%', resize: 'vertical' }}
                disabled={loading}
              />
            </div>
          </>
        );

      case 3:
        return (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Contact & Legal</h2>

            {/* Address Fields - Required */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Street address *
              </label>
              <input
                type="text"
                value={address.street}
                onChange={(e) => setAddress({ ...address, street: e.target.value })}
                className="input"
                placeholder="123 Main St"
                style={{
                  borderRadius: 10,
                  width: '100%',
                  borderColor: errors.addressStreet && touched.addressStreet ? '#EF4444' : undefined,
                }}
                disabled={loading}
              />
              {errors.addressStreet && touched.addressStreet && (
                <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                  {errors.addressStreet}
                </p>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 8, marginBottom: 12 }}>
              <div>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  marginBottom: 6,
                  color: 'var(--text-secondary)',
                  fontWeight: 500,
                }}>
                  City *
                </label>
                <input
                  type="text"
                  value={address.city}
                  onChange={(e) => setAddress({ ...address, city: e.target.value })}
                  className="input"
                  placeholder="New York"
                  style={{
                    borderRadius: 10,
                    borderColor: errors.addressCity && touched.addressCity ? '#EF4444' : undefined,
                  }}
                  disabled={loading}
                />
                {errors.addressCity && touched.addressCity && (
                  <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                    {errors.addressCity}
                  </p>
                )}
              </div>
              <div>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  marginBottom: 6,
                  color: 'var(--text-secondary)',
                  fontWeight: 500,
                }}>
                  State <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
                </label>
                <input
                  type="text"
                  value={address.state}
                  onChange={(e) => setAddress({ ...address, state: e.target.value })}
                  className="input"
                  placeholder="NY"
                  style={{ borderRadius: 10 }}
                  disabled={loading}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
              <div>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  marginBottom: 6,
                  color: 'var(--text-secondary)',
                  fontWeight: 500,
                }}>
                  ZIP code <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
                </label>
                <input
                  type="text"
                  value={address.zip}
                  onChange={(e) => setAddress({ ...address, zip: e.target.value })}
                  className="input"
                  placeholder="10001"
                  style={{ borderRadius: 10 }}
                  disabled={loading}
                />
              </div>
              <div>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  marginBottom: 6,
                  color: 'var(--text-secondary)',
                  fontWeight: 500,
                }}>
                  Country *
                </label>
                <input
                  type="text"
                  value={address.country}
                  onChange={(e) => setAddress({ ...address, country: e.target.value })}
                  className="input"
                  placeholder="United States"
                  style={{
                    borderRadius: 10,
                    borderColor: errors.addressCountry && touched.addressCountry ? '#EF4444' : undefined,
                  }}
                  disabled={loading}
                />
                {errors.addressCountry && touched.addressCountry && (
                  <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                    {errors.addressCountry}
                  </p>
                )}
              </div>
            </div>

            {/* Billing Contact Name */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Billing contact name <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="text"
                value={billingContactName}
                onChange={(e) => setBillingContactName(e.target.value)}
                className="input"
                placeholder="John Doe"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              />
            </div>

            {/* Billing Contact Email */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Billing contact email <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="email"
                value={billingContactEmail}
                onChange={(e) => setBillingContactEmail(e.target.value)}
                className="input"
                placeholder="billing@example.com"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              />
            </div>

            {/* Phone */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Phone <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="input"
                placeholder="+1 (555) 123-4567"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              />
            </div>

            {/* Tax ID */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Tax ID / EIN <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="text"
                value={taxId}
                onChange={(e) => setTaxId(e.target.value)}
                className="input"
                placeholder="12-3456789"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              />
            </div>

            {/* Timezone */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Timezone
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="input"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              >
                {Intl.supportedValuesOf('timeZone').map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
          </>
        );

      case 4:
        return (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Branding (Optional)</h2>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Add a logo to personalize your organization. You can skip this step and add it later from settings.
            </p>

            {/* Logo URL */}
            <div style={{ marginBottom: 12 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                marginBottom: 6,
                color: 'var(--text-secondary)',
                fontWeight: 500,
              }}>
                Logo URL <span style={{ fontSize: 12, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="url"
                value={logo}
                onChange={(e) => setLogo(e.target.value)}
                className="input"
                placeholder="https://example.com/logo.png"
                style={{ borderRadius: 10, width: '100%' }}
                disabled={loading}
              />
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                Recommended size: 200x200px, PNG or SVG format
              </p>
            </div>

            {logo && (
              <div style={{ marginTop: 16, textAlign: 'center' }}>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>Preview:</p>
                <img
                  src={logo}
                  alt="Logo preview"
                  style={{
                    maxWidth: 200,
                    maxHeight: 200,
                    objectFit: 'contain',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: 16,
                  }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
            )}
          </>
        );

      default:
        return null;
    }
  };

  return (
    <div>
      {errors.general && (
        <div style={{
          marginBottom: 16,
          padding: 12,
          background: '#FEF2F2',
          border: '1px solid #FCA5A5',
          borderRadius: 6,
          color: '#991B1B',
          fontSize: 14,
        }}>
          {errors.general}
        </div>
      )}

      {/* Progress Indicator */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          {Array.from({ length: totalSteps }, (_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: 4,
                background: i < currentStep ? 'var(--accent)' : '#E5E7EB',
                marginRight: i < totalSteps - 1 ? 4 : 0,
                borderRadius: 2,
                transition: 'background 0.3s',
              }}
            />
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center' }}>
          Step {currentStep} of {totalSteps}
        </p>
      </div>

      {/* Step Content */}
      <form onSubmit={(e) => { e.preventDefault(); handleNext(); }}>
        {renderStepContent()}

        {/* Navigation Buttons */}
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          {currentStep > 1 && (
            <button
              type="button"
              onClick={handlePrevious}
              className="btn"
              disabled={loading}
              style={{
                borderRadius: 9999,
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              <ChevronLeft size={16} />
              Back
            </button>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || (currentStep === 1 && (!slugAvailable || checkingSlug))}
            style={{
              borderRadius: 9999,
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              opacity: loading || (currentStep === 1 && (!slugAvailable || checkingSlug)) ? 0.7 : 1,
              cursor: loading || (currentStep === 1 && (!slugAvailable || checkingSlug)) ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Processing...' : currentStep === totalSteps ? 'Continue to team setup' : 'Continue'}
            {currentStep < totalSteps && <ChevronRight size={16} />}
          </button>
        </div>
      </form>

      {/* Back to signup options */}
      {currentStep === 1 && (
        <div style={{ marginTop: 16, textAlign: 'center', fontSize: 14, color: 'var(--text-secondary)' }}>
          <button
            onClick={onBack}
            disabled={loading}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent)',
              cursor: loading ? 'not-allowed' : 'pointer',
              textDecoration: 'underline',
              fontWeight: 600,
              padding: 0,
              fontSize: 14,
            }}
          >
            ← Back to signup options
          </button>
        </div>
      )}
    </div>
  );
};

export default OrganizationDetailsForm;
