import { create } from 'zustand';
import type { CursorPosition } from '@/types/presence';

interface PresenceStore {
  remoteCursors: CursorPosition[];
  setCursors: (cursors: CursorPosition[]) => void;
  addCursor: (cursor: CursorPosition) => void;
  removeCursor: (clientId: string) => void;
}

export const usePresenceStore = create<PresenceStore>((set) => ({
  remoteCursors: [],
  setCursors: (cursors) => set({ remoteCursors: cursors }),
  addCursor: (cursor) =>
    set((state) => ({
      remoteCursors: [
        ...state.remoteCursors.filter((c) => c.clientId !== cursor.clientId),
        cursor,
      ],
    })),
  removeCursor: (clientId) =>
    set((state) => ({
      remoteCursors: state.remoteCursors.filter((c) => c.clientId !== clientId),
    })),
}));
