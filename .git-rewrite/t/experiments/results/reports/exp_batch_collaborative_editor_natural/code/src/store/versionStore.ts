import { create } from 'zustand';
import type { VersionEntry, VersionDiff } from '@/types/version';
import type { DocumentSnapshot } from '@/types/editor';
import { VersionManager } from '@/services/VersionManager';

interface VersionStore {
  versionManager: VersionManager;
  versions: VersionEntry[];
  selectedVersion: VersionEntry | null;
  diffResult: VersionDiff | null;
  initialized: boolean;

  init: () => Promise<void>;
  saveVersion: (snapshot: DocumentSnapshot, author: string, message?: string) => void;
  selectVersion: (version: VersionEntry | null) => void;
  diff: (fromVersion: number, toVersion: number) => void;
  revertTo: (version: number) => DocumentSnapshot | null;
  refresh: () => void;
}

export const useVersionStore = create<VersionStore>((set, get) => ({
  versionManager: new VersionManager(),
  versions: [],
  selectedVersion: null,
  diffResult: null,
  initialized: false,

  init: async () => {
    const vm = get().versionManager;
    await vm.init();
    set({ versions: vm.getAll(), initialized: true });
  },

  saveVersion: (snapshot, author, message) => {
    const vm = get().versionManager;
    vm.saveVersion(snapshot, author, message);
    set({ versions: vm.getAll() });
  },

  selectVersion: (version) => set({ selectedVersion: version, diffResult: null }),

  diff: (fromVersion, toVersion) => {
    const vm = get().versionManager;
    const result = vm.diff(fromVersion, toVersion);
    set({ diffResult: result });
  },

  revertTo: (version) => {
    return get().versionManager.revertTo(version);
  },

  refresh: () => {
    set({ versions: get().versionManager.getAll() });
  },
}));
