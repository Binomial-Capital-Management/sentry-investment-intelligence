interface NavSectionProps {
  children: React.ReactNode;
}

const NavSection = ({ children }: NavSectionProps) => (
  <div className="flex flex-col gap-2">
    {children}
  </div>
);

export default NavSection;
