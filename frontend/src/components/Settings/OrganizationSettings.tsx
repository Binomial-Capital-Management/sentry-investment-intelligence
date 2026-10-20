import { useState, useEffect } from 'react';
import { useUser, useOrganization, useOrganizationList } from '@clerk/clerk-react';
import {
  Building2, Users, Trash2, Save, X, UserPlus, AlertTriangle,
  Mail, Clock, CheckCircle, XCircle, RefreshCw, Crown, LogOut,
  Info, Settings, ChevronRight, Plus,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { organizationApiService, type Organization, type OrganizationMember, type Invitation } from '@/services/organizationApi';
import CreateOrganizationForm from './CreateOrganizationForm';

type TabType = 'members' | 'invitations' | 'settings' | 'danger-zone';

const OrganizationSettings = () => {
  const { user } = useUser();
  const { organization } = useOrganization();
  const { userMemberships, setActive } = useOrganizationList({
    userMemberships: { infinite: true },
  });

  // View mode: 'list' shows all orgs user belongs to, 'detail' shows current org settings, 'create' shows create form
  const [viewMode, setViewMode] = useState<'list' | 'detail' | 'create'>('list');
  const [switchingOrg, setSwitchingOrg] = useState<string | null>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('members');

  // Data state
  const [orgData, setOrgData] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadingInvitations, setLoadingInvitations] = useState(false);

  // Edit organization form
  const [editedName, setEditedName] = useState('');
  const [editedIndustry, setEditedIndustry] = useState('');
  const [hasChanges, setHasChanges] = useState(false);

  // Invite member form
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'org:admin' | 'org:member'>('org:member');
  const [inviting, setInviting] = useState(false);
  const [emailError, setEmailError] = useState('');

  // Member actions
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);
  const [removingMember, setRemovingMember] = useState<string | null>(null);

  // Invitation actions
  const [resendingInvite, setResendingInvite] = useState<string | null>(null);
  const [revokingInvite, setRevokingInvite] = useState<string | null>(null);

  // Confirmation modals
  const [confirmAction, setConfirmAction] = useState<{
    type: 'leave' | 'delete' | 'remove-member' | 'revoke-invite' | null;
    data?: any;
  }>({ type: null });
  const [actionInProgress, setActionInProgress] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');

  // Check if user is admin
  const isAdmin = members.some(m => m.user_id === user?.id && m.role === 'org:admin');
  // Check if user is the creator (uses creator_id from org data)
  // If creator_id is null (orphaned org), any admin can delete
  const isCreator = orgData?.creator_id === user?.id || (orgData?.creator_id === null && isAdmin);

  // Load organization data
  useEffect(() => {
    if (!organization?.id) {
      setLoading(false);
      return;
    }
    loadOrganizationData();
  }, [organization?.id]);

  const loadOrganizationData = async () => {
    if (!organization?.id) return;

    try {
      setLoading(true);
      const [org, membersList] = await Promise.all([
        organizationApiService.getOrganization(organization.id),
        organizationApiService.getMembers(organization.id),
      ]);

      setOrgData(org);
      setMembers(membersList);
      setEditedName(org.name);
      setEditedIndustry('');

      if (isAdmin) {
        loadInvitations();
      }
    } catch (error: any) {
      console.error('Failed to load organization:', error);
      toast.error(error.message || 'Failed to load organization data');
    } finally {
      setLoading(false);
    }
  };

  const loadInvitations = async () => {
    if (!organization?.id) return;

    try {
      setLoadingInvitations(true);
      const invites = await organizationApiService.listInvitations(organization.id);
      setInvitations(invites);
    } catch (error: any) {
      console.error('Failed to load invitations:', error);
    } finally {
      setLoadingInvitations(false);
    }
  };

  // Track changes
  useEffect(() => {
    if (!orgData) return;
    const changed = editedName !== orgData.name || editedIndustry !== '';
    setHasChanges(changed);
  }, [editedName, editedIndustry, orgData]);

  // Save organization changes
  const handleSave = async () => {
    if (!organization?.id || !hasChanges) return;

    try {
      setSaving(true);
      const updates: any = {};
      if (editedName !== orgData?.name) updates.name = editedName;
      if (editedIndustry) updates.industry = editedIndustry;

      await organizationApiService.updateOrganization(organization.id, updates);
      toast.success('Organization updated successfully');
      setHasChanges(false);
      await loadOrganizationData();
    } catch (error: any) {
      console.error('Failed to save organization:', error);
      toast.error(error.message || 'Failed to update organization');
    } finally {
      setSaving(false);
    }
  };

  // Cancel changes
  const handleCancel = () => {
    if (!orgData) return;
    setEditedName(orgData.name);
    setEditedIndustry('');
    setHasChanges(false);
  };

  // Validate email
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email) {
      setEmailError('Email is required');
      return false;
    }
    if (!emailRegex.test(email)) {
      setEmailError('Please enter a valid email address');
      return false;
    }
    setEmailError('');
    return true;
  };

  // Invite member
  const handleInviteMember = async () => {
    if (!organization?.id) return;
    if (!validateEmail(inviteEmail)) return;

    try {
      setInviting(true);
      await organizationApiService.inviteMember(organization.id, {
        email: inviteEmail,
        role: inviteRole,
      });

      toast.success(`Invitation sent to ${inviteEmail}`);
      setInviteEmail('');
      setInviteRole('org:member');
      setEmailError('');
      setShowInviteModal(false);
      await loadInvitations();
    } catch (error: any) {
      console.error('Failed to invite member:', error);
      toast.error(error.message || 'Failed to send invitation');
    } finally {
      setInviting(false);
    }
  };

  // Update member role
  const handleUpdateRole = async (userId: string, newRole: 'org:admin' | 'org:member') => {
    if (!organization?.id) return;

    try {
      setUpdatingRole(userId);
      await organizationApiService.updateMemberRole(organization.id, userId, { role: newRole });
      toast.success('Member role updated successfully');
      await loadOrganizationData();
    } catch (error: any) {
      console.error('Failed to update role:', error);
      toast.error(error.message || 'Failed to update member role');
    } finally {
      setUpdatingRole(null);
    }
  };

  // Remove member
  const handleRemoveMember = async () => {
    if (!organization?.id || !confirmAction.data) return;

    try {
      setActionInProgress(true);
      await organizationApiService.removeMember(organization.id, confirmAction.data.userId);
      toast.success(`${confirmAction.data.userName} removed from organization`);
      await loadOrganizationData();
      setConfirmAction({ type: null });
    } catch (error: any) {
      console.error('Failed to remove member:', error);
      toast.error(error.message || 'Failed to remove member');
    } finally {
      setActionInProgress(false);
    }
  };

  // Resend invitation
  const handleResendInvitation = async (invitationId: string, email: string) => {
    if (!organization?.id) return;

    try {
      setResendingInvite(invitationId);
      await organizationApiService.resendInvitation(organization.id, invitationId);
      toast.success(`Invitation resent to ${email}`);
      await loadInvitations();
    } catch (error: any) {
      console.error('Failed to resend invitation:', error);
      toast.error(error.message || 'Failed to resend invitation');
    } finally {
      setResendingInvite(null);
    }
  };

  // Revoke invitation
  const handleRevokeInvitation = async () => {
    if (!organization?.id || !confirmAction.data) return;

    try {
      setActionInProgress(true);
      await organizationApiService.revokeInvitation(organization.id, confirmAction.data.invitationId);
      toast.success('Invitation revoked successfully');
      await loadInvitations();
      setConfirmAction({ type: null });
    } catch (error: any) {
      console.error('Failed to revoke invitation:', error);
      toast.error(error.message || 'Failed to revoke invitation');
    } finally {
      setActionInProgress(false);
    }
  };

  // Leave organization (from detail view / danger zone)
  const handleLeaveOrganization = async () => {
    if (!organization?.id) return;

    try {
      setActionInProgress(true);

      // Use Clerk SDK first (source of truth)
      const membership = userMemberships?.data?.find(m => m.organization.id === organization.id);
      if (membership) {
        await membership.destroy();
      } else {
        // Fallback to backend
        await organizationApiService.leaveOrganization(organization.id);
      }

      // CRITICAL: Clear localStorage
      localStorage.removeItem('activeOrganization');

      toast.success('Left organization successfully');
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 1000);
    } catch (error: any) {
      console.error('Failed to leave organization:', error);
      const errorMessage = error?.message || error?.toString() || '';
      if (errorMessage.includes('minimum required permissions') || errorMessage.includes('at least one')) {
        toast.error('Cannot leave: You are the last admin. Promote another member first, or delete the organization.');
      } else {
        toast.error(error.message || 'Failed to leave organization');
      }
      setActionInProgress(false);
      setConfirmAction({ type: null });
    }
  };

  // Delete organization
  const handleDeleteOrganization = async () => {
    if (!organization?.id || !orgData) return;
    if (deleteConfirmText !== orgData.slug) {
      toast.error('Please type the organization slug to confirm deletion');
      return;
    }

    try {
      setActionInProgress(true);
      await organizationApiService.deleteOrganization(organization.id);
      toast.success('Organization deleted successfully');
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 1000);
    } catch (error: any) {
      console.error('Failed to delete organization:', error);
      toast.error(error.message || 'Failed to delete organization');
      setActionInProgress(false);
    }
  };

  // Get status badge
  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; icon: any; text: string }> = {
      pending: { color: 'bg-blue-50 text-blue-700 border-blue-200', icon: Clock, text: 'Pending' },
      accepted: { color: 'bg-green-50 text-green-700 border-green-200', icon: CheckCircle, text: 'Accepted' },
      revoked: { color: 'bg-gray-50 text-gray-700 border-gray-200', icon: XCircle, text: 'Revoked' },
      expired: { color: 'bg-red-50 text-red-700 border-red-200', icon: XCircle, text: 'Expired' },
    };

    const config = statusConfig[status.toLowerCase()] || statusConfig.pending;
    const Icon = config.icon;

    return (
      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.text}
      </span>
    );
  };

  // Handle switching to an organization
  const handleSwitchToOrg = async (orgId: string) => {
    if (switchingOrg) return;
    setSwitchingOrg(orgId);
    try {
      if (setActive) {
        await setActive({ organization: orgId });
        localStorage.setItem('activeOrganization', orgId);
        // Reload to refresh context
        window.location.reload();
      }
    } catch (error) {
      console.error('Failed to switch organization:', error);
      toast.error('Failed to switch organization');
      setSwitchingOrg(null);
    }
  };

  // Handle leaving an organization (from list view)
  const handleLeaveFromList = async (orgId: string, orgName: string) => {
    if (!confirm(`Are you sure you want to leave "${orgName}"? You will lose access to this organization.`)) {
      return;
    }
    try {
      // Find the membership for this organization
      const membership = userMemberships?.data?.find(m => m.organization.id === orgId);

      console.log('[LeaveOrg] Found membership:', membership ? 'yes' : 'no', 'for org:', orgId);
      console.log('[LeaveOrg] Current user:', user?.id);

      if (membership) {
        // Use Clerk SDK to destroy the membership (source of truth)
        // Webhook will sync to backend automatically
        console.log('[LeaveOrg] Calling membership.destroy()...');
        await membership.destroy();
        console.log('[LeaveOrg] ✓ membership.destroy() succeeded');
        toast.success(`Left ${orgName} successfully`);
      } else {
        // Fallback to backend API if membership not found in Clerk state
        console.log('[LeaveOrg] No membership found, falling back to backend API');
        await organizationApiService.leaveOrganization(orgId);
        toast.success(`Left ${orgName} successfully`);
      }

      // CRITICAL: Clear localStorage if leaving the currently active org
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId === orgId) {
        console.log('[LeaveOrg] Clearing activeOrganization from localStorage');
        localStorage.removeItem('activeOrganization');
      }

      // Refresh the page to update Clerk's membership list
      window.location.reload();
    } catch (error: any) {
      console.error('[LeaveOrg] Failed to leave organization:', error);

      // Handle Clerk's "last admin" protection
      const errorMessage = error?.message || error?.toString() || '';
      if (errorMessage.includes('minimum required permissions') || errorMessage.includes('at least one')) {
        toast.error('Cannot leave: You are the last admin. Promote another member first, or delete the organization.');
      } else {
        toast.error(error.message || 'Failed to leave organization');
      }
    }
  };

  // Render loading state
  if (loading && organization) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-gray-900 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-sm text-gray-600">Loading organization settings...</p>
        </div>
      </div>
    );
  }

  // Determine what to show based on context
  const hasOrganizations = userMemberships?.data && userMemberships.data.length > 0;
  const isInOrganization = !!organization;

  // Show CREATE form only when explicitly requested or when user has no orgs
  if (viewMode === 'create' || (!hasOrganizations && !isInOrganization)) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4">
        {hasOrganizations && (
          <button
            onClick={() => setViewMode('list')}
            className="mb-6 text-sm text-gray-500 hover:text-gray-900 flex items-center gap-1"
          >
            ← Back to Organizations
          </button>
        )}
        <CreateOrganizationForm
          onSuccess={() => {
            window.location.reload();
          }}
        />
      </div>
    );
  }

  // Show LIST view when in personal workspace but user has organizations
  if (!isInOrganization && hasOrganizations && viewMode === 'list') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Your Organizations</h1>
            <p className="text-sm text-gray-500 mt-1">
              You're currently in your personal workspace. Select an organization to manage it.
            </p>
          </div>
          <button
            onClick={() => setViewMode('create')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-black transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Organization
          </button>
        </div>

        <div className="space-y-3">
          {userMemberships?.data?.map((membership) => (
            <div
              key={membership.organization.id}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {membership.organization.imageUrl ? (
                    <img
                      src={membership.organization.imageUrl}
                      alt={membership.organization.name}
                      className="w-10 h-10 rounded-md object-cover border border-gray-200"
                    />
                  ) : (
                    <div className="w-10 h-10 bg-gray-100 rounded-md flex items-center justify-center border border-gray-200">
                      <Building2 className="w-5 h-5 text-gray-500" />
                    </div>
                  )}
                  <div>
                    <h3 className="font-medium text-gray-900">{membership.organization.name}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                        {membership.role === 'org:admin' ? (
                          <>
                            <Crown className="w-3 h-3" />
                            Admin
                          </>
                        ) : (
                          <>
                            <Users className="w-3 h-3" />
                            Member
                          </>
                        )}
                      </span>
                      {membership.organization.slug && (
                        <span className="text-xs text-gray-400">
                          /{membership.organization.slug}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleLeaveFromList(membership.organization.id, membership.organization.name)}
                    className="px-3 py-1.5 text-xs font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                    title="Leave organization"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleSwitchToOrg(membership.organization.id)}
                    disabled={switchingOrg === membership.organization.id}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    {switchingOrg === membership.organization.id ? (
                      <>
                        <div className="w-3 h-3 border border-gray-400 border-t-transparent rounded-full animate-spin" />
                        Switching...
                      </>
                    ) : (
                      <>
                        Switch & Manage
                        <ChevronRight className="w-3 h-3" />
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 p-4 bg-blue-50 border border-blue-100 rounded-lg">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-blue-900">Tip: Switch Workspaces</h4>
              <p className="text-sm text-blue-700 mt-1">
                Use the workspace switcher in the top navigation to quickly switch between your personal workspace and organizations.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // If we're in an org but don't have orgData yet, show loading
  if (isInOrganization && !orgData) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-gray-900 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-sm text-gray-600">Loading organization settings...</p>
        </div>
      </div>
    );
  }

  // Fallback: if somehow we have no org and no memberships, show create form
  if (!orgData) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4">
        <CreateOrganizationForm
          onSuccess={() => {
            window.location.reload();
          }}
        />
      </div>
    );
  }

  const pendingInvitationsCount = invitations.filter(i => i.status === 'pending').length;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center gap-4">
        {organization?.imageUrl ? (
          <img
            src={organization.imageUrl}
            alt={`${orgData.name} logo`}
            className="w-12 h-12 rounded-md object-cover border border-gray-200"
          />
        ) : (
          <div className="w-12 h-12 bg-gray-100 rounded-md flex items-center justify-center border border-gray-200">
            <Building2 className="w-6 h-6 text-gray-500" />
          </div>
        )}
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">{orgData.name}</h1>
          <p className="text-sm text-gray-500">Organization Settings</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-8">
        <nav className="flex space-x-8" role="tablist">
          {[
            { id: 'members', label: 'Members', icon: Users, count: members.length },
            ...(isAdmin ? [{ id: 'invitations', label: 'Invitations', icon: Mail, count: pendingInvitationsCount > 0 ? pendingInvitationsCount : undefined }] : []),
            { id: 'settings', label: 'Settings', icon: Settings },
            { id: 'danger-zone', label: 'Danger Zone', icon: AlertTriangle },
          ].map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`pb-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center gap-2">
                <tab.icon className="w-4 h-4" />
                {tab.label}
                {tab.count !== undefined && (
                  <span className={`ml-1 px-1.5 py-0.5 text-xs font-medium rounded-full ${activeTab === tab.id ? 'bg-gray-100 text-gray-900' : 'bg-gray-100 text-gray-600'}`}>
                    {tab.count}
                  </span>
                )}
              </div>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* Members Tab */}
        {activeTab === 'members' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-gray-900">Team Members</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Manage access and roles.
                </p>
              </div>
              {isAdmin ? (
                <button
                  onClick={() => setShowInviteModal(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-black transition-colors"
                >
                  <UserPlus className="w-4 h-4" />
                  Invite Member
                </button>
              ) : (
                <div className="group relative">
                  <button
                    disabled
                    className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-400 text-sm font-medium rounded-md cursor-not-allowed"
                  >
                    <UserPlus className="w-4 h-4" />
                    Invite Member
                  </button>
                  <div className="absolute bottom-full mb-2 right-0 w-48 p-2 bg-gray-800 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Only admins can invite new members. Contact an admin to add users.
                  </div>
                </div>
              )}
            </div>

            {members.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200 border-dashed">
                <Users className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <p className="text-sm font-medium text-gray-900">No members found</p>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
                <table className="w-full text-sm text-left">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-medium">
                    <tr>
                      <th className="py-3 px-4">User</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Joined</th>
                      {isAdmin && <th className="py-3 px-4 text-right">Actions</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {members.map((member) => (
                      <tr key={member.user_id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="py-3 px-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-900">{member.name || 'Unknown User'}</span>
                              {member.user_id === user?.id && (
                                <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600 border border-gray-200">You</span>
                              )}
                            </div>
                            <div className="text-gray-500 mt-0.5">{member.email}</div>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          {isAdmin ? (
                            <div className="flex flex-col">
                              <select
                                value={member.role}
                                onChange={(e) => handleUpdateRole(member.user_id, e.target.value as 'org:admin' | 'org:member')}
                                disabled={
                                  updatingRole === member.user_id ||
                                  (member.role === 'org:admin' && members.filter(m => m.role === 'org:admin').length === 1)
                                }
                                className="text-xs font-medium px-2 py-1 border border-gray-300 rounded bg-white hover:bg-gray-50 focus:ring-2 focus:ring-gray-900 focus:border-transparent disabled:opacity-50 disabled:bg-gray-100"
                                title={
                                  member.role === 'org:admin' && members.filter(m => m.role === 'org:admin').length === 1
                                    ? 'Cannot demote the last admin'
                                    : 'Change member role'
                                }
                              >
                                <option value="org:member">Member</option>
                                <option value="org:admin">Admin</option>
                              </select>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                                {member.role === 'org:admin' ? <Crown className="w-3 h-3" /> : <Users className="w-3 h-3" />}
                                {member.role === 'org:admin' ? 'Admin' : 'Member'}
                              </span>
                              {!isAdmin && (
                                <span className="text-xs text-gray-400" title="Contact an admin to change roles">
                                  (Read-only)
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-gray-500">
                          {new Date(member.joined_at).toLocaleDateString()}
                        </td>
                        {isAdmin && (
                          <td className="py-3 px-4 text-right">
                            {member.user_id !== user?.id && (
                              <button
                                onClick={() => setConfirmAction({
                                  type: 'remove-member',
                                  data: { userId: member.user_id, userName: member.name || 'this member' },
                                })}
                                disabled={removingMember === member.user_id}
                                className="text-gray-400 hover:text-red-600 transition-colors p-1"
                                title="Remove member"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Invitations Tab */}
        {activeTab === 'invitations' && isAdmin && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Pending Invitations</h2>
              <p className="text-sm text-gray-500 mt-1">
                Manage outstanding invitations.
              </p>
            </div>

            {loadingInvitations ? (
              <div className="text-center py-12">
                <div className="w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full animate-spin mx-auto"></div>
              </div>
            ) : invitations.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200 border-dashed">
                <Mail className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <p className="text-sm font-medium text-gray-900">No pending invitations</p>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
                <table className="w-full text-sm text-left">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-medium">
                    <tr>
                      <th className="py-3 px-4">Email</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Sent</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {invitations.map((invitation) => (
                      <tr key={invitation.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="py-3 px-4 font-medium text-gray-900">{invitation.email_address}</td>
                        <td className="py-3 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                            {invitation.role === 'org:admin' ? 'Admin' : 'Member'}
                          </span>
                        </td>
                        <td className="py-3 px-4">{getStatusBadge(invitation.status)}</td>
                        <td className="py-3 px-4 text-gray-500">{new Date(invitation.created_at).toLocaleDateString()}</td>
                        <td className="py-3 px-4 text-right">
                          {invitation.status === 'pending' && (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleResendInvitation(invitation.id, invitation.email_address)}
                                disabled={resendingInvite === invitation.id}
                                className="text-gray-400 hover:text-gray-900 transition-colors"
                                title="Resend"
                              >
                                <RefreshCw className={`w-4 h-4 ${resendingInvite === invitation.id ? 'animate-spin' : ''}`} />
                              </button>
                              <button
                                onClick={() => setConfirmAction({
                                  type: 'revoke-invite',
                                  data: { invitationId: invitation.id, email: invitation.email_address },
                                })}
                                disabled={revokingInvite === invitation.id}
                                className="text-gray-400 hover:text-red-600 transition-colors"
                                title="Revoke"
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Organization Settings</h2>
              <p className="text-sm text-gray-500 mt-1">
                General configuration.
              </p>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Organization Name</label>
                  <input
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    disabled={!isAdmin}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-gray-900 focus:border-transparent disabled:bg-gray-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Slug</label>
                  <input
                    type="text"
                    value={orgData.slug}
                    disabled
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Industry</label>
                  <input
                    type="text"
                    value={editedIndustry}
                    onChange={(e) => setEditedIndustry(e.target.value)}
                    disabled={!isAdmin}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-gray-900 focus:border-transparent disabled:bg-gray-50"
                    placeholder="e.g. Finance"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Usage Credits</label>
                  <div className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-gray-50 text-gray-900 font-mono">
                    {orgData.usage_credits.toLocaleString()}
                  </div>
                </div>
              </div>

              {isAdmin && hasChanges && (
                <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-black transition-colors disabled:opacity-50"
                  >
                    <Save className="w-4 h-4" />
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    onClick={handleCancel}
                    disabled={saving}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Danger Zone Tab */}
        {activeTab === 'danger-zone' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Danger Zone</h2>
              <p className="text-sm text-gray-500 mt-1">
                Irreversible actions.
              </p>
            </div>

            {!isCreator && (
              <div className="bg-white border border-gray-200 rounded-lg p-6 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Leave Organization</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Revoke your access to this organization.
                    {isAdmin && members.filter(m => m.role === 'org:admin').length === 1 && (
                      <span className="block text-amber-600 mt-1">
                        ⚠️ You cannot leave because you are the last admin. Promote another member first.
                      </span>
                    )}
                  </p>
                </div>
                <button
                  onClick={() => setConfirmAction({ type: 'leave' })}
                  disabled={isAdmin && members.filter(m => m.role === 'org:admin').length === 1}
                  className="px-4 py-2 bg-white border border-gray-300 text-red-600 text-sm font-medium rounded-md hover:bg-red-50 hover:border-red-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Leave
                </button>
              </div>
            )}

            {isCreator && (
              <div className="bg-white border border-red-200 rounded-lg p-6 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Delete Organization</h3>
                  <p className="text-sm text-gray-500 mt-1">Permanently remove this organization and all data.</p>
                </div>
                <button
                  onClick={() => setConfirmAction({ type: 'delete' })}
                  className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 transition-colors"
                >
                  Delete Organization
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm" role="dialog" aria-modal="true">
          <div className="bg-white rounded-lg shadow-lg max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="text-base font-semibold text-gray-900">Invite Member</h3>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-gray-400 hover:text-gray-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email Address</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => {
                    setInviteEmail(e.target.value);
                    setEmailError('');
                  }}
                  placeholder="colleague@company.com"
                  className={`w-full px-3 py-2 text-sm border rounded-md focus:ring-2 focus:ring-gray-900 focus:border-transparent ${emailError ? 'border-red-300 focus:ring-red-200' : 'border-gray-300'}`}
                />
                {emailError && <p className="mt-1 text-xs text-red-600">{emailError}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as 'org:admin' | 'org:member')}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-gray-900 focus:border-transparent bg-white"
                >
                  <option value="org:member">Member</option>
                  <option value="org:admin">Admin</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 border-t border-gray-200">
              <button
                onClick={() => setShowInviteModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                Cancel
              </button>
              <button
                onClick={handleInviteMember}
                disabled={inviting || !inviteEmail}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-black disabled:opacity-50 transition-colors"
              >
                {inviting ? 'Sending...' : 'Send Invitation'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction.type && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm" role="dialog" aria-modal="true">
          <div className="bg-white rounded-lg shadow-lg max-w-md w-full p-6">
            <div className="flex items-start gap-4 mb-6">
              <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                confirmAction.type === 'delete' ? 'bg-red-50 text-red-600' : 'bg-yellow-50 text-yellow-600'
              }`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">
                  {confirmAction.type === 'delete' && 'Delete Organization?'}
                  {confirmAction.type === 'leave' && 'Leave Organization?'}
                  {confirmAction.type === 'remove-member' && 'Remove Member?'}
                  {confirmAction.type === 'revoke-invite' && 'Revoke Invitation?'}
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  {confirmAction.type === 'delete' && 'This action cannot be undone. All data will be permanently lost.'}
                  {confirmAction.type === 'leave' && 'You will lose access to this organization.'}
                  {confirmAction.type === 'remove-member' && `Are you sure you want to remove ${confirmAction.data?.userName}?`}
                  {confirmAction.type === 'revoke-invite' && `Are you sure you want to revoke the invitation for ${confirmAction.data?.email}?`}
                </p>
              </div>
            </div>

            {confirmAction.type === 'delete' && (
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Type <span className="font-mono text-red-600">{orgData?.slug}</span> to confirm
                </label>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
              </div>
            )}

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setConfirmAction({ type: null });
                  setDeleteConfirmText('');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (confirmAction.type === 'delete') handleDeleteOrganization();
                  else if (confirmAction.type === 'leave') handleLeaveOrganization();
                  else if (confirmAction.type === 'remove-member') handleRemoveMember();
                  else if (confirmAction.type === 'revoke-invite') handleRevokeInvitation();
                }}
                disabled={actionInProgress || (confirmAction.type === 'delete' && deleteConfirmText !== orgData?.slug)}
                className={`px-4 py-2 text-sm font-medium text-white rounded-md disabled:opacity-50 transition-colors ${
                  confirmAction.type === 'delete' || confirmAction.type === 'remove-member' || confirmAction.type === 'revoke-invite'
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-yellow-600 hover:bg-yellow-700'
                }`}
              >
                {actionInProgress ? 'Processing...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OrganizationSettings;
