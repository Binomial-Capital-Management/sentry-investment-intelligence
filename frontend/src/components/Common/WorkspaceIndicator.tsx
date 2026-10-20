import { useOrganization, useUser } from '@clerk/clerk-react';
import { Building2, User } from 'lucide-react';

interface WorkspaceIndicatorProps {
  size?: 'sm' | 'md';
}

/**
 * WorkspaceIndicator component
 * Shows which workspace (personal or organization) the user is currently in
 */
const WorkspaceIndicator = ({ size = 'sm' }: WorkspaceIndicatorProps) => {
  const { organization } = useOrganization();
  const { user } = useUser();

  const isOrganization = !!organization;
  const workspaceName = organization?.name || 'Personal';

  const styles = {
    sm: {
      fontSize: '11px',
      padding: '3px 8px',
      iconSize: 12,
      gap: '4px',
    },
    md: {
      fontSize: '12px',
      padding: '4px 10px',
      iconSize: 14,
      gap: '5px',
    },
  };

  const currentStyle = styles[size];

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: currentStyle.gap,
        padding: currentStyle.padding,
        background: isOrganization ? '#F0F6FF' : '#F9FAFB',
        border: `1px solid ${isOrganization ? '#DBEAFE' : '#E5E7EB'}`,
        borderRadius: '6px',
        fontSize: currentStyle.fontSize,
        color: isOrganization ? '#1E40AF' : '#6B7280',
        fontWeight: '500',
        whiteSpace: 'nowrap',
      }}
      title={`Current workspace: ${workspaceName}`}
    >
      {isOrganization ? (
        organization?.imageUrl ? (
          <img
            src={organization.imageUrl}
            alt={organization.name}
            style={{
              width: `${currentStyle.iconSize}px`,
              height: `${currentStyle.iconSize}px`,
              borderRadius: '3px',
              objectFit: 'cover',
              border: '1px solid #DBEAFE',
              flexShrink: 0,
            }}
          />
        ) : (
          <Building2 size={currentStyle.iconSize} style={{ color: '#2563EB', flexShrink: 0 }} />
        )
      ) : (
        user?.imageUrl ? (
          <img
            src={user.imageUrl}
            alt={user.fullName || 'User'}
            style={{
              width: `${currentStyle.iconSize}px`,
              height: `${currentStyle.iconSize}px`,
              borderRadius: '50%',
              objectFit: 'cover',
              border: '1px solid #E5E7EB',
              flexShrink: 0,
            }}
          />
        ) : (
          <User size={currentStyle.iconSize} style={{ color: '#6B7280', flexShrink: 0 }} />
        )
      )}
      <span>{workspaceName}</span>
    </div>
  );
};

export default WorkspaceIndicator;
