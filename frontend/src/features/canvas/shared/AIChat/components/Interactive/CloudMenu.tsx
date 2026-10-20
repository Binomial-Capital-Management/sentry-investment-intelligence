interface CloudMenuProps {
  onGoogleDrive: () => void;
  onOneDrivePersonal: () => void;
  onOneDriveBusiness: () => void;
  onSharePoint: () => void;
}

const menuItemStyle: React.CSSProperties = {
  width: '100%',
  textAlign: 'left',
  padding: '0.375rem 0.625rem',
  fontFamily: 'var(--cc-font-ui)',
  fontSize: '0.688rem',
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  color: 'hsl(var(--cc-text-200))',
  background: 'transparent',
  border: 'none',
  borderRadius: 'var(--cc-radius-lg)',
  cursor: 'pointer',
  transition: 'background-color 0.1s ease',
};

export function CloudMenu({
  onGoogleDrive,
  onOneDrivePersonal,
  onOneDriveBusiness,
  onSharePoint,
}: CloudMenuProps) {
  return (
    <div style={{
      position: 'absolute',
      bottom: '100%',
      left: 0,
      marginBottom: 4,
      width: 200,
      backgroundColor: 'hsl(var(--cc-bg-000))',
      border: '0.5px solid hsl(var(--cc-border-200) / 30%)',
      borderRadius: 'var(--cc-radius-2xl)',
      boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
      zIndex: 50,
      padding: '0.375rem',
    }}>
      <button onClick={onGoogleDrive} className="cc-btn-ghost" style={menuItemStyle}>
        <img src="/connector-logos/google-drive.png" alt="Google Drive" style={{ width: 16, height: 12, objectFit: 'contain' }} />
        <span style={{ fontWeight: 500 }}>Google Drive</span>
      </button>
      <button onClick={onOneDrivePersonal} className="cc-btn-ghost" style={menuItemStyle}>
        <img src="/connector-logos/one-drive.png" alt="OneDrive" style={{ width: 16, height: 12, objectFit: 'contain' }} />
        <span style={{ fontWeight: 500 }}>OneDrive Personal</span>
      </button>
      <button onClick={onOneDriveBusiness} className="cc-btn-ghost" style={menuItemStyle}>
        <img src="/connector-logos/one-drive.png" alt="OneDrive Business" style={{ width: 16, height: 12, objectFit: 'contain' }} />
        <span style={{ fontWeight: 500 }}>OneDrive Business</span>
      </button>
      <button onClick={onSharePoint} className="cc-btn-ghost" style={menuItemStyle}>
        <img src="/connector-logos/sharepoint-logo.png" alt="SharePoint" style={{ width: 16, height: 12, objectFit: 'contain' }} />
        <span style={{ fontWeight: 500 }}>SharePoint</span>
      </button>
    </div>
  );
}
