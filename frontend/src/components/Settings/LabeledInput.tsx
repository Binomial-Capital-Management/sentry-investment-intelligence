interface LabeledInputProps {
  label: string;
  type?: string;
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  placeholder?: string;
}

const LabeledInput = ({
  label,
  type = 'text',
  value,
  onChange,
  readOnly = false,
  placeholder,
}: LabeledInputProps) => {
  return (
    <div>
      <label className="text-sm text-gray-600 block mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        readOnly={readOnly}
        placeholder={placeholder}
        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded bg-white h-8 focus:border-blue-500 focus:outline-none"
      />
    </div>
  );
};

export default LabeledInput;
