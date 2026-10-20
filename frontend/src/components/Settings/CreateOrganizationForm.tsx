import { useState, useEffect } from 'react';
import { useClerk, useOrganizationList } from '@clerk/clerk-react';
import {
  Building2, Check, X, Loader2, ArrowRight, Users, Globe, LineChart, ShieldCheck,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { organizationApiService } from '@/services/organizationApi';

// Industry options
const INDUSTRIES = [
  'Finance & Banking',
  'Asset Management',
  'Private Equity',
  'Venture Capital',
  'Hedge Fund',
  'Family Office',
  'Insurance',
  'Technology',
  'Healthcare',
  'Real Estate',
  'Consulting',
  'Other',
];

interface CreateOrganizationFormProps {
  onSuccess?: () => void;
}

const CreateOrganizationForm = ({ onSuccess }: CreateOrganizationFormProps) => {
  const clerk = useClerk();
  const { createOrganization } = useOrganizationList();

  // Form state
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [industry, setIndustry] = useState('');
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);

  // Validation state
  const [slugAvailable, setSlugAvailable] = useState<boolean | null>(null);
  const [checkingSlug, setCheckingSlug] = useState(false);
  const [slugError, setSlugError] = useState('');

  // Form state
  const [creating, setCreating] = useState(false);
  const [step, setStep] = useState<'form' | 'success'>('form');
  const [createdOrg, setCreatedOrg] = useState<{ id: string; name: string; slug: string } | null>(null);

  // Auto-generate slug from name
  const generateSlug = (orgName: string) => {
    return orgName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 63);
  };

  // Handle name change
  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setName(value);

    if (!slugManuallyEdited) {
      const newSlug = generateSlug(value);
      setSlug(newSlug);
      setSlugAvailable(null);
      setSlugError('');
    }
  };

  // Handle slug change
  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(value);
    setSlugManuallyEdited(true);
    setSlugAvailable(null);
    setSlugError('');
  };

  // Check slug availability with debounce (checks against your DB)
  useEffect(() => {
    if (slug.length < 3) {
      setSlugAvailable(null);
      if (slug.length > 0) {
        setSlugError('Slug must be at least 3 characters');
      }
      return;
    }

    setCheckingSlug(true);
    const timer = setTimeout(async () => {
      try {
        const result = await organizationApiService.checkSlugAvailability(slug);
        setSlugAvailable(result.available);
        if (!result.available) {
          setSlugError(result.message || 'This slug is already taken');
        } else {
          setSlugError('');
        }
      } catch (error) {
        console.error('Error checking slug:', error);
        setSlugAvailable(null);
      } finally {
        setCheckingSlug(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [slug]);

  // Create organization - same pattern as CustomRegisterForm.tsx
  const handleCreate = async () => {
    if (!name || !slug || !slugAvailable) return;

    // Check if clerk.createOrganization is available
    if (!createOrganization) {
      console.error('[CreateOrg] createOrganization not available');
      toast.error('Unable to create organization. Please try refreshing the page.');
      return;
    }

    setCreating(true);

    try {
      console.log('[CreateOrg] Creating organization via Clerk SDK...');

      // Step 1: Create organization in Clerk
      const organization = await createOrganization({
        name,
        slug,
        ...(industry && {
          publicMetadata: {
             industry,
          },
        }),
      });

      console.log('[CreateOrg] ✓ Organization created in Clerk:', organization?.id);

      // Step 2: Sync to Backend immediately (since webhooks may be missing/delayed)
      if (organization) {
        try {
          await organizationApiService.createOrganization({
            name: organization.name,
            slug: organization.slug || slug,
            industry,
            id: organization.id, // Pass Clerk ID to backend
          });
          console.log('[CreateOrg] ✓ Synced to backend');
        } catch (syncError) {
          console.error('[CreateOrg] ⚠️ Failed to sync to backend (might be handled by webhook):', syncError);
          // Continue anyway, as Clerk creation was successful
        }
      }

      // Step 3: Set as active organization
      if (organization && clerk?.setActive) {
        await clerk.setActive({ organization: organization.id });
        localStorage.setItem('activeOrganization', organization.id);
      }

      setCreatedOrg({
        id: organization.id,
        name: organization.name,
        slug: organization.slug || slug,
      });
      setStep('success');
      toast.success('Organization created successfully');

    } catch (error: any) {
      console.error('[CreateOrg] Failed to create organization:', error);

      let errorMessage = 'Failed to create organization';

      if (error?.errors?.[0]?.code === 'form_identifier_exists') {
        errorMessage = 'This organization slug is already taken';
      } else if (error?.errors?.[0]?.message) {
        errorMessage = error.errors[0].message;
      }

      toast.error(errorMessage);
    } finally {
      setCreating(false);
    }
  };

  // Refresh page to load new org context
  const handleContinue = () => {
    window.location.reload();
  };

  // Check if form is valid
  const isFormValid = name.length > 0 && slug.length >= 3 && slugAvailable === true;

  // Success state
  if (step === 'success' && createdOrg) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-white border border-gray-200 rounded-lg p-8 shadow-sm text-center">
          <div className="w-12 h-12 bg-green-50 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Organization Ready</h2>
          <p className="text-gray-600 mb-6">
            <span className="font-medium text-gray-900">{createdOrg.name}</span> has been created successfully.
          </p>

          <div className="flex flex-col gap-3">
            <button
              onClick={handleContinue}
              className="w-full inline-flex justify-center items-center gap-2 px-4 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-black transition-colors"
            >
              Go to Dashboard
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => onSuccess?.()}
              className="w-full px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              Stay here
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Form state
  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-gray-900 tracking-tight">Create Organization</h2>
        <p className="text-gray-500 mt-1">
          Establish a new workspace for your team.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        <div className="p-6 sm:p-8">
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-6">

            {/* Organization Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Organization Name
              </label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={name}
                  onChange={handleNameChange}
                  placeholder="e.g. Acme Capital"
                  className="w-full pl-10 pr-4 py-2.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-all placeholder:text-gray-400"
                  disabled={creating}
                  autoFocus
                />
              </div>
            </div>

            {/* Slug */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Workspace URL
              </label>
              <div className="flex rounded-md shadow-sm">
                <span className="inline-flex items-center px-3 rounded-l-md border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                  binomialsentry.ai/
                </span>
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={slug}
                    onChange={handleSlugChange}
                    placeholder="acme-capital"
                    className={`block w-full rounded-none rounded-r-md border py-2.5 pl-3 pr-10 text-sm focus:outline-none focus:ring-2 transition-all ${
                      slugError
                        ? 'border-red-300 focus:ring-red-200 focus:border-red-300'
                        : 'border-gray-300 focus:ring-gray-900 focus:border-transparent'
                    }`}
                    disabled={creating}
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                    {checkingSlug && <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />}
                    {!checkingSlug && slugAvailable === true && <Check className="w-4 h-4 text-green-500" />}
                    {!checkingSlug && slugAvailable === false && <X className="w-4 h-4 text-red-500" />}
                  </div>
                </div>
              </div>
              {slugError ? (
                <p className="mt-1.5 text-xs text-red-600">{slugError}</p>
              ) : slugAvailable === true ? (
                <p className="mt-1.5 text-xs text-green-600">Available</p>
              ) : null}
            </div>

            {/* Industry */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Industry <span className="text-gray-400 font-normal">(Optional)</span>
              </label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-all bg-white"
                disabled={creating}
              >
                <option value="">Select industry...</option>
                {INDUSTRIES.map((ind) => (
                  <option key={ind} value={ind}>{ind}</option>
                ))}
              </select>
            </div>

            {/* Info Section */}
            <div className="bg-gray-50 rounded-md p-4 border border-gray-100">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Included with Organization</h4>
              <ul className="space-y-2.5">
                <li className="flex items-center gap-2.5 text-sm text-gray-600">
                  <Users className="w-4 h-4 text-gray-400" />
                  <span>Team collaboration & member management</span>
                </li>
                <li className="flex items-center gap-2.5 text-sm text-gray-600">
                  <Globe className="w-4 h-4 text-gray-400" />
                  <span>Shared portfolios and assets</span>
                </li>
                <li className="flex items-center gap-2.5 text-sm text-gray-600">
                  <ShieldCheck className="w-4 h-4 text-gray-400" />
                  <span>Enterprise-grade security & permissions</span>
                </li>
              </ul>
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={!isFormValid || creating}
                className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-all ${
                  isFormValid && !creating
                    ? 'bg-gray-900 text-white hover:bg-black shadow-sm'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    Create Organization
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
        <div className="bg-gray-50 px-6 py-4 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            Organizations are isolated environments. Your personal data remains private.
          </p>
        </div>
      </div>
    </div>
  );
};

export default CreateOrganizationForm;
