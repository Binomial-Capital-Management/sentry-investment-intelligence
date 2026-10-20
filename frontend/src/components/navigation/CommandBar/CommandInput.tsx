import React from 'react';

interface CommandInputProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

const CommandInput: React.FC<CommandInputProps> = ({ value, onChange, placeholder }) => {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder || 'Ask Sentry (/, #, @ for power commands)'}
      className="flex-1 bg-transparent outline-none text-sm"
      style={{ color: 'var(--text-primary)' }}
      aria-label="Command input"
    />
  );
};

export default CommandInput;
