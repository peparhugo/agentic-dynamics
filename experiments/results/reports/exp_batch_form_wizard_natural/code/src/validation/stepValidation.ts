import { isValidEmail, isValidPhone, isNotEmpty, isValidDate, isDateInPast } from '../validation';
import type { FormData, ValidationError, StepId, DamageAssessment } from '../types';

export function validateStep(step: StepId, data: FormData): ValidationError[] {
  const errors: ValidationError[] = [];

  switch (step) {
    case 'welcome':
      if (!isNotEmpty(data.policyNumber)) {
        errors.push({ field: 'policyNumber', message: 'Policy number is required' });
      } else if (!/^[A-Za-z0-9]{6,20}$/.test(data.policyNumber)) {
        errors.push({ field: 'policyNumber', message: 'Policy number must be 6-20 alphanumeric characters' });
      }
      break;

    case 'claimant':
      if (!isNotEmpty(data.claimant.firstName)) {
        errors.push({ field: 'claimant.firstName', message: 'First name is required' });
      }
      if (!isNotEmpty(data.claimant.lastName)) {
        errors.push({ field: 'claimant.lastName', message: 'Last name is required' });
      }
      if (!isNotEmpty(data.claimant.email)) {
        errors.push({ field: 'claimant.email', message: 'Email is required' });
      } else if (!isValidEmail(data.claimant.email)) {
        errors.push({ field: 'claimant.email', message: 'Email format is invalid' });
      }
      if (isNotEmpty(data.claimant.phone) && !isValidPhone(data.claimant.phone)) {
        errors.push({ field: 'claimant.phone', message: 'Phone format is invalid' });
      }
      if (isNotEmpty(data.claimant.dateOfBirth) && !isValidDate(data.claimant.dateOfBirth)) {
        errors.push({ field: 'claimant.dateOfBirth', message: 'Date of birth is invalid' });
      }
      break;

    case 'incident':
      if (!isNotEmpty(data.incident.incidentDate)) {
        errors.push({ field: 'incident.incidentDate', message: 'Incident date is required' });
      } else if (!isValidDate(data.incident.incidentDate)) {
        errors.push({ field: 'incident.incidentDate', message: 'Incident date is invalid' });
      } else if (!isDateInPast(data.incident.incidentDate)) {
        errors.push({ field: 'incident.incidentDate', message: 'Incident date must be in the past' });
      }
      if (!isNotEmpty(data.incident.description)) {
        errors.push({ field: 'incident.description', message: 'Description is required' });
      }
      if (data.incident.policeReportFiled && !isNotEmpty(data.incident.policeReportNumber)) {
        errors.push({ field: 'incident.policeReportNumber', message: 'Police report number is required when filed' });
      }
      break;

    case 'damage': {
      const dmg = data.damage as DamageAssessment | null;
      if (!dmg) {
        errors.push({ field: 'damage', message: 'Damage details are required' });
        break;
      }
      if (data.incident.incidentType === 'auto') {
        const ad = dmg as Record<string, unknown>;
        if (!isNotEmpty(ad.vehicleMake as string)) {
          errors.push({ field: 'damage.vehicleMake', message: 'Vehicle make is required' });
        }
      } else if (data.incident.incidentType === 'property') {
        const pd = dmg as Record<string, unknown>;
        if (!pd.propertyType) {
          errors.push({ field: 'damage.propertyType', message: 'Property type is required' });
        }
      } else if (data.incident.incidentType === 'health') {
        const hi = dmg as Record<string, unknown>;
        if (!isNotEmpty(hi.injuryType as string)) {
          errors.push({ field: 'damage.injuryType', message: 'Injury type is required' });
        }
      }
      break;
    }

    case 'signature':
      if (!data.signature?.dataUrl) {
        errors.push({ field: 'signature', message: 'Signature is required' });
      }
      if (!data.agreedToTerms) {
        errors.push({ field: 'agreedToTerms', message: 'You must agree to the terms' });
      }
      break;
  }

  return errors;
}

export function isStepValid(step: StepId, data: FormData): boolean {
  return validateStep(step, data).length === 0;
}
