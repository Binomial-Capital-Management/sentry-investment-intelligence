import { LucideIcon } from 'lucide-react';

interface TabButtonProps {
  icon: LucideIcon;
  label: string;
  active: boolean;
  onClick: () => void;
}

const TabButton = ({ icon: Icon, label, active, onClick }: TabButtonProps) => {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-3 text-sm transition-colors ${
        active ? 'bg-gray-50 border-l-3 border-blue-600 font-semibold' : 'border-l-3 border-transparent font-normal'
      }`}
    >
      <Icon size={14} className="text-gray-600" />
      <span>{label}</span>
    </button>
  );
};

export default TabButton;
