// removed unused clsx import

interface NavItemProps {
  title: string;
  active?: boolean;
  isActive?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}

const NavItem = ({ title, active = false, isActive = false, onClick, children }: NavItemProps) => {
  const isCurrentlyActive = active || isActive;

  return (
    <button
      className="w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-200 hover:scale-[1.02]"
      title={title}
      aria-label={title}
      onClick={onClick}
      style={{
        background: isCurrentlyActive ? 'var(--accent-subtle)' : 'transparent',
        color: isCurrentlyActive ? 'var(--accent)' : 'var(--text-secondary)',
      }}
      onMouseEnter={(e) => {
        if (!isCurrentlyActive) {
          e.currentTarget.style.background = 'var(--bg-hover)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isCurrentlyActive) {
          e.currentTarget.style.background = 'transparent';
        }
      }}
    >
      {children}
    </button>
  );
};

export default NavItem;
