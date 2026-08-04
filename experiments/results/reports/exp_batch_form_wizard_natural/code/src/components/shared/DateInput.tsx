import { useId } from 'react';

interface DateInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  error?: string;
  hint?: string;
  disabled?: boolean;
  min?: string;
  max?: string;
}

export function DateInput({
  label,
  value,
  onChange,
  required = false,
  error,
  hint,
  disabled = false,
  min,
  max,
}: DateInputProps) {
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
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`form-input${error ? ' form-input--error' : ''}`}
        required={required}
        aria-required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${errorId}${hint ? ` ${hintId}` : ''}` : hint ? hintId : undefined}
        disabled={disabled}
        min={min}
        max={max}
      />
      {error && (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
