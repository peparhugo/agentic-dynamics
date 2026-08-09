const STORAGE_KEY = 'insurance_claim_wizard_draft';
const UNDO_HISTORY_KEY = 'insurance_claim_wizard_undo';
const REDO_HISTORY_KEY = 'insurance_claim_wizard_redo';
const VISITED_STEPS_KEY = 'insurance_claim_wizard_visited';

interface StoredState {
  data: unknown;
  currentStep: string;
  timestamp: number;
}

export function saveDraft(state: StoredState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full or unavailable
  }
}

export function loadDraft(): StoredState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredState;
  } catch {
    return null;
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function saveVisitedSteps(steps: string[]): void {
  try {
    localStorage.setItem(VISITED_STEPS_KEY, JSON.stringify(steps));
  } catch {
    // ignore
  }
}

export function loadVisitedSteps(): string[] {
  try {
    const raw = localStorage.getItem(VISITED_STEPS_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as string[];
  } catch {
    return [];
  }
}

export function saveUndoHistory(state: StoredState[]): void {
  try {
    localStorage.setItem(UNDO_HISTORY_KEY, JSON.stringify(state.slice(-30)));
  } catch {
    // ignore
  }
}

export function loadUndoHistory(): StoredState[] {
  try {
    const raw = localStorage.getItem(UNDO_HISTORY_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as StoredState[];
  } catch {
    return [];
  }
}

export function saveRedoHistory(state: StoredState[]): void {
  try {
    localStorage.setItem(REDO_HISTORY_KEY, JSON.stringify(state.slice(-30)));
  } catch {
    // ignore
  }
}

export function loadRedoHistory(): StoredState[] {
  try {
    const raw = localStorage.getItem(REDO_HISTORY_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as StoredState[];
  } catch {
    return [];
  }
}

export function clearHistories(): void {
  try {
    localStorage.removeItem(UNDO_HISTORY_KEY);
    localStorage.removeItem(REDO_HISTORY_KEY);
    localStorage.removeItem(VISITED_STEPS_KEY);
  } catch {
    // ignore
  }
}
