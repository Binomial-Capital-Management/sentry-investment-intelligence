import { useState } from 'react';
import { Plus, X, Mail } from 'lucide-react';

interface TeamInvitationFormProps {
  onComplete: (invites: Array<{ email: string; role: string }>) => void;
  onSkip: () => void;
  organizationName: string;
}

const TeamInvitationForm = ({ onComplete, onSkip, organizationName }: TeamInvitationFormProps) => {
  const [invites, setInvites] = useState<Array<{ email: string; role: string }>>([
    { email: '', role: 'org:member' },
  ]);
  const [errors, setErrors] = useState<{ [key: number]: string }>({});

  const validateEmail = (email: string): boolean => {
    if (!email) return true; // Empty is ok, user can skip
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleEmailChange = (index: number, value: string) => {
    const newInvites = [...invites];
    newInvites[index].email = value;
    setInvites(newInvites);

    // Clear error if email becomes valid
    if (validateEmail(value)) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  const handleRoleChange = (index: number, value: string) => {
    const newInvites = [...invites];
    newInvites[index].role = value;
    setInvites(newInvites);
  };

  const addInvite = () => {
    setInvites([...invites, { email: '', role: 'org:member' }]);
  };

  const removeInvite = (index: number) => {
    if (invites.length === 1) {
      // Keep at least one empty field
      setInvites([{ email: '', role: 'org:member' }]);
    } else {
      setInvites(invites.filter((_, i) => i !== index));
    }
    // Clear error for removed field
    const newErrors = { ...errors };
    delete newErrors[index];
    setErrors(newErrors);
  };

  const handleContinue = () => {
    // Validate all emails
    const newErrors: { [key: number]: string } = {};
    invites.forEach((invite, index) => {
      if (invite.email && !validateEmail(invite.email)) {
        newErrors[index] = 'Invalid email format';
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Filter out empty emails
    const validInvites = invites.filter(inv => inv.email.trim());
    onComplete(validInvites);
  };

  const handleSkip = () => {
    onSkip();
  };

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
        Invite your team
      </h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14 }}>
        Invite colleagues to join <strong>{organizationName}</strong>. You can skip this step and invite them later.
      </p>

      {/* Invites List */}
      <div style={{ marginBottom: 16 }}>
        {invites.map((invite, index) => (
          <div key={index} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              {/* Email Input */}
              <div style={{ flex: 1 }}>
                <input
                  type="email"
                  value={invite.email}
                  onChange={(e) => handleEmailChange(index, e.target.value)}
                  className="input"
                  placeholder="colleague@company.com"
                  style={{
                    borderRadius: 10,
                    width: '100%',
                    borderColor: errors[index] ? '#EF4444' : undefined,
                  }}
                />
                {errors[index] && (
                  <p style={{ color: '#EF4444', fontSize: '0.875rem', marginTop: '0.25rem', fontWeight: 500 }}>
                    {errors[index]}
                  </p>
                )}
              </div>

              {/* Role Dropdown */}
              <select
                value={invite.role}
                onChange={(e) => handleRoleChange(index, e.target.value)}
                className="input"
                style={{
                  borderRadius: 10,
                  width: '140px',
                  padding: '10px 12px',
                  cursor: 'pointer',
                }}
              >
                <option value="org:member">Member</option>
                <option value="org:admin">Admin</option>
              </select>

              {/* Remove Button */}
              <button
                type="button"
                onClick={() => removeInvite(index)}
                style={{
                  padding: '10px',
                  border: '1px solid var(--border)',
                  borderRadius: 10,
                  background: 'var(--bg-base)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minWidth: '40px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#FEF2F2';
                  e.currentTarget.style.borderColor = '#FCA5A5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--bg-base)';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
              >
                <X size={16} style={{ color: '#EF4444' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Another Button */}
      {invites.length < 10 && (
        <button
          type="button"
          onClick={addInvite}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 12px',
            border: '1px dashed var(--border)',
            borderRadius: 10,
            background: 'transparent',
            cursor: 'pointer',
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginBottom: 24,
            width: '100%',
            justifyContent: 'center',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--bg-surface)';
            e.currentTarget.style.borderColor = 'var(--accent)';
            e.currentTarget.style.color = 'var(--accent)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = 'var(--border)';
            e.currentTarget.style.color = 'var(--text-secondary)';
          }}
        >
          <Plus size={16} />
          Add another team member
        </button>
      )}

      {/* Info Box */}
      <div style={{
        padding: 12,
        background: '#F0F9FF',
        border: '1px solid #BAE6FD',
        borderRadius: 6,
        marginBottom: 24,
        display: 'flex',
        gap: 10,
        alignItems: 'flex-start',
      }}>
        <Mail size={16} style={{ color: '#0284C7', flexShrink: 0, marginTop: 2 }} />
        <div style={{ fontSize: 13, color: '#075985', lineHeight: '1.5' }}>
          Invitations will be sent after you complete account setup. Team members will receive an email to join the organization.
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 12 }}>
        <button
          type="button"
          onClick={handleSkip}
          style={{
            flex: 1,
            padding: '10px 20px',
            fontSize: 14,
            fontWeight: 500,
            color: 'var(--text-secondary)',
            background: 'transparent',
            border: '1px solid var(--border)',
            borderRadius: 9999,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-surface)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          Skip for now
        </button>
        <button
          type="button"
          onClick={handleContinue}
          className="btn btn-primary"
          style={{
            flex: 1,
            borderRadius: 9999,
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          Continue to account setup
        </button>
      </div>
    </div>
  );
};

export default TeamInvitationForm;
