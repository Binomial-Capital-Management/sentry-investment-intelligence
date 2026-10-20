import { ReactNode } from 'react';

interface SettingRowProps {
  label: string;
  description: string;
  control: ReactNode;
}

const SettingRow = ({ label, description, control }: SettingRowProps) => {
  return (
    <div className="flex items-center justify-between">
      <div>
        <label className="text-sm font-medium">{label}</label>
        <p className="text-sm text-gray-600 mt-0.5">{description}</p>
      </div>
      {control}
    </div>
  );
};

export default SettingRow;
