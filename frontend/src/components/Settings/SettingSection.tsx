import { ReactNode } from 'react';

interface SettingSectionProps {
  title: string;
  children: ReactNode;
}

const SettingSection = ({ title, children }: SettingSectionProps) => {
  return (
    <div className="bg-white border border-gray-200 rounded-md shadow-sm mb-4 overflow-hidden">
      <div className="bg-gray-100 px-4 py-3 border-b border-gray-200">
        <span className="text-sm font-medium text-gray-900">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
};

export default SettingSection;
