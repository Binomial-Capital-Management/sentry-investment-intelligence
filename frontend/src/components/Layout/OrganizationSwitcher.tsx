import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser, useOrganization, useOrganizationList } from '@clerk/clerk-react';
import { ChevronDown, Building2, User, Settings } from 'lucide-react';

/**
 * OrganizationSwitcher component
 * Allows users to switch between personal workspace and organization workspaces
 * Uses Clerk's hooks for organization management
 */
const OrganizationSwitcher = () => {
  const navigate = useNavigate();
  const { user } = useUser();
  const { organization } = useOrganization();
  const { userMemberships, setActive } = useOrganizationList({
    userMemberships: {
      infinite: true,
    },
  });

  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setShowDropdown(false);
    if (showDropdown) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showDropdown]);

  // Handle workspace switching
  const handleSwitch = async (orgId: string | null) => {
    if (loading) return;

    try {
      setLoading(true);

      if (setActive) {
        await setActive({ organization: orgId });
      }

      setShowDropdown(false);

      // Store active organization in localStorage for persistence
      if (orgId) {
        localStorage.setItem('activeOrganization', orgId);
      } else {
        localStorage.removeItem('activeOrganization');
      }

      // Reload to ensure all state is fresh
      window.location.reload();
    } catch (error) {
      console.error('Failed to switch workspace:', error);
    } finally {
      setLoading(false);
    }
  };

  // Current workspace display
  const getCurrentWorkspace = () => {
    if (organization) {
      return {
        name: organization.name,
        type: 'organization' as const,
        id: organization.id,
      };
    }
    return {
      name: 'Personal',
      type: 'personal' as const,
      id: null,
    };
  };

  const currentWorkspace = getCurrentWorkspace();

  return (
    <div style={{ position: 'relative' }}>
      {/* Current Workspace Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          setShowDropdown(!showDropdown);
        }}
        disabled={loading}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 8px',
          background: '#252830',
          border: '1px solid #2a2d35',
          borderRadius: '4px',
          cursor: loading ? 'wait' : 'pointer',
          fontSize: '12px',
          fontWeight: 500,
          color: '#ffffff',
          transition: 'all 0.2s',
          opacity: loading ? 0.6 : 1,
        }}
        onMouseEnter={(e) => {
          if (!loading) {
            e.currentTarget.style.background = '#2d3038';
            e.currentTarget.style.borderColor = '#3a3d45';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#252830';
          e.currentTarget.style.borderColor = '#2a2d35';
        }}
      >
        {currentWorkspace.type === 'organization' ? (
          organization?.imageUrl ? (
            <img
              src={organization.imageUrl}
              alt={organization.name}
              style={{
                width: '14px',
                height: '14px',
                borderRadius: '3px',
                objectFit: 'cover',
                border: '1px solid #2a2d35',
              }}
            />
          ) : (
            <Building2 size={12} style={{ color: '#3b82f6' }} />
          )
        ) : (
          user?.imageUrl ? (
            <img
              src={user.imageUrl}
              alt={user.fullName || 'User'}
              style={{
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                objectFit: 'cover',
                border: '1px solid #2a2d35',
              }}
            />
          ) : (
            <User size={12} style={{ color: '#9ca3af' }} />
          )
        )}
        <span>{currentWorkspace.name}</span>
        <ChevronDown
          size={12}
          style={{
            color: '#9ca3af',
            transform: showDropdown ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        />
      </button>

      {/* Dropdown Menu */}
      {showDropdown && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            minWidth: '220px',
            background: '#1a1d23',
            border: '1px solid #2a2d35',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
            zIndex: 1000,
            padding: '6px',
          }}
        >
          {/* Personal Workspace */}
          <button
            onClick={() => handleSwitch(null)}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              width: '100%',
              padding: '6px 8px',
              background: currentWorkspace.type === 'personal' ? '#252830' : 'transparent',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'wait' : 'pointer',
              fontSize: '12px',
              fontWeight: currentWorkspace.type === 'personal' ? 600 : 500,
              color: '#ffffff',
              textAlign: 'left',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!loading && currentWorkspace.type !== 'personal') {
                e.currentTarget.style.background = '#252830';
              }
            }}
            onMouseLeave={(e) => {
              if (currentWorkspace.type !== 'personal') {
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            {user?.imageUrl ? (
              <img
                src={user.imageUrl}
                alt={user.fullName || 'User'}
                style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  objectFit: 'cover',
                  border: '1px solid #2a2d35',
                  flexShrink: 0,
                }}
              />
            ) : (
              <User size={14} style={{ color: '#9ca3af', flexShrink: 0 }} />
            )}
            <div style={{ flex: 1 }}>
              <div>Personal</div>
              <div style={{ fontSize: '10px', color: '#9ca3af', fontWeight: 400 }}>
                {user?.emailAddresses?.[0]?.emailAddress || 'Your workspace'}
              </div>
            </div>
            {currentWorkspace.type === 'personal' && (
              <div
                style={{
                  width: '5px',
                  height: '5px',
                  borderRadius: '50%',
                  background: '#3b82f6',
                  flexShrink: 0,
                }}
              />
            )}
          </button>

          {/* Divider if there are organizations */}
          {userMemberships && userMemberships.data && userMemberships.data.length > 0 && (
            <div
              style={{
                height: '1px',
                background: '#2a2d35',
                margin: '4px 0',
              }}
            />
          )}

          {/* Organizations */}
          {userMemberships?.data?.map((membership) => (
            <button
              key={membership.organization.id}
              onClick={() => handleSwitch(membership.organization.id)}
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                width: '100%',
                padding: '6px 8px',
                background:
                  currentWorkspace.id === membership.organization.id ? '#252830' : 'transparent',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'wait' : 'pointer',
                fontSize: '12px',
                fontWeight:
                  currentWorkspace.id === membership.organization.id ? 600 : 500,
                color: '#ffffff',
                textAlign: 'left',
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => {
                if (!loading && currentWorkspace.id !== membership.organization.id) {
                  e.currentTarget.style.background = '#252830';
                }
              }}
              onMouseLeave={(e) => {
                if (currentWorkspace.id !== membership.organization.id) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {membership.organization.imageUrl ? (
                <img
                  src={membership.organization.imageUrl}
                  alt={membership.organization.name}
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '4px',
                    objectFit: 'cover',
                    border: '1px solid #2a2d35',
                    flexShrink: 0,
                  }}
                />
              ) : (
                <Building2 size={14} style={{ color: '#3b82f6', flexShrink: 0 }} />
              )}
              <div style={{ flex: 1 }}>
                <div>{membership.organization.name}</div>
                <div
                  style={{ fontSize: '10px', color: '#9ca3af', fontWeight: 400 }}
                >
                  {membership.role === 'org:admin' ? 'Admin' : 'Member'}
                </div>
              </div>
              {currentWorkspace.id === membership.organization.id && (
                <div
                  style={{
                    width: '5px',
                    height: '5px',
                    borderRadius: '50%',
                    background: '#3b82f6',
                    flexShrink: 0,
                  }}
                />
              )}
            </button>
          ))}

          {/* No organizations message */}
          {(!userMemberships?.data || userMemberships.data.length === 0) && (
            <div
              style={{
                padding: '6px 8px',
                fontSize: '11px',
                color: '#9ca3af',
                textAlign: 'center',
              }}
            >
              No organizations yet
            </div>
          )}

          {/* Organization Settings Link - Always show if user has organizations OR is in one */}
          {(organization || (userMemberships?.data && userMemberships.data.length > 0)) && (
            <>
              <div
                style={{
                  height: '1px',
                  background: '#2a2d35',
                  margin: '4px 0',
                }}
              />
              <button
                onClick={() => {
                  setShowDropdown(false);
                  navigate('/settings/organization');
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  width: '100%',
                  padding: '6px 8px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#ffffff',
                  textAlign: 'left',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#252830';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <Settings size={14} style={{ color: '#9ca3af', flexShrink: 0 }} />
                <span>{organization ? 'Organization Settings' : 'Manage Organizations'}</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default OrganizationSwitcher;
