import { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react';
import type {
  FormState,
  FormAction,
  FormData,
  StepId,
  ValidationError,
  UploadedFile,
  WitnessInfo,
  SignatureData,
} from '../types';
import { DEFAULT_FORM_DATA, STEPS } from '../types';
import { validateStep } from '../validation/stepValidation';
import { deepSet } from '../utils/object';
import {
  saveDraft,
  loadDraft,
  clearDraft,
  saveVisitedSteps,
  loadVisitedSteps,
  saveUndoHistory,
  loadUndoHistory,
  saveRedoHistory,
  loadRedoHistory,
  clearHistories,
} from '../utils/storage';

interface FormContextValue {
  state: FormState;
  dispatch: React.Dispatch<FormAction>;
  goToStep: (step: StepId) => void;
  nextStep: () => void;
  prevStep: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  availableSteps: StepId[];
  currentStepIndex: number;
  setField: (path: string, value: unknown) => void;
  validateCurrentStep: () => ValidationError[];
}

function computeAvailableSteps(data: FormData): StepId[] {
  const steps: StepId[] = [];
  for (const step of STEPS) {
    if (step.id === 'witnesses' && !data.hasWitnesses) continue;
    steps.push(step.id);
  }
  return steps;
}

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case 'SET_FIELD': {
      const newData = deepSet(state.data as unknown as Record<string, unknown>, action.path, action.value) as unknown as FormData;
      return { ...state, data: newData };
    }
    case 'SET_STEP_DATA':
      return {
        ...state,
        data: { ...state.data, ...action.data },
      };
    case 'GO_TO_STEP':
      return {
        ...state,
        currentStep: action.step,
        visitedSteps: new Set([...state.visitedSteps, action.step]),
        validationErrors: [],
      };
    case 'NEXT_STEP': {
      const avail = action.availableSteps;
      const currentIdx = avail.indexOf(state.currentStep);
      const nextIdx = currentIdx + 1;
      if (nextIdx >= avail.length) return state;
      const nextStep = avail[nextIdx];
      return {
        ...state,
        currentStep: nextStep,
        visitedSteps: new Set([...state.visitedSteps, nextStep]),
        validationErrors: [],
      };
    }
    case 'PREV_STEP': {
      const availPrev = action.availableSteps;
      const currentIdxPrev = availPrev.indexOf(state.currentStep);
      const prevIdx = currentIdxPrev - 1;
      if (prevIdx < 0) return state;
      return {
        ...state,
        currentStep: availPrev[prevIdx],
        validationErrors: [],
      };
    }
    case 'SET_VALIDATION_ERRORS':
      return { ...state, validationErrors: action.errors };
    case 'CLEAR_VALIDATION_ERRORS':
      return { ...state, validationErrors: [] };
    case 'ADD_FILE':
      return {
        ...state,
        data: { ...state.data, documents: [...state.data.documents, action.file] },
      };
    case 'REMOVE_FILE':
      return {
        ...state,
        data: {
          ...state.data,
          documents: state.data.documents.filter((f) => f.id !== action.fileId),
        },
      };
    case 'ADD_WITNESS':
      return {
        ...state,
        data: { ...state.data, witnesses: [...state.data.witnesses, action.witness] },
      };
    case 'REMOVE_WITNESS':
      return {
        ...state,
        data: {
          ...state.data,
          witnesses: state.data.witnesses.filter((_, i) => i !== action.index),
        },
      };
    case 'SET_SIGNATURE':
      return { ...state, data: { ...state.data, signature: action.signature } };
    case 'SET_SUBMITTING':
      return { ...state, isSubmitting: action.isSubmitting };
    case 'SET_SUBMIT_SUCCESS':
      return { ...state, submitSuccess: action.success };
    case 'RESTORE_STATE':
      return {
        ...action.state,
        visitedSteps: new Set(action.state.visitedSteps),
        validationErrors: [],
      };
    case 'RESET':
      return {
        data: { ...DEFAULT_FORM_DATA },
        currentStep: 'welcome',
        visitedSteps: new Set(['welcome']),
        validationErrors: [],
        isSubmitting: false,
        submitSuccess: false,
      };
    case 'BATCH':
      return action.actions.reduce((s, a) => formReducer(s, a), state);
    default:
      return state;
  }
}

function createInitialState(): FormState {
  const saved = loadDraft();
  const visited = loadVisitedSteps();
  if (saved?.data) {
    return {
      data: saved.data as FormData,
      currentStep: 'welcome',
      visitedSteps: new Set(visited.length > 0 ? visited : ['welcome']),
      validationErrors: [],
      isSubmitting: false,
      submitSuccess: false,
    };
  }
  return {
    data: { ...DEFAULT_FORM_DATA },
    currentStep: 'welcome',
    visitedSteps: new Set(['welcome']),
    validationErrors: [],
    isSubmitting: false,
    submitSuccess: false,
  };
}

