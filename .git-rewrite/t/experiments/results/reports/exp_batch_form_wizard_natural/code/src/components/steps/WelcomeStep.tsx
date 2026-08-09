import { useForm } from '../../context/FormContext';
import { TextInput } from '../shared/TextInput';
import { ScreenReaderOnly } from '../accessibility/ScreenReaderOnly';

export function WelcomeStep() {
  const { state, setField } = useForm();
  const { data, validationErrors } = state;

  const error = validationErrors.find((e) => e.field === 'policyNumber')?.message;

  return (
    <fieldset className="step-content">
      <legend className="step-legend">
        <h2>Welcome to Insurance Claims</h2>
      </legend>
      <p className="step-description">
        Enter your policy number to get started with your claim.
      </p>

      <TextInput
        label="Policy Number"
        value={data.policyNumber}
        onChange={(v) => setField('policyNumber', v)}
        required
        error={error}
        placeholder="e.g. POL123456"
        hint="Your policy number can be found on your insurance card or welcome letter."
        autoComplete="off"
        maxLength={20}
      />

      <ScreenReaderOnly>
        <p>Press Tab to navigate to the Next button after entering your policy number.</p>
      </ScreenReaderOnly>
    </fieldset>
  );
}
