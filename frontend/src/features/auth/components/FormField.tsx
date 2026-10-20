/**
 * Reusable form field component with label and error display
 */

import { forwardRef } from 'react';

interface FormFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  touched?: boolean;
}

export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(
  ({ label, error, touched, id, className = '', ...props }, ref) => {
    const fieldId = id || label.toLowerCase().replace(/\s+/g, '-');
    const hasError = error && touched;
    
    return (
      <div className="mb-3">
        <label 
          htmlFor={fieldId}
          className="block text-sm mb-1.5 text-[var(--text-secondary)] font-medium"
        >
          {label}
        </label>
        <input
          ref={ref}
          id={fieldId}
          className={`
            input w-full rounded-[10px]
            ${hasError ? 'border-red-500' : ''}
            ${className}
          `}
          aria-invalid={hasError}
          aria-describedby={hasError ? `${fieldId}-error` : undefined}
          {...props}
        />
        {hasError && (
          <p
            id={`${fieldId}-error`}
            className="text-red-500 text-sm mt-1 font-medium"
          >
            {error}
          </p>
        )}
      </div>
    );
  }
);

FormField.displayName = 'FormField';

export default FormField;