const FormContext = createContext<FormContextValue | null>(null);

export function FormProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(formReducer, undefined, createInitialState);

  const undoStack = useRef<FormState[]>(loadUndoHistory().map((s) => ({
    ...s,
    data: s.data as FormData,
    visitedSteps: new Set((s as unknown as { visitedSteps: string[] }).visitedSteps || []),
    validationErrors: [],
    isSubmitting: false,
    submitSuccess: false,
  })));
  const redoStack = useRef<FormState[]>(loadRedoHistory().map((s) => ({
    ...s,
    data: s.data as FormData,
    visitedSteps: new Set((s as unknown as { visitedSteps: string[] }).visitedSteps || []),
    validationErrors: [],
    isSubmitting: false,
    submitSuccess: false,
  })));

  const pushUndo = useCallback((currentState: FormState) => {
    undoStack.current = [...undoStack.current.slice(-29), { ...currentState, visitedSteps: new Set(currentState.visitedSteps) }];
    redoStack.current = [];
    saveUndoHistory(undoStack.current.map((s) => ({ data: s.data, currentStep: s.currentStep, timestamp: Date.now() })));
    saveRedoHistory([]);
  }, []);

  const canUndo = undoStack.current.length > 0;
  const canRedo = redoStack.current.length > 0;

  const undo = useCallback(() => {
    if (undoStack.current.length === 0) return;
    const prev = undoStack.current.pop()!;
    redoStack.current.push({ ...state, visitedSteps: new Set(state.visitedSteps) });
    dispatch({ type: 'RESTORE_STATE', state: { ...prev, visitedSteps: new Set(prev.visitedSteps) } });
    saveUndoHistory(undoStack.current.map((s) => ({ data: s.data, currentStep: s.currentStep, timestamp: Date.now() })));
    saveRedoHistory(redoStack.current.map((s) => ({ data: s.data, currentStep: s.currentStep, timestamp: Date.now() })));
  }, [state]);

  const redo = useCallback(() => {
    if (redoStack.current.length === 0) return;
    const next = redoStack.current.pop()!;
    undoStack.current.push({ ...state, visitedSteps: new Set(state.visitedSteps) });
    dispatch({ type: 'RESTORE_STATE', state: { ...next, visitedSteps: new Set(next.visitedSteps) } });
    saveUndoHistory(undoStack.current.map((s) => ({ data: s.data, currentStep: s.currentStep, timestamp: Date.now() })));
    saveRedoHistory(redoStack.current.map((s) => ({ data: s.data, currentStep: s.currentStep, timestamp: Date.now() })));
  }, [state]);

  const setField = useCallback((path: string, value: unknown) => {
    pushUndo(state);
    dispatch({ type: 'SET_FIELD', path, value });
  }, [state, pushUndo]);

  const goToStep = useCallback((step: StepId) => {
    pushUndo(state);
    dispatch({ type: 'GO_TO_STEP', step });
  }, [state, pushUndo]);

  const availableSteps = computeAvailableSteps(state.data);
  const currentStepIndex = availableSteps.indexOf(state.currentStep);

  const nextStep = useCallback(() => {
    const errors = validateStep(state.currentStep, state.data);
    if (errors.length > 0) {
      dispatch({ type: 'SET_VALIDATION_ERRORS', errors });
      return;
    }
    pushUndo(state);
    dispatch({ type: 'NEXT_STEP', availableSteps });
  }, [state, pushUndo, availableSteps]);

  const prevStep = useCallback(() => {
    pushUndo(state);
    dispatch({ type: 'PREV_STEP', availableSteps });
  }, [state, pushUndo, availableSteps]);

  const validateCurrentStep = useCallback((): ValidationError[] => {
    const errors = validateStep(state.currentStep, state.data);
    dispatch({ type: 'SET_VALIDATION_ERRORS', errors });
    return errors;
  }, [state.currentStep, state.data]);

  // Auto-save
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(() => {
      saveDraft({ data: state.data, currentStep: state.currentStep, timestamp: Date.now() });
      saveVisitedSteps([...state.visitedSteps]);
    }, 500);
    return () => {
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    };
  }, [state.data, state.currentStep, state.visitedSteps]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) {
        e.preventDefault();
        redo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo]);

  const contextValue: FormContextValue = {
    state,
    dispatch,
    goToStep,
    nextStep,
    prevStep,
    undo,
    redo,
    canUndo,
    canRedo,
    availableSteps,
    currentStepIndex,
    setField,
    validateCurrentStep,
  };

  return <FormContext.Provider value={contextValue}>{children}</FormContext.Provider>;
}

export function useForm(): FormContextValue {
  const ctx = useContext(FormContext);
  if (!ctx) throw new Error('useForm must be used within a FormProvider');
  return ctx;
}

export function clearAllDrafts(): void {
  clearDraft();
  clearHistories();
}
