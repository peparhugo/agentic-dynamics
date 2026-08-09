import { useId } from 'react';

interface CheckboxInputProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  error?: string;
  disabled?: boolean;
  hint?: string;
}

export function CheckboxInput({
  label,
  checked,
  onChange,
  error,
  disabled = false,
  hint,
}: CheckboxInputProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <div className="form-field form-field--checkbox" role="group">
      <div className="checkbox-wrapper">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className={`form-checkbox${error ? ' form-checkbox--error' : ''}`}
          aria-invalid={!!error}
          aria-describedby={error ? `${errorId}${hint ? ` ${hintId}` : ''}` : hint ? hintId : undefined}
          disabled={disabled}
        />
        <label htmlFor={id} className="form-label form-label--checkbox">
          {label}
        </label>
      </div>
      {hint && (
        <p id={hintId} className="form-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
