import { useForm } from '../../context/FormContext';
import { TextInput } from '../shared/TextInput';
import { SelectInput } from '../shared/SelectInput';
import { CheckboxInput } from '../shared/CheckboxInput';
import { DateInput } from '../shared/DateInput';
import type { AutoDamage, PropertyDamage, HealthInjury } from '../../types';

const PROPERTY_TYPES = [
  { value: 'residential', label: 'Residential' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'other', label: 'Other' },
];

const DAMAGED_AREA_OPTIONS = [
  { value: 'roof', label: 'Roof' },
  { value: 'walls', label: 'Walls' },
  { value: 'floor', label: 'Floor / Foundation' },
  { value: 'windows', label: 'Windows' },
  { value: 'plumbing', label: 'Plumbing' },
  { value: 'electrical', label: 'Electrical' },
  { value: 'other', label: 'Other' },
];

const BODY_PARTS = [
  { value: 'head', label: 'Head' },
  { value: 'neck', label: 'Neck' },
  { value: 'back', label: 'Back / Spine' },
  { value: 'shoulder', label: 'Shoulder' },
  { value: 'arm', label: 'Arm / Elbow' },
  { value: 'wrist', label: 'Wrist / Hand' },
  { value: 'leg', label: 'Leg / Knee' },
  { value: 'ankle', label: 'Ankle / Foot' },
  { value: 'other', label: 'Other' },
];

const DEFAULT_AUTO_DAMAGE: AutoDamage = {
  vehicleMake: '',
  vehicleModel: '',
  vehicleYear: '',
  licensePlate: '',
  damageDescription: '',
  otherVehicleInvolved: false,
  otherDriverInfo: '',
};

const DEFAULT_PROPERTY_DAMAGE: PropertyDamage = {
  propertyType: 'residential',
  damagedAreas: [],
  estimatedLoss: '',
  occupantsPresent: false,
};

const DEFAULT_HEALTH_INJURY: HealthInjury = {
  injuryType: '',
  bodyParts: [],
  medicalAttention: false,
  facilityName: '',
  treatmentDate: '',
  ongoingTreatment: false,
};

