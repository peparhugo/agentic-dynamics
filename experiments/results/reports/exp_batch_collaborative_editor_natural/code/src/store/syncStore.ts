import { create } from 'zustand';
import type { ConnectionState } from '@/types/sync';

interface SyncStore {
  connectionState: ConnectionState;
  peers: number;
  pendingOps: number;
  lastSyncAt: number | null;
  error: string | null;

  setConnectionState: (state: ConnectionState) => void;
  setPeers: (count: number) => void;
  setPendingOps: (count: number) => void;
  setLastSyncAt: (timestamp: number) => void;
  setError: (error: string | null) => void;
}

export const useSyncStore = create<SyncStore>((set) => ({
  connectionState: 'disconnected',
  peers: 0,
  pendingOps: 0,
  lastSyncAt: null,
  error: null,

  setConnectionState: (state) => set({ connectionState: state }),
  setPeers: (count) => set({ peers: count }),
  setPendingOps: (count) => set({ pendingOps: count }),
  setLastSyncAt: (timestamp) => set({ lastSyncAt: timestamp }),
  setError: (error) => set({ error }),
}));
