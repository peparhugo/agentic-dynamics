import { useId } from 'react';

interface TextInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'email' | 'tel' | 'number' | 'password';
  required?: boolean;
  error?: string;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
  autoComplete?: string;
  maxLength?: number;
}

export function TextInput({
  label,
  value,
  onChange,
  type = 'text',
  required = false,
  error,
  placeholder,
  hint,
  disabled = false,
  autoComplete,
  maxLength,
}: TextInputProps) {
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
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`form-input${error ? ' form-input--error' : ''}`}
        required={required}
        aria-required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${errorId}${hint ? ` ${hintId}` : ''}` : hint ? hintId : undefined}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete={autoComplete}
        maxLength={maxLength}
      />
      {error && (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
