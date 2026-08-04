export interface ClaimantInfo {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  dateOfBirth: string;
  address: string;
  city: string;
  postalCode: string;
}

export interface IncidentDetails {
  incidentDate: string;
  incidentTime: string;
  incidentType: 'auto' | 'property' | 'health' | 'other';
  description: string;
  location: string;
  policeReportFiled: boolean;
  policeReportNumber: string;
}

export interface AutoDamage {
  vehicleMake: string;
  vehicleModel: string;
  vehicleYear: string;
  licensePlate: string;
  damageDescription: string;
  otherVehicleInvolved: boolean;
  otherDriverInfo: string;
}

export interface PropertyDamage {
  propertyType: 'residential' | 'commercial' | 'other';
  damagedAreas: string[];
  estimatedLoss: string;
  occupantsPresent: boolean;
}

export interface HealthInjury {
  injuryType: string;
  bodyParts: string[];
  medicalAttention: boolean;
  facilityName: string;
  treatmentDate: string;
  ongoingTreatment: boolean;
}

export type DamageAssessment = AutoDamage | PropertyDamage | HealthInjury;

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  dataUrl: string;
}

export interface WitnessInfo {
  name: string;
  phone: string;
  email: string;
  relationship: string;
}

export interface SignatureData {
  dataUrl: string;
  signedAt: string;
}

export interface FormData {
  policyNumber: string;
  claimant: ClaimantInfo;
  incident: IncidentDetails;
  damage: DamageAssessment | null;
  documents: UploadedFile[];
  witnesses: WitnessInfo[];
  hasWitnesses: boolean;
  signature: SignatureData | null;
  agreedToTerms: boolean;
}

export type StepId =
  | 'welcome'
  | 'claimant'
  | 'incident'
  | 'damage'
  | 'documents'
  | 'witnesses'
  | 'review'
  | 'signature'
  | 'confirmation';

export interface StepConfig {
  id: StepId;
  title: string;
  description: string;
}

export interface ValidationError {
  field: string;
  message: string;
}

export interface FormState {
  data: FormData;
  currentStep: StepId;
  visitedSteps: Set<StepId>;
  validationErrors: ValidationError[];
  isSubmitting: boolean;
  submitSuccess: boolean;
}

export const DEFAULT_FORM_DATA: FormData = {
  policyNumber: '',
  claimant: {
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    dateOfBirth: '',
    address: '',
    city: '',
    postalCode: '',
  },
  incident: {
    incidentDate: '',
    incidentTime: '',
    incidentType: 'auto',
    description: '',
    location: '',
    policeReportFiled: false,
    policeReportNumber: '',
  },
  damage: null,
  documents: [],
  witnesses: [],
  hasWitnesses: false,
  signature: null,
  agreedToTerms: false,
};

export const STEPS: StepConfig[] = [
  { id: 'welcome', title: 'Get Started', description: 'Policy lookup' },
  { id: 'claimant', title: 'Your Details', description: 'Claimant information' },
  { id: 'incident', title: 'Incident', description: 'What happened' },
  { id: 'damage', title: 'Assessment', description: 'Damage details' },
  { id: 'documents', title: 'Documents', description: 'Supporting files' },
  { id: 'witnesses', title: 'Witnesses', description: 'Witness information' },
  { id: 'review', title: 'Review', description: 'Verify details' },
  { id: 'signature', title: 'Sign', description: 'Declaration' },
  { id: 'confirmation', title: 'Done', description: 'Submitted' },
];

export type FormAction =
  | { type: 'SET_FIELD'; path: string; value: unknown }
  | { type: 'SET_STEP_DATA'; step: StepId; data: Partial<FormData> }
  | { type: 'GO_TO_STEP'; step: StepId }
  | { type: 'NEXT_STEP'; availableSteps: StepId[] }
  | { type: 'PREV_STEP'; availableSteps: StepId[] }
  | { type: 'SET_VALIDATION_ERRORS'; errors: ValidationError[] }
  | { type: 'CLEAR_VALIDATION_ERRORS' }
  | { type: 'ADD_FILE'; file: UploadedFile }
  | { type: 'REMOVE_FILE'; fileId: string }
  | { type: 'ADD_WITNESS'; witness: WitnessInfo }
  | { type: 'REMOVE_WITNESS'; index: number }
  | { type: 'SET_SIGNATURE'; signature: SignatureData }
  | { type: 'SET_SUBMITTING'; isSubmitting: boolean }
  | { type: 'SET_SUBMIT_SUCCESS'; success: boolean }
  | { type: 'RESTORE_STATE'; state: FormState }
  | { type: 'RESET' }
  | { type: 'BATCH'; actions: FormAction[] };