export function DamageAssessmentStep() {
  const { state, setField } = useForm();
  const { data, validationErrors } = state;
  const incidentType = data.incident.incidentType;

  const getError = (field: string) =>
    validationErrors.find((e) => e.field === `damage.${field}`)?.message;

  const renderAutoDamage = () => {
    const dmg = (data.damage as AutoDamage) || DEFAULT_AUTO_DAMAGE;
    return (
      <>
        <div className="form-row">
          <TextInput
            label="Vehicle Make"
            value={dmg.vehicleMake}
            onChange={(v) => setField('damage.vehicleMake', v)}
            required
            error={getError('vehicleMake')}
            placeholder="e.g. Toyota"
          />
          <TextInput
            label="Vehicle Model"
            value={dmg.vehicleModel}
            onChange={(v) => setField('damage.vehicleModel', v)}
            placeholder="e.g. Camry"
          />
        </div>
        <div className="form-row">
          <TextInput
            label="Vehicle Year"
            value={dmg.vehicleYear}
            onChange={(v) => setField('damage.vehicleYear', v)}
            placeholder="e.g. 2020"
          />
          <TextInput
            label="License Plate"
            value={dmg.licensePlate}
            onChange={(v) => setField('damage.licensePlate', v)}
            placeholder="ABC-1234"
          />
        </div>
        <TextInput
          label="Damage Description"
          value={dmg.damageDescription}
          onChange={(v) => setField('damage.damageDescription', v)}
          placeholder="Describe the vehicle damage"
        />
        <CheckboxInput
          label="Was another vehicle involved?"
          checked={dmg.otherVehicleInvolved}
          onChange={(v) => setField('damage.otherVehicleInvolved', v)}
        />
        {dmg.otherVehicleInvolved && (
          <TextInput
            label="Other Driver Information"
            value={dmg.otherDriverInfo}
            onChange={(v) => setField('damage.otherDriverInfo', v)}
            placeholder="Name, contact, and insurance info"
          />
        )}
      </>
    );
  };

  const renderPropertyDamage = () => {
    const dmg = (data.damage as PropertyDamage) || DEFAULT_PROPERTY_DAMAGE;
    return (
      <>
        <SelectInput
          label="Property Type"
          value={dmg.propertyType}
          onChange={(v) => setField('damage.propertyType', v)}
          options={PROPERTY_TYPES}
          required
          error={getError('propertyType')}
        />
        <fieldset className="checklist-fieldset">
          <legend>Damaged Areas (select all that apply)</legend>
          {DAMAGED_AREA_OPTIONS.map((opt) => (
            <CheckboxInput
              key={opt.value}
              label={opt.label}
              checked={dmg.damagedAreas?.includes(opt.value) || false}
              onChange={(checked) => {
                const areas = checked
                  ? [...(dmg.damagedAreas || []), opt.value]
                  : (dmg.damagedAreas || []).filter((a) => a !== opt.value);
                setField('damage.damagedAreas', areas);
              }}
            />
          ))}
        </fieldset>
        <TextInput
          label="Estimated Loss ($)"
          value={dmg.estimatedLoss}
          onChange={(v) => setField('damage.estimatedLoss', v)}
          type="number"
          placeholder="e.g. 5000"
        />
        <CheckboxInput
          label="Were occupants present during the incident?"
          checked={dmg.occupantsPresent}
          onChange={(v) => setField('damage.occupantsPresent', v)}
        />
      </>
    );
  };

  const renderHealthInjury = () => {
    const dmg = (data.damage as HealthInjury) || DEFAULT_HEALTH_INJURY;
    return (
      <>
        <TextInput
          label="Injury Type"
          value={dmg.injuryType}
          onChange={(v) => setField('damage.injuryType', v)}
          required
          error={getError('injuryType')}
          placeholder="e.g. Fracture, Burn, Sprain"
        />
        <fieldset className="checklist-fieldset">
          <legend>Affected Body Parts (select all that apply)</legend>
          {BODY_PARTS.map((opt) => (
            <CheckboxInput
              key={opt.value}
              label={opt.label}
              checked={dmg.bodyParts?.includes(opt.value) || false}
              onChange={(checked) => {
                const parts = checked
                  ? [...(dmg.bodyParts || []), opt.value]
                  : (dmg.bodyParts || []).filter((p) => p !== opt.value);
                setField('damage.bodyParts', parts);
              }}
            />
          ))}
        </fieldset>
        <CheckboxInput
          label="Did you seek medical attention?"
          checked={dmg.medicalAttention}
          onChange={(v) => setField('damage.medicalAttention', v)}
        />
        {dmg.medicalAttention && (
          <>
            <TextInput
              label="Medical Facility Name"
              value={dmg.facilityName}
              onChange={(v) => setField('damage.facilityName', v)}
              placeholder="Hospital or clinic name"
            />
            <DateInput
              label="Treatment Date"
              value={dmg.treatmentDate}
              onChange={(v) => setField('damage.treatmentDate', v)}
              max={new Date().toISOString().split('T')[0]}
            />
            <CheckboxInput
              label="Is ongoing treatment required?"
              checked={dmg.ongoingTreatment}
              onChange={(v) => setField('damage.ongoingTreatment', v)}
            />
          </>
        )}
      </>
    );
  };

  return (
    <fieldset className="step-content">
      <legend className="step-legend">
        <h2>Damage Assessment</h2>
      </legend>
      <p className="step-description">
        Provide details about the {incidentType === 'auto' ? 'vehicle' : incidentType === 'property' ? 'property' : incidentType === 'health' ? 'injury' : 'incident'}.
      </p>

      {incidentType === 'auto' && renderAutoDamage()}
      {incidentType === 'property' && renderPropertyDamage()}
      {incidentType === 'health' && renderHealthInjury()}
      {incidentType === 'other' && (
        <TextInput
          label="Describe the loss or damage"
          value={(data.damage as Record<string, unknown>)?.description as string || ''}
          onChange={(v) => setField('damage', { ...(data.damage as Record<string, unknown> || {}), description: v })}
          placeholder="Describe what was damaged or lost"
        />
      )}
    </fieldset>
  );
}
