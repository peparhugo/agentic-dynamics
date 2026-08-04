import { useForm } from '../../context/FormContext';
import { TextInput } from '../shared/TextInput';
import { DateInput } from '../shared/DateInput';
import { SelectInput } from '../shared/SelectInput';
import { CheckboxInput } from '../shared/CheckboxInput';

const INCIDENT_TYPES = [
  { value: 'auto', label: 'Auto Accident' },
  { value: 'property', label: 'Property Damage' },
  { value: 'health', label: 'Health / Injury' },
  { value: 'other', label: 'Other' },
];

export function IncidentDetailsStep() {
  const { state, setField } = useForm();
  const { data, validationErrors } = state;

  const getError = (field: string) =>
    validationErrors.find((e) => e.field === `incident.${field}`)?.message;

  return (
    <fieldset className="step-content">
      <legend className="step-legend">
        <h2>Incident Details</h2>
      </legend>
      <p className="step-description">
        Tell us what happened. Provide as much detail as possible.
      </p>

      <SelectInput
        label="Incident Type"
        value={data.incident.incidentType}
        onChange={(v) => setField('incident.incidentType', v)}
        options={INCIDENT_TYPES}
        required
      />

      <div className="form-row">
        <DateInput
          label="Incident Date"
          value={data.incident.incidentDate}
          onChange={(v) => setField('incident.incidentDate', v)}
          required
          error={getError('incidentDate')}
          max={new Date().toISOString().split('T')[0]}
        />
        <TextInput
          label="Incident Time (approx)"
          value={data.incident.incidentTime}
          onChange={(v) => setField('incident.incidentTime', v)}
          placeholder="e.g. 14:30"
        />
      </div>

      <TextInput
        label="Location"
        value={data.incident.location}
        onChange={(v) => setField('incident.location', v)}
        placeholder="Address or intersection"
        autoComplete="street-address"
      />

      <TextInput
        label="Description"
        value={data.incident.description}
        onChange={(v) => setField('incident.description', v)}
        required
        error={getError('description')}
        placeholder="Describe what happened in detail"
      />

      <CheckboxInput
        label="Was a police report filed?"
        checked={data.incident.policeReportFiled}
        onChange={(v) => setField('incident.policeReportFiled', v)}
      />

      {data.incident.policeReportFiled && (
        <TextInput
          label="Police Report Number"
          value={data.incident.policeReportNumber}
          onChange={(v) => setField('incident.policeReportNumber', v)}
          required
          error={getError('policeReportNumber')}
          placeholder="e.g. PR-2024-001234"
        />
      )}
    </fieldset>
  );
}
