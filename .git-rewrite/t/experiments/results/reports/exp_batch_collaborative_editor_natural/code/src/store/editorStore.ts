import { create } from 'zustand';
import type { DocumentState, FormatAttrs, EditorOp } from '@/types/editor';
import { CRDTManager } from '@/services/CRDTManager';
import { SyncEngine } from '@/services/SyncEngine';
import { CursorManager } from '@/services/CursorManager';

interface EditorStore {
  crdt: CRDTManager;
  syncEngine: SyncEngine | null;
  cursorManager: CursorManager;
  documentState: DocumentState;
  user: { id: string; name: string; color: string };
  localCursorPosition: number;
  isConnected: boolean;
  peerCount: number;
  pendingOps: number;

  initialize: (userId: string, userName: string, userColor: string, wsUrl: string) => Promise<void>;
  setSyncEngine: (engine: SyncEngine) => void;
  insertText: (position: number, text: string, attrs?: FormatAttrs) => void;
  deleteText: (start: number, length: number) => void;
  applyFormat: (start: number, end: number, attrs: FormatAttrs) => void;
  setCursorPosition: (pos: number, selection?: { anchor: number; head: number }) => void;
  updateDocumentState: (state: DocumentState) => void;
  setConnected: (connected: boolean) => void;
  setPeerCount: (count: number) => void;
  setPendingOps: (count: number) => void;
  disconnect: () => void;
}

export const useEditorStore = create<EditorStore>((set, get) => ({
  crdt: new CRDTManager(),
  syncEngine: null,
  cursorManager: new CursorManager(),
  documentState: { content: '', formats: [], version: 0, versionVector: {} },
  user: { id: '', name: '', color: '' },
  localCursorPosition: 0,
  isConnected: false,
  peerCount: 0,
  pendingOps: 0,

  initialize: async (userId, userName, userColor, wsUrl) => {
    const crdt = new CRDTManager(userId);
    get().cursorManager.start();
    const engine = new SyncEngine(crdt, wsUrl, { id: userId, name: userName, color: userColor });
    await engine.initialize();
    engine.connect();
    set({
      crdt,
      syncEngine: engine,
      user: { id: userId, name: userName, color: userColor },
      documentState: crdt.getState(),
    });
  },

  setSyncEngine: (engine) => set({ syncEngine: engine }),

  insertText: (position, text, attrs = {}) => {
    const { crdt, syncEngine } = get();
    const ops = crdt.localInsert(position, text, attrs);
    if (ops.length > 0 && syncEngine) {
      syncEngine.sendOps(ops);
    }
    set({ documentState: crdt.getState() });
  },

  deleteText: (start, length) => {
    const { crdt, syncEngine } = get();
    const ops = crdt.localDelete(start, length);
    if (ops.length > 0 && syncEngine) {
      syncEngine.sendOps(ops);
    }
    set({ documentState: crdt.getState() });
  },

  applyFormat: (start, end, attrs) => {
    const { crdt, syncEngine } = get();
    const ops = crdt.localFormat(start, end, attrs);
    if (ops.length > 0 && syncEngine) {
      syncEngine.sendOps(ops);
    }
    set({ documentState: crdt.getState() });
  },

  setCursorPosition: (pos, selection) => {
    const { syncEngine } = get();
    if (syncEngine) {
      syncEngine.setCursorPosition(pos, selection);
    }
    set({ localCursorPosition: pos });
  },

  updateDocumentState: (state) => set({ documentState: state }),

  setConnected: (connected) => set({ isConnected: connected }),
  setPeerCount: (count) => set({ peerCount: count }),
  setPendingOps: (count) => set({ pendingOps: count }),

  disconnect: () => {
    const { syncEngine, cursorManager } = get();
    cursorManager.stop();
    syncEngine?.disconnect();
    set({ syncEngine: null, isConnected: false });
  },
}));
