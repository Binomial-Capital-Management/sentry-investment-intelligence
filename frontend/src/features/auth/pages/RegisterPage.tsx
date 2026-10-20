/**
 * Register page - combines AuthLayout with RegisterForm and org signup flow
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '@clerk/clerk-react';
import { ChevronsUpDown } from 'lucide-react';
import { AuthLayout } from '../components/AuthLayout';
import { RegisterForm } from '../components/RegisterForm';
import { isClerkConfigured } from '../hooks/useDevAuth';
import { AUTH_ROUTES } from '../constants';
import { FallbackRegisterForm } from './FallbackForms';
import type { PendingOrgData, TeamInvite } from '../types';

// Import existing org forms (they're well-built, no need to rewrite)
import OrganizationDetailsForm from '../../../components/Landing/OrganizationDetailsForm';
import TeamInvitationForm from '../../../components/Landing/TeamInvitationForm';

type AccountType = 'personal' | 'organization';
type OrgStep = 'details' | 'team' | 'account';

export function RegisterPage() {
  const navigate = useNavigate();
  const clerkConfigured = isClerkConfigured();
  
  // Always call hook unconditionally
  const { isSignedIn } = useUser();

  // Account type selection
  const [accountType, setAccountType] = useState<AccountType>('personal');
  const [showAccountTypeDropdown, setShowAccountTypeDropdown] = useState(false);

  // Organization signup state
  const [orgStep, setOrgStep] = useState<OrgStep>('details');
  const [pendingOrgData, setPendingOrgData] = useState<PendingOrgData | null>(null);
  const [pendingInvites, setPendingInvites] = useState<TeamInvite[]>([]);

  // Redirect if already signed in
  useEffect(() => {
    if (clerkConfigured && isSignedIn) {
      navigate(AUTH_ROUTES.CHAT);
    }
  }, [isSignedIn, navigate, clerkConfigured]);

  const handleAccountTypeChange = (type: AccountType) => {
    setAccountType(type);
    setShowAccountTypeDropdown(false);
    setOrgStep('details');
    setPendingOrgData(null);
    setPendingInvites([]);
  };

  if (!clerkConfigured) {
    return (
      <AuthLayout>
        <FallbackRegisterForm />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <h1 className="text-[28px] font-extrabold mb-2">
        {accountType === 'organization' ? 'Create your organization' : 'Create your account'}
      </h1>
      <p className="text-[var(--text-secondary)] mb-6">
        {accountType === 'organization' 
          ? 'Set up a shared workspace for your team' 
          : 'Start using the agentic risk workspace today.'}
      </p>

      {/* Account Type Selector */}
      <div className="flex justify-between items-center relative mb-6">
        <label className="text-sm text-[#1F1F1F] font-medium">
          Account type
        </label>
        <button
          type="button"
          onClick={() => setShowAccountTypeDropdown(!showAccountTypeDropdown)}
          className="px-3 py-1.5 text-sm border-none rounded bg-transparent text-[#1F1F1F] cursor-pointer font-normal relative flex items-center gap-1.5"
        >
          {accountType === 'personal' ? 'Personal Account' : 'Create Organization'}
          <ChevronsUpDown size={14} />
        </button>

        {showAccountTypeDropdown && (
          <div className="absolute top-full right-0 mt-1 min-w-[180px] bg-white border border-[#EDEBE9] rounded-lg shadow-lg z-10 overflow-hidden">
            <div
              onClick={() => handleAccountTypeChange('personal')}
              className={`px-3.5 py-2.5 cursor-pointer flex items-center justify-between text-sm hover:bg-gray-100 ${
                accountType === 'personal' ? 'bg-gray-100' : ''
              }`}
            >
              <span>Personal Account</span>
              {accountType === 'personal' && <span>✓</span>}
            </div>
            <div
              onClick={() => handleAccountTypeChange('organization')}
              className={`px-3.5 py-2.5 cursor-pointer flex items-center justify-between text-sm hover:bg-gray-100 ${
                accountType === 'organization' ? 'bg-gray-100' : ''
              }`}
            >
              <span>Create Organization</span>
              {accountType === 'organization' && <span>✓</span>}
            </div>
          </div>
        )}
      </div>

      {/* Conditional Forms Based on Account Type */}
      {accountType === 'organization' && orgStep === 'details' ? (
        <OrganizationDetailsForm
          onComplete={(orgData) => {
            setPendingOrgData(orgData as PendingOrgData);
            setOrgStep('team');
          }}
          onBack={() => navigate(AUTH_ROUTES.LANDING)}
        />
      ) : accountType === 'organization' && orgStep === 'team' ? (
        <TeamInvitationForm
          organizationName={pendingOrgData?.organizationName || ''}
          onComplete={(invites) => {
            setPendingInvites(invites as TeamInvite[]);
            setOrgStep('account');
          }}
          onSkip={() => {
            setPendingInvites([]);
            setOrgStep('account');
          }}
        />
      ) : (
        <RegisterForm
          pendingOrgData={pendingOrgData}
          pendingInvites={pendingInvites}
        />
      )}
    </AuthLayout>
  );
}

export default RegisterPage;
