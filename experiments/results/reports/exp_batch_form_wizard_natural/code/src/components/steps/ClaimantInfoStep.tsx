import { useForm } from '../../context/FormContext';
import { TextInput } from '../shared/TextInput';
import { DateInput } from '../shared/DateInput';

export function ClaimantInfoStep() {
  const { state, setField } = useForm();
  const { data, validationErrors } = state;

  const getError = (field: string) =>
    validationErrors.find((e) => e.field === `claimant.${field}`)?.message;

  return (
    <fieldset className="step-content">
      <legend className="step-legend">
        <h2>Your Details</h2>
      </legend>
      <p className="step-description">
        Please provide your personal information as it appears on your policy.
      </p>

      <div className="form-row">
        <TextInput
          label="First Name"
          value={data.claimant.firstName}
          onChange={(v) => setField('claimant.firstName', v)}
          required
          error={getError('firstName')}
          autoComplete="given-name"
        />
        <TextInput
          label="Last Name"
          value={data.claimant.lastName}
          onChange={(v) => setField('claimant.lastName', v)}
          required
          error={getError('lastName')}
          autoComplete="family-name"
        />
      </div>

      <div className="form-row">
        <TextInput
          label="Email"
          value={data.claimant.email}
          onChange={(v) => setField('claimant.email', v)}
          type="email"
          required
          error={getError('email')}
          autoComplete="email"
        />
        <TextInput
          label="Phone"
          value={data.claimant.phone}
          onChange={(v) => setField('claimant.phone', v)}
          type="tel"
          error={getError('phone')}
          autoComplete="tel"
          hint="Optional, but recommended"
        />
      </div>

      <DateInput
        label="Date of Birth"
        value={data.claimant.dateOfBirth}
        onChange={(v) => setField('claimant.dateOfBirth', v)}
        error={getError('dateOfBirth')}
        hint="Optional. Must match what's on your policy."
      />

      <TextInput
        label="Address"
        value={data.claimant.address}
        onChange={(v) => setField('claimant.address', v)}
        autoComplete="street-address"
        placeholder="123 Main St"
      />
      <TextInput
        label="City"
        value={data.claimant.city}
        onChange={(v) => setField('claimant.city', v)}
        autoComplete="address-level2"
      />
      <TextInput
        label="Postal Code"
        value={data.claimant.postalCode}
        onChange={(v) => setField('claimant.postalCode', v)}
        autoComplete="postal-code"
      />
    </fieldset>
  );
}
