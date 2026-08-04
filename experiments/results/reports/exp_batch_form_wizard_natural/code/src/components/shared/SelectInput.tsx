import { useId } from 'react';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  required?: boolean;
  error?: string;
  hint?: string;
  disabled?: boolean;
  placeholder?: string;
}

export function SelectInput({
  label,
  value,
  onChange,
  options,
  required = false,
  error,
  hint,
  disabled = false,
  placeholder,
}: SelectInputProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <div className="form-field" role="group">
      <label htmlFor={id} className="form-label">
        {label}
        {required && <span className="required-asterisk" aria-hidden="true"> *</span>}
      </label>
      {hint && (
        <p id={hintId} className="form-hint">
          {hint}
        </p>
      )}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`form-select${error ? ' form-select--error' : ''}`}
        required={required}
        aria-required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${errorId}${hint ? ` ${hintId}` : ''}` : hint ? hintId : undefined}
        disabled={disabled}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
